module BeesLib.InputBuffer

open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open BeesUtil.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open PortAudioSharp


type Worker = Buf -> int -> int

let tbdTimeHead = DateTime.MinValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The ring buffer functions as 0, 1, or 2 active segments.
//
//            |––––––––– ring ––––––––––|
// Empty    0 |           gap           |
// AtBegin  1 | segCur |      gap       |  gap >= minimum
// Middle   1 | gapB |  segCur   | gapA |  segCur growth has caused it to trim itself
// AtEnd    1 | gap  |      segCur      |  segCur can go no further. (unlikely: segCur fits exactly)
// Chasing  2 | segCur | gap |  segOld  |  After segOld there is likely unused (nRingFrames % nFrames)
//
// Empty –> AtBegin –> Middle –> AtEnd –> Chasing –> AtBegin ...
//
//      || time  –>                 A                                                     A
// seg0 || inactive  | cur growing  | old shrinking | inactive | cur growing              | ...
// seg1 || inactive  | inactive     | cur growing              | old shrinking | inactive | ...

type Seg(head: int, tail: int, nRingFrames: int, beesConfig: BeesConfig) =
  let duration nFrames = TimeSpan.FromSeconds (float nFrames / float beesConfig.InSampleRate)
  member val  Head     = head                                                     with get, set
  member val  Tail     = tail                                                     with get, set
  member this.Size     = assert (this.Head >= this.Tail) ; this.Head - this.Tail
  member this.Duration = duration this.Size
  member val  TimeHead = tbdTimeHead                                              with get, set
  member this.TimeTail = this.TimeHead - this.Duration
  member this.IsActive = this.Size <> 0

  member this.Copy()   = Seg(this.Head, this.Tail, nRingFrames, beesConfig)

  member this.Reset() = this.Head <- 0 ; this.Tail <- 0

  member this.AdvanceHead nFrames timeHead =
    let headNew = this.Head + nFrames
    assert (headNew <= nRingFrames)
    this.Head     <- headNew
    this.TimeHead <- timeHead

  /// Trim nFrames from the tail.  May result in an empty Seg.
  member this.TrimTail nFrames  : unit =
    if this.Size > nFrames then  this.Tail <- this.Tail + nFrames
                           else  this.Reset()


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type TakeFunction =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type CallbackAcceptanceJob = {
  CbMessage        : CbMessage
  SegCur           : Seg
  SegOld           : Seg
  CompletionSource : TaskCompletionSource<unit> }

type TakeJob = {
  Data: TakeFunction
  CompletionSource: TaskCompletionSource<unit> }

