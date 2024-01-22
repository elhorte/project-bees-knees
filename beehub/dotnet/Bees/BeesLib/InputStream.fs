module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesUtil.WorkList
open BeesUtil.PortAudioUtils
open PortAudioSharp


type Worker = Buf -> int -> int

let tbdTimeHead = DateTime.MinValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The ring buffer comprises 0, 1, or 2 active segments.
//
//            |––––––––– ring ––––––––––|
// Empty    0 |           gap           |
// AtBegin  1 | segCur |      gap       |  gap >= minimum
// Middle   1 | gapB |  segCur   | gapA |  segCur growth has caused it to trim itself
// AtEnd    1 | gap  |      segCur      |  segCur can go no further; happens on only one callback per repeating cycle
// Chasing  2 | segCur | gap |  segOld  |  After segOld there is likely unused (nRingFrames % nFrames)
//                                         Note: when AtEnd, segCur may fit exactly but this is unlikely.
//
// Repeating lifecycle:  Empty –> AtBegin –> Middle –> AtEnd –> Chasing –> AtBegin ...
//
//      || time  –>  A (repeat point)                    X (exchange point)                                                  A
//      || Empty     | AtBegin      | Middle     | AtEnd | Chasing       | AtBegin      | Middle     | AtEnd | Chasing       |
// seg0 || inactive  | cur growing  | cur moving         | old shrinking | inactive     | inactive           | cur growing   |
// seg1 || inactive  | inactive     | inactive           | cur growing   | cur growing  | cur moving         | old shrinking |
//
// There are two pairs of segments:
//
//    callback  client
//      time     task
//    --------  ------
//    cbSegCur  segCur   .Head is overall head of data
//    cbSegOld  segOld   .Tail is overall tail of data
// 
// A background task loop takes each job from jobQueue and runs it to completion.
// Each callback    queues a job to copy cbSegCur/cbSegOld to segCur/segOld
// Each client call queues a job to access data from the ring.
// Client calls have to be asynchronous because they have to run in the jobQueue task.

type Seg(head: int, tail: int, nRingFrames: int, beesConfig: BeesConfig) =
  let duration nFrames = TimeSpan.FromSeconds (float nFrames / float beesConfig.InSampleRate)
  member val  Head     = head                                                     with get, set
  member val  Tail     = tail                                                     with get, set
  member this.NFrames  = assert (this.Head >= this.Tail) ; this.Head - this.Tail
  member this.Duration = duration this.NFrames
  member val  TimeHead = tbdTimeHead                                              with get, set
  member this.TimeTail = this.TimeHead - this.Duration
  member this.Active   = this.NFrames <> 0
  member this.Copy()   = Seg(this.Head, this.Tail, nRingFrames, beesConfig)
  member this.Reset()  = this.Head <- 0 ; this.Tail <- 0 ; assert (not this.Active)

  member this.AdvanceHead nFrames timeHead =
    let headNew = this.Head + nFrames
    assert (headNew <= nRingFrames)
    this.Head     <- headNew
    this.TimeHead <- timeHead

  /// Trim nFrames from the tail.  May result in an inactive Seg.
  member this.TrimTail nFrames  : unit =
    if this.NFrames > nFrames then  this.Tail <- this.Tail + nFrames
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


