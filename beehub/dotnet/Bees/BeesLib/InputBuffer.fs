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

type Seg(head: int, tail: int, nRingFrames: int) =
  member val  Head = head  with get, set
  member val  Tail = tail  with get, set
  member this.Size  : int =
    assert (this.Head >= this.Tail)
    this.Head - this.Tail
  member this.IsActive  : bool =  this.Size <> 0

  member this.Copy() =  Seg(this.Head, this.Tail, nRingFrames)

  member this.AdvanceHead nFrames =
    let headNew = this.Head + nFrames
    assert (headNew < nRingFrames)
    this.Head <- headNew
  
  /// Trim nFrames from the tail.  May result in an empty Seg.
  member this.TrimTail nFrames  : unit =
    if this.Size > nFrames then  this.Tail <- this.Tail + nFrames
                           else  this.Head <- 0
                                 this.Tail <- 0


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type TakeFunctions =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type CallbackAcceptanceJob = {
  CbMessage        : CbMessage
  SegCur           : Seg
  SegOld           : Seg
  Latest           : DateTime
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

  let durationToNFrames (duration: TimeSpan) =
    let nFramesApprox = duration.TotalSeconds * float beesConfig.InSampleRate
    int (Math.Ceiling nFramesApprox)
    
  let mutable beesConfig = beesConfig // so it’s visible in the debugger
  let frameSize    = beesConfig.InChannelCount * sizeof<SampleType>
  let ringDuration = TimeSpan.FromMilliseconds(200) // beesConfig.RingBufferDuration
  let nRingFrames  = durationToNFrames ringDuration
  let nRingBytes   = int nRingFrames * frameSize
  let ringPtr      = Marshal.AllocHGlobal(nRingBytes)
  let gapDuration  = TimeSpan.FromMilliseconds 10
  let mutable nGapFrames = durationToNFrames gapDuration
  
  let indexToVoidptr index  : voidptr =
    let indexByteOffset = index * frameSize
    let intPtr = IntPtr (int ringPtr + indexByteOffset)
    intPtr.ToPointer()

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Putting data from the callback into the ring

  let mutable cbSegCur = Seg(0, 0, nRingFrames)
  let mutable cbSegOld = Seg(0, 0, nRingFrames)
  let mutable cbLatest = DateTime.Now

  let exchangeSegs() =
    assert not cbSegOld.IsActive
    assert (cbSegOld.Head = 0)
    let tmp = cbSegCur
    cbSegCur <- cbSegOld
    cbSegOld <- tmp

  // In case the callback’s nFrames arg varies from one callback to the next,
  // adjust nGapFrames for the maximum nFrames arg seen.
  // The goal is plenty of room between head and tail.
  // Code assumes that nRingFrames > 2 * nGapFrames
  let adjustNGapFrames nFrames =
    let gapCandidate = nFrames * 4
    nGapFrames <- max nGapFrames gapCandidate
    if nRingFrames < 2 * nGapFrames then
      failwith $"nRingFrames is too small. nFrames: {nFrames}  nGapFrames: {nGapFrames}  nRingFrames: {nRingFrames}"
  
  // type State = // |––––––––– ring ––––––––––|                                        
  //   | Empty    // |           gap           |                                        
  //   | AtBegin  // | segCur |      gap       |  gap >= minimum                        
  //   | Middle   // | gapB |  segCur   | gapA |  segCur has been trimmed      
  //   | AtEnd    // | gap |      segCur       |  unlikely: segCur fits exactly         
  //   | Chasing  // | segCur | gap |  segOld  |  There is likely some unused after segOld
  let prepForNewFrames nFrames =
    adjustNGapFrames nFrames
    let roomAhead = nRingFrames - (cbSegCur.Head + nFrames)
    if roomAhead >= 0 then
      // The block will fit after segCur.Head
      // state is Empty, AtBegin, Middle, Chasing
      if cbSegOld.IsActive then
        // state is Chasing
        // segOld is active and ahead of us.
        assert (cbSegCur.Head < cbSegOld.Tail)
        cbSegOld.TrimTail nFrames  // may result in segOld being empty
        // state is AtBegin, Chasing
      if not cbSegOld.IsActive then
        // state is Empty, AtBegin, Middle
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

  let copy (callbackBlockPtr: IntPtr) (head: int) nFrames =
    let fromPtr = callbackBlockPtr.ToPointer()
    let toPtr   = indexToVoidptr head
    let size    = int64 (nFrames * frameSize)
    () // Buffer.MemoryCopy(fromPtr, toPtr, size, size)

  let finshCallback (cbMessage: CbMessage) =
    let writeCallbackBlockToRing (callbackBlockPtr: IntPtr) =
      let nFrames = int cbMessage.FrameCount
      prepForNewFrames nFrames  // may update segCur.Head
      copy callbackBlockPtr cbSegCur.Head nFrames
      cbSegCur.AdvanceHead nFrames
      cbLatest <- cbMessage.Timestamp
    let submitCallbackAcceptanceJob callbackAcceptanceJob =
      jobQueue.Enqueue(CallbackAcceptance callbackAcceptanceJob)
    // Copy the data then Submit a FinshCallback job.
    let callbackBlockPtr = cbMessage.InputSamples
    writeCallbackBlockToRing callbackBlockPtr
    let callbackAcceptanceJob = {
      CbMessage        = cbMessage
      SegCur           = cbSegCur.Copy()
      SegOld           = cbSegOld.Copy()
      Latest           = cbLatest
      CompletionSource = TaskCompletionSource<unit>() }
    submitCallbackAcceptanceJob callbackAcceptanceJob
    callbackAcceptanceJob.CompletionSource.SetResult()
  
  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring
  
  let mutable segCur = cbSegCur.Copy()
  let mutable segOld = cbSegOld.Copy()
  let mutable latest = DateTime.Now
  
  let handleCallbackAcceptance callbackAcceptance =
    segCur <- callbackAcceptance.SegCur
    segOld <- callbackAcceptance.SegOld
    latest <- callbackAcceptance.Latest
    Console.WriteLine $"{segCur.Head}"
//  let cbMessage = callbackAcceptance.CbMessage
//  let nFrames = int cbMessage.FrameCount
//  let fromPtr = cbMessage.InputSamples.ToPointer()
//  let ringHeadPtr = indexToPointer segCur.Head
//  copy fromPtr ringHeadPtr nFrames


  let mutable bufBegin = DateTime.Now
  let mutable earliest = DateTime.Now
 
  
 
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
    printfn $"InputBuffer size: {nRingBytes / 1_000_000} MB for {ringDuration}"
    printfn $"InputBuffer nFrames: {nRingFrames}"
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

  // Called from the callback; internal use.
  member this.FinishCallback(cbMessage: CbMessage) =  finshCallback cbMessage
    
  /// Reach back as close as possible to a time in the past.
  member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
    get dateTime duration worker

  /// Keep as much as possible of the given TimeSpan
  /// and return the start DateTime of what is currently kept.
  member this.Keep(duration: TimeSpan)  : DateTime = keep duration
