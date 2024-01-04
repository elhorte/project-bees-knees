module BeesLib.RingBuffer

open System
open System.Collections.Concurrent
open System.Runtime.InteropServices
open System.Threading.Tasks
open BeesLib.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open Microsoft.FSharp.NativeInterop

type Worker = Buf -> int -> int


type TakeFunctions =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type CallbackJob = {
  CbMessage        : CbMessage
  CompletionSource : TaskCompletionSource<unit> }

type TakeJob = {
  Data: TakeFunctions
  CompletionSource: TaskCompletionSource<unit> }

type Job =
  | Callback of CallbackJob
  | Take     of TakeJob

type Seg() =
  member val head  = 0  with get, set
  member val tail  = 0  with get, set
  member this.size  : int =
    assert (this.head >= this.tail)
    this.head - this.tail
  member this.isEmpty  : bool = this.size = 0
  
  /// Trim nFrames from the tail.
  /// The result might be an empty Seg.
  member this.trim nFrames  : unit =
    if this.size > nFrames then  this.tail <- this.tail + nFrames
                           else  this.head <- 0
                                 this.tail <- 0


type RingBuffer(beesConfig: BeesConfig) =

  let jobQueue = AsyncConcurrentQueue<Job>()

  let frameSize   = beesConfig.InChannelCount * sizeof<SampleType>
  let nRingFrames = beesConfig.RingBufferDuration.Seconds * beesConfig.InSampleRate
  let nRingBytes  = int nRingFrames * frameSize
  let ringPtr =
    Marshal.AllocHGlobal(nRingBytes)
    |> NativePtr.ofNativeInt<float32>

  // These are used only at callback time.
  let mutable gap = 0 // gap maintained between head and tail as head advances
  let seg0 = Seg()
  let seg1 = Seg()
  let segs = [| seg0; seg1 |]
  let mutable segCur = seg0
  let mutable segOld = seg1
  let mutable segCurNum = 0
  let mutable segOldNum = 1

  let exchangeSegs() =
    assert segOld.isEmpty
    assert (segOld.head = 0)
    segCurNum <- 1 - segCurNum
    segOldNum <- 1 - segOldNum
    segCur <- segs[segCurNum]
    segOld <- segs[segOldNum]

  let adjustSegs nFrames =
    let roomAhead = nRingFrames - (segCur.head + nFrames)
    if roomAhead >= 0 then
      // The block will fit at the head of curSeg
      if not segOld.isEmpty then
        assert (segCur.head < segOld.tail)
        segOld.trim nFrames
      if segOld.isEmpty then
        // ensure that there is a gap made up of
        // - room after  segCur.head + nFrames -> room
        // - room before segCur.tail           -> gap - room
        let roomBehind = gap - roomAhead
        if roomBehind > 0 then
          segCur.tail <- roomBehind
        else
          assert (segCur.tail = 0)
    else
      // The block will not fit at the head of curSeg.
      exchangeSegs()
      // segCur starts fresh with head = 0, tail = 0, and we trim away segOld.tail to ensure the gap.
      segOld.tail <- nFrames + gap

  // If the callback nFrames arg varies,
  // adjust the gap for the maximum nFrames seen.
  // The goal is plenty of room between head and tail as head advances.
  let adjustGapSize nFrames =
    let gapCandidate = nFrames * 10
    gap <- max gap gapCandidate

  // let modulo index =
  //   let excess = index - nRingFrames
  //   if excess >= 0 then  excess // wraps
  //                  else  index
  
  let indexToPointer index  : nativeptr<SampleType> =  NativePtr.add ringPtr (index * sizeof<float32>)
      
  let writeBlock (block: nativeptr<SampleType>) nFrames =
    adjustGapSize nFrames
    adjustSegs nFramesf
    let toPtr = indexToPointer segCur.head
    Marshal.Copy(toPtr, block, startIndex = 0, length = (int nFrames))
    segCur.head <- segCur.head + nFrames

    
  member this.WriteBlock(block: nativeptr<SampleType>, nFrames: int) = 
    writeBlock block nFrames
  
  let mutable bufBegin = DateTime.Now
  let mutable earliest = DateTime.Now
  let mutable index    = 0
  let duration = beesConfig.ringBufferDuration
  let nSamples = beesConfig.ringBufferDuration.Seconds * beesConfig.inSampleRate * beesConfig.nChannels
  let nBytes = frameCountToByteCount nSamples
  let buffer = Array.init nSamples (fun _ -> float32 0.0f)

  let advanceIndex count =
    let indexNew = index + count
    let excess = indexNew - nBytes
    index <- if excess < 0 then  index + int count else  0
  
  let handleCallback inputCallback =
    let cbMessage = inputCallback.CbMessage
    let (BufRef bufArrayRef) = cbMessage.InputSamplesCopyRef
    let from = !bufArrayRef
    let size = int cbMessage.FrameCount 
    System.Buffer.BlockCopy(from, 0, buffer, index, size)
    advanceIndex size
    inputCallback.CompletionSource.SetResult()
  
  let handleTake inputTake =
    ()
    // let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
    // let size = frameCountToByteCount inputTake.FrameCount 
    // System.Buffer.BlockCopy(from, 0, buffer, index, size)
    // advanceIndex inputTake.FrameCount
    // inputTake.CompletionSource.SetResult()
  
  // Method to process jobQueue items
  let rec processQueue() = task {
    let! job = jobQueue.DequeueAsync()
    match job with
    | Callback x ->  handleCallback x
    | Take     x ->  handleTake     x
    return! processQueue() }

  // Submit a job
  let doCallback cbMessage _ _ =
    let callbackJob = {
      CbMessage        = cbMessage
      CompletionSource = TaskCompletionSource<unit>() }
    jobQueue.Enqueue(Callback callbackJob)

  do
    cbMessageWorkList.Subscribe(doCallback)
    Task.Run<unit> (fun () -> task { do! processQueue() }) |> ignore

  
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
    
  /// Reach back as close as possible to a time in the past.
  member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
    get dateTime duration worker

  /// Keep as much as possible of the given TimeSpan
  /// and return the start DateTime of what is currently kept.
  member this.Keep(duration: TimeSpan)  : DateTime = keep duration

  // Method to submit a job
  member this.Callback(cbMessage: CbMessage, workId: WorkId, unsubscribeMe: Unsubscriber) =
    doCallback cbMessage workId unsubscribeMe