type Job =
  | CallbackAcceptance of CallbackAcceptanceJob
  | Take               of TakeJob

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type InputBuffer(beesConfig: BeesConfig) =

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

  let mutable cbSegCur = Seg(0, 0, nRingFrames, beesConfig)  // seg0
  let mutable cbSegOld = Seg(0, 0, nRingFrames, beesConfig)  // seg1

  let exchangeSegs() =
    assert not cbSegOld.IsActive
    let tmp = cbSegCur
    cbSegCur <- cbSegOld
    cbSegOld <- tmp
    assert (cbSegCur.Head = 0)
    cbSegCur.TimeHead <- tbdTimeHead

  // In case the callback’s nFrames arg varies from one callback to the next,
  // adjust nGapFrames for the maximum nFrames arg seen.
  // The goal is plenty of room between head and tail.
  // Code assumes that nRingFrames > 2 * nGapFrames
  let adjustNGapFrames nFrames =
    let gapCandidate = nFrames * 4
    nGapFrames <- max nGapFrames gapCandidate
    if nRingFrames < 2 * nGapFrames then
      failwith $"nRingFrames is too small. nFrames: {nFrames}  nGapFrames: {nGapFrames}  nRingFrames: {nRingFrames}"
  
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

  let finishCallback (cbMessage: CbMessage) =
    let writeCallbackBlockToRing (callbackBlockPtr: IntPtr) =
      let nFrames = int cbMessage.FrameCount
      prepForNewFrames nFrames // may update segCur.Head
      copy callbackBlockPtr cbSegCur.Head nFrames
      cbSegCur.AdvanceHead nFrames cbMessage.Timestamp
    let submitCallbackAcceptanceJob callbackAcceptanceJob =
      jobQueue.Enqueue(CallbackAcceptance callbackAcceptanceJob)
    // Copy the data then Submit a FinshCallback job.
    let callbackBlockPtr = cbMessage.InputSamples
    writeCallbackBlockToRing callbackBlockPtr
    let callbackAcceptanceJob = {
      CbMessage        = cbMessage
      SegCur           = cbSegCur.Copy()
      SegOld           = cbSegOld.Copy()
      CompletionSource = TaskCompletionSource<unit>() }
    submitCallbackAcceptanceJob callbackAcceptanceJob
    callbackAcceptanceJob.CompletionSource.SetResult()

  // Called from the method
  let callback input output frameCount timeInfo statusFlags userDataPtr cbContext =
    let timeStamp = DateTime.Now
    let (input : IntPtr) = input
    let (output: IntPtr) = output
    let withEcho  = Volatile.Read &cbContext.WithEchoRef.contents
    let seqNum    = Volatile.Read &cbContext.SeqNumRef.contents
    if withEcho then
      let size = uint64 (frameCount * uint32 sizeof<float32>)
      Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
    Volatile.Write(cbContext.SeqNumRef, seqNum + 1)
    match cbContext.CbMessagePool.Take() with
    | None -> // Yikes, pool is empty
      cbContext.Logger.Add seqNum timeStamp "CbMessagePool is empty" null
      PortAudioSharp.StreamCallbackResult.Continue
    | Some cbMessage ->
      if Volatile.Read &cbContext.WithLoggingRef.contents then
        cbContext.Logger.Add seqNum timeStamp "cb bufs=" cbMessage.PoolStats
      // the callback args
      cbMessage.InputSamples <- input
      cbMessage.Output       <- output
      cbMessage.FrameCount   <- frameCount
      cbMessage.TimeInfo     <- timeInfo
      cbMessage.StatusFlags  <- statusFlags
      cbMessage.UserDataPtr  <- userDataPtr
      // more from the callback
      cbMessage.CbContext    <- cbContext
      cbMessage.WithEcho     <- withEcho 
      cbMessage.SeqNum       <- seqNum
      cbMessage.Timestamp    <- timeStamp
      match cbContext.CbMessagePool.CountAvail with
      | 0 -> PortAudioSharp.StreamCallbackResult.Complete // todo should continue?
      | _ -> finishCallback cbMessage
             PortAudioSharp.StreamCallbackResult.Continue

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring
  
  let mutable segCur = cbSegCur.Copy()
  let mutable segOld = cbSegOld.Copy()
  let segOldest() = if segOld.IsActive then segCur else segOld
  let mutable timeTail = segOldest().TimeTail
  let mutable timeHead = segCur     .TimeHead
  
  let handleCallbackAcceptance callbackAcceptance =
    let cbMessage = callbackAcceptance.CbMessage
    cbMessage.CbContext.CbMessagePool.ItemUseBegin()
    segCur <- callbackAcceptance.SegCur
    segOld <- callbackAcceptance.SegOld
    Console.WriteLine $"{segCur.Head}"
    // ...
    cbMessage.CbContext.CbMessagePool.ItemUseEnd(cbMessage)
//  let cbMessage = callbackAcceptance.CbMessage
//  let nFrames = int cbMessage.FrameCount
//  let fromPtr = cbMessage.InputSamples.ToPointer()
//  let ringHeadPtr = indexToPointer segCur.Head
//  copy fromPtr ringHeadPtr nFrames
 
  
 
  let handleTake inputTake =
    ()
    // let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
    // let size = frameCountToByteCount inputTake.FrameCount 
    // System.Buffer.BlockCopy(from, 0, buffer, index, size)
    // advanceIndex inputTake.FrameCount
    // inputTake.CompletionSource.SetResult()
   
  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Process jobs from jobQueue

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
      elif dateTime < timeTail then  timeTail
                               else  dateTime
    () // todo WIP
    
  let keep (duration: TimeSpan) =
    assert (duration > TimeSpan.Zero)
    let now = DateTime.Now
    let dateTime = now - duration
    timeTail <- 
      if dateTime < timeTail then  timeTail
                             else  dateTime
    timeTail
    
  let locationOfDateTime (dateTime: DateTime)  : Option<Seg * int> =
    if not (timeTail <= dateTime && dateTime <= timeHead) then Some (segCur, 1)
    else None

  
  // Called from the PortAudio callback at interrupt time; internal use.
  member this.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr, cbContext) =
    callback           input  output  frameCount  timeInfo  statusFlags  userDataPtr  cbContext

  /// Create a stream of samples starting at a past DateTime.
  /// The stream is exhausted when it gets to the end of buffered data.
  /// The recipient is responsible for separating out channels from the sequence.
  // member this.Get(dateTime: DateTime, worker: Worker)  : SampleType seq option = seq {
  //    let segIndex = segOfDateTime dateTime
  //    match seg with
  //    | None: return! None
  //    | Some seg :
  //    if isInSegOld dateTime then
  //    todo WIP
  //      
  // }