/// <summary>Make the pool of CbMessages used by the stream callback</summary>
let makeCbMessagePool beesConfig =
  let bufSize    = 1024
  let startCount = Environment.ProcessorCount * 4    // many more than number of cores
  let minCount   = 4
  CbMessagePool(bufSize, startCount, minCount)


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type InputStream(beesConfig: BeesConfig, withEcho: bool, withLogging: bool) =
  let startTime = DateTime.Now
  let logger = Logger(8000, startTime)
  let cancellationTokenSource = new CancellationTokenSource()
  let jobQueue = AsyncConcurrentQueue<Job>()
  let cbMessageWorkList = WorkList<CbMessage>()
  let cbMessagePool: CbMessagePool = makeCbMessagePool beesConfig
  let mutable paStream = dummyInstance<PortAudioSharp.Stream>()
  let mutable seqNum = 0
  let mutable withEcho = false
  let mutable withLogging = false
  let getWithEcho   () = Volatile.Read &withEcho
  let getWithLogging() = Volatile.Read &withEcho

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
    let intPtr = ringPtr + IntPtr indexByteOffset
    intPtr.ToPointer()

  //–––––––––––––––––––––––––––––––––––––

  /// <summary>
  ///   Continuously receives messages from a CbMessageQueue;
  ///   processes each message with the provided function.
  /// </summary>
  /// <param name="workPerCallback"> A function to process each message.                     </param>
  /// <param name="cbMessageQueue"    > A CbMessageQueue from which to receive the messages. </param>
  let cbMessageQueueHandler workPerCallback (cbMessageQueue: CbMessageQueue) =
  //let mutable callbackMessage = Unchecked.defaultof<CbMessage>
    let doOne (m: CbMessage) =
      cbMessagePool.ItemUseBegin()
      workPerCallback m
      cbMessagePool.ItemUseEnd   m
    cbMessageQueue.iter doOne

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // CbMessageQueue

  /// <summary>
  ///   Creates and starts a CbMessageQueue that will process CbMessages inserted by callbacks.
  /// </summary>
  /// <param name="workPerCallback">A function that processes a CbMessageQueueMessage</param>
  /// <returns>Returns a started CbMessageQueue</returns>
  let makeAndStartCbMessageQueue workPerCallback  : CbMessageQueue =
    let cbMessageQueue = CbMessageQueue()
    let handler() = cbMessageQueueHandler workPerCallback cbMessageQueue
    Task.Run handler |> ignore
    cbMessageQueue

  let cbMessageQueue = makeAndStartCbMessageQueue cbMessageWorkList.HandleEvent

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Putting data from the callback into the ring

  let mutable cbSegCur = Seg(0, 0, nRingFrames, beesConfig)  // seg0
  let mutable cbSegOld = Seg(0, 0, nRingFrames, beesConfig)  // seg1

  let exchangeSegs() =
    assert not cbSegOld.Active
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
      if cbSegOld.Active then
        // state is Chasing
        // segOld is active and ahead of us.
        assert (cbSegCur.Head < cbSegOld.Tail)
        cbSegOld.TrimTail nFrames  // may result in segOld being inactive
        // state is AtBegin, Chasing
      if not cbSegOld.Active then
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
  
  let copy (callbackBlockPtr: IntPtr) (head: int) nFrames  : IntPtr =
    let fromPtr = callbackBlockPtr.ToPointer()
    let toPtr   = indexToVoidptr head
    let size    = int64 (nFrames * frameSize)
    paTryCatchRethrow (fun () -> Buffer.MemoryCopy(fromPtr, toPtr, size, size))
    IntPtr toPtr

  // // for debug
  // let printCallback (i: InputStream) (m: CbMessage) =
  //   let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
  //   let percentCPU   = i.PaStream.CpuLoad * 100.0
  //   let sDebug = sprintf "%3d: %A %s" m.SeqNum m.Timestamp m.PoolStats
  //   let sWork  = sprintf $"work: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
  //   Console.WriteLine($"{sDebug}   ––   {sWork}")

  // Called from the Callback method
  // Must not allocate memory because this is a system-level callback
  let callback input output frameCount timeInfo statusFlags userDataPtr =
    let finishCallback (cbMessage: CbMessage) =
      let writeCallbackBlockToRing (callbackBlockPtr: IntPtr) =
        let nFrames = int cbMessage.FrameCount
        prepForNewFrames nFrames // may update segCur.Head
        let ptr = copy callbackBlockPtr cbSegCur.Head nFrames
        cbSegCur.AdvanceHead nFrames cbMessage.Timestamp
        ptr
      let submitCallbackAcceptanceJob callbackAcceptanceJob =
        jobQueue.Enqueue(CallbackAcceptance callbackAcceptanceJob)
      // Copy the data then Submit a FinshCallback job.
      let ptrToCopy = writeCallbackBlockToRing cbMessage.InputSamples
      cbMessage.InputSamplesRingCopy <- ptrToCopy
      let callbackAcceptanceJob = {
        CbMessage        = cbMessage
        SegCur           = cbSegCur.Copy()
        SegOld           = cbSegOld.Copy()
        CompletionSource = TaskCompletionSource<unit>() }
      submitCallbackAcceptanceJob callbackAcceptanceJob
      callbackAcceptanceJob.CompletionSource.SetResult()
    let timeStamp = DateTime.Now
    let (input : IntPtr) = input
    let (output: IntPtr) = output
    if getWithEcho() then
      let size = uint64 (frameCount * uint32 sizeof<float32>)
      Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
    seqNum <- seqNum + 1
    match cbMessagePool.Take() with
    | None -> // Yikes, pool is empty
      logger.Add seqNum timeStamp "CbMessagePool is empty" null
      PortAudioSharp.StreamCallbackResult.Continue
    | Some cbMessage ->
      if getWithLogging() then  logger.Add seqNum timeStamp "cb bufs=" cbMessagePool.PoolStats
      // the callback args
      cbMessage.InputSamples <- input
      cbMessage.Output       <- output
      cbMessage.FrameCount   <- frameCount
      cbMessage.TimeInfo     <- timeInfo
      cbMessage.StatusFlags  <- statusFlags
      cbMessage.UserDataPtr  <- userDataPtr
      // more from the callback
      cbMessage.WithEcho     <- withEcho
      cbMessage.Timestamp    <- timeStamp
      cbMessage.SeqNum       <- seqNum
      match cbMessagePool.CountAvail with
      | 0 -> PortAudioSharp.StreamCallbackResult.Complete // should continue?
      | _ -> finishCallback cbMessage
             PortAudioSharp.StreamCallbackResult.Continue

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring
  
  let mutable segCur = cbSegCur.Copy()
  let mutable segOld = cbSegOld.Copy()
  let segOldest() = if segOld.Active then segOld else segCur
  let mutable timeTail = segOldest().TimeTail
  let mutable timeHead = segCur     .TimeHead
  
  let handleCallbackAcceptance callbackAcceptance =
    let cbMessage = callbackAcceptance.CbMessage
    cbMessagePool.ItemUseBegin()
    segCur <- callbackAcceptance.SegCur
    segOld <- callbackAcceptance.SegOld
    Console.WriteLine $"{segCur.Head}"
    // ...
    cbMessagePool.ItemUseEnd(cbMessage)
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
      if cancellationTokenSource.IsCancellationRequested then return () else
      let! job = jobQueue.DequeueAsync()
      run job
      return! loop() }
    task { do! loop() }
  
  let start() =
    paTryCatchRethrow(fun() -> paStream.Start())
    printfn $"InputStream size: {nRingBytes / 1_000_000} MB for {ringDuration}"
    printfn $"InputStream nFrames: {nRingFrames}"
    Task.Run<unit> processQueue |> ignore

  let stop() =
    paStream.Stop()
    cancellationTokenSource.Cancel()
   
