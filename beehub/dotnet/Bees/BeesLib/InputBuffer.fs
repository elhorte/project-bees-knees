module BeesLib.InputBuffer

open System
open System.Collections.Concurrent
open System.Runtime.InteropServices
open System.Threading.Tasks

open BeesLib.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool


type Worker = Buf -> int -> int

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type Seg(head: int, tail: int) =
  member val Head = 0  with get, set
  member val Tail = 0  with get, set
  member this.Size  : int =
    assert (this.Head >= this.Tail)
    this.Head - this.Tail
  member this.IsEmpty  : bool =  this.Size = 0
  
  /// Trim nFrames from the tail.  May result in an empty Seg.
  member this.TrimTail nFrames  : unit =
    if this.Size > nFrames then  this.Tail <- this.Tail + nFrames
                           else  this.Head <- 0
                                 this.Tail <- 0

  member this.Copy()  : Seg =  Seg(this.Head, this.Tail)

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type TakeFunctions =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type CallbackAcceptanceJob = {
  CbMessage        : CbMessage
  SegCur           : Seg
  SegOld           : Seg
  CompletionSource : TaskCompletionSource<unit> }

type TakeJob = {
  Data: TakeFunctions
  CompletionSource: TaskCompletionSource<unit> }

type Job =
  | CallbackAcceptance of CallbackAcceptanceJob
  | Take               of TakeJob

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type InputBuffer(beesConfig     : BeesConfig     ,
                 cbMessageQueue : CbMessageQueue ) =

  let jobQueue = AsyncConcurrentQueue<Job>()

  let frameSize   = beesConfig.InChannelCount * sizeof<SampleType>
  let nRingFrames = beesConfig.RingBufferDuration.Seconds * beesConfig.InSampleRate
  let nRingBytes  = int nRingFrames * frameSize
  let ring        = Marshal.AllocHGlobal(nRingBytes)
  let gapDuration = TimeSpan.FromMilliseconds 10
  let mutable nGapFrames = gapDuration.Seconds * beesConfig.InSampleRate
  
  let indexToPointer index  : voidptr =
    let indexByteOffset = index * frameSize
    let intPtr = IntPtr (int ring + indexByteOffset)
    intPtr.ToPointer()

  // These are used only when getting data from the callback.
  let mutable cbSegCur = Seg(0, 0)
  let mutable cbSegOld = Seg(0, 0)
  // These are used only for giving out ring data.
  let mutable segCur = Seg(0, 0)
  let mutable segOld = Seg(0, 0)
  
  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // getting data from the callback

  let exchangeSegs() =
    assert  cbSegOld.IsEmpty
    assert (cbSegOld.Head = 0)
    let tmp = cbSegCur
    cbSegCur <- cbSegOld
    cbSegOld <- tmp

  // In case the callback’s nFrames arg varies from one callback to the next,
  // adjust the gap for the maximum nFrames arg seen.
  // The goal is plenty of room between head and tail.
  let adjustRingGapSize nFrames =
    let gapCandidate = nFrames * 10 // Code assumes that gap > nFrames
    nGapFrames <- max nGapFrames gapCandidate
  
  // type State = // |––––––––– ring ––––––––––|                                        
  //   | Empty    // |           gap           |                                        
  //   | AtBegin  // | segCur |      gap       |  gap >= minimum                        
  //   | Middle   // | gapB |  segCur   | gapA |  segCur has been trimmed      
  //   | AtEnd    // | gap |      segCur       |  unlikely: segCur fits exactly         
  //   | Chasing  // | segCur | gap |  segOld  |  There is likely some unused after segOld
  let prepRingHead nFrames =
    adjustRingGapSize nFrames
    let roomAhead = nRingFrames - (cbSegCur.Head + nFrames)
    if roomAhead >= 0 then
      // The block will fit after segCur.Head
      // state is Empty, AtBegin, Middle, Chasing
      if not cbSegOld.IsEmpty then
        // state is Chasing
        // segOld is active and ahead of us.
        assert (cbSegCur.Head < cbSegOld.Tail)
        cbSegOld.TrimTail nFrames  // may result in segOld being empty
        // state is AtBegin, Chasing
      if cbSegOld.IsEmpty then
        // state is Empty, AtBegin, Middle
        assert (cbSegCur.Tail = 0)
        let roomBehind = nGapFrames - roomAhead
        if roomBehind > 0 then
          // Some of the gap will be at the beginning of the ring.
          cbSegCur.Tail <- roomBehind
          // state is Middle, AtEnd
        else ()
          // state is AtBegin, Middle
    else
      // state is Middle
      // The block will not fit at the segCur.Head.
      exchangeSegs()
      assert (cbSegCur.Head = 0)
      // segCur starts fresh with head = 0, tail = 0, and we trim away segOld.Tail to ensure the gap.
      cbSegOld.Tail <- nFrames + nGapFrames
      // state is Chasing

  let copy (fromPtr: voidptr) (toPtr: voidptr) nFrames =
    let size = int64 (nFrames * frameSize)
    Buffer.MemoryCopy(fromPtr, toPtr, size, size)

  let finshCallback (cbMessage: CbMessage) =
    let writeCallbackBlockToRing (callbackBlockPtr: voidptr) =
      let nFrames = int cbMessage.FrameCount
      prepRingHead nFrames  // mutates segCur.Head
      let ringHeadPtr = indexToPointer cbSegCur.Head
      copy callbackBlockPtr ringHeadPtr nFrames
      cbSegCur.Head <- cbSegCur.Head + nFrames
      let callbackAcceptanceJob = {
        CbMessage        = cbMessage
        SegCur           = cbSegCur.Copy()
        SegOld           = cbSegOld.Copy()
        CompletionSource = TaskCompletionSource<unit>() }
      callbackAcceptanceJob
    let submitCallbackAcceptanceJob callbackAcceptanceJob =
      jobQueue.Enqueue(CallbackAcceptance callbackAcceptanceJob)
    // Copy the data then Submit a FinshCallback job.
    let callbackBlockPtr = cbMessage.InputSamples.ToPointer()
    let callbackAcceptanceJob = writeCallbackBlockToRing callbackBlockPtr
    submitCallbackAcceptanceJob callbackAcceptanceJob
    callbackAcceptanceJob.CompletionSource.SetResult()
  
  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // giving out ring data
  
  let handleCallbackAcceptance callbackAcceptance =
    segCur <- callbackAcceptance.SegCur
    segOld <- callbackAcceptance.SegOld
      
  
  let mutable bufBegin = DateTime.Now
  let mutable earliest = DateTime.Now
  let duration = beesConfig.RingBufferDuration
 
  
 
  let handleTake inputTake =
    ()
    // let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
    // let size = frameCountToByteCount inputTake.FrameCount 
    // System.Buffer.BlockCopy(from, 0, buffer, index, size)
    // advanceIndex inputTake.FrameCount
    // inputTake.CompletionSource.SetResult()
  
  // Method to process jobQueue items

  let processQueue() =
    let run job =
      match job with
      | CallbackAcceptance x ->  handleCallbackAcceptance x
      | Take               x ->  handleTake               x
    let rec loop() = task {
      let! job = jobQueue.DequeueAsync()
      run job
      return! loop() }
    task { do! loop() }
   
  do
    Task.Run<unit> processQueue |> ignore

  
  let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
    let now = DateTime.Now
    let beginDt =
      if   dateTime > now      then  now
      elif dateTime < earliest then  earliest
                               else  dateTime
    ()
    
  let keep (duration: TimeSpan) =
    assert (duration > TimeSpan.Zero)
    let now = DateTime.Now
    let dateTime = now - duration
    earliest <- 
      if dateTime < earliest then  earliest
                             else  dateTime
    earliest

  // Called from the callback
  member this.FinishCallback(cbMessage: CbMessage) =  finshCallback cbMessage
    
  /// Reach back as close as possible to a time in the past.
  member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
    get dateTime duration worker

  /// Keep as much as possible of the given TimeSpan
  /// and return the start DateTime of what is currently kept.
  member this.Keep(duration: TimeSpan)  : DateTime = keep duration