//   let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
//     let now = DateTime.Now
//     let beginDt =
//       if   dateTime > now      then  now
//       elif dateTime < timeTail then  timeTail
//                                else  dateTime
//     () // WIP
//     
//   let keep (duration: TimeSpan) =
//     assert (duration > TimeSpan.Zero)
//     let now = DateTime.Now
//     let dateTime = now - duration
//     timeTail <- 
//       if dateTime < timeTail then  timeTail
//                              else  dateTime
//     timeTail
//     
//   let locationOfDateTime (dateTime: DateTime)  : Option<Seg * int> =
//     if not (timeTail <= dateTime && dateTime <= timeHead) then Some (segCur, 1)
//     else None

   
  member val CbMessagePool  = cbMessagePool
  member val CbMessageQueue = cbMessageQueue
  member val Logger         = logger
  member val StartTime      = startTime
  member val BeesConfig     = beesConfig

  member this.PaStream    with get()     = paStream // filled in after construction (chicken or egg)
                          and  set value = paStream <- value
  member this.WithEcho    with get()     = getWithEcho()
                          and  set value = Volatile.Write(&withEcho, value)
  member this.WithLogging with get()     = getWithLogging()
                          and  set value = Volatile.Write(&withLogging, value)

  member this.Start() = start()
  member this.Stop () = stop ()
  // Called from the PortAudio callback at interrupt time; internal use.
  member this.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) =
    callback           input  output  frameCount  timeInfo  statusFlags  userDataPtr
    // PortAudioSharp.StreamCallbackResult.Continue

  /// Create a stream of samples starting at a past DateTime.
  /// The stream is exhausted when it gets to the end of buffered data.
  /// The recipient is responsible for separating out channels from the sequence.
  // member this.Get(dateTime: DateTime, worker: Worker)  : SampleType seq option = seq {
  //    let segIndex = segOfDateTime dateTime
  //    match seg with
  //    | None: return! None
  //    | Some seg :
  //    if isInSegOld dateTime then
  //    WIP
  //      
  // }

  interface IDisposable with
    member this.Dispose() =
      this.Stop()
      // Explicitly release any other managed resources here if needed

