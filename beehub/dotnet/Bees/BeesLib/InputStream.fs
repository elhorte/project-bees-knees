module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesUtil.WorkList
open BeesUtil.PortAudioUtils


type Worker = Buf -> int -> int

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


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type TakeFunction =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type CallbackAcceptanceJob = {
  CbMessage        : CbMessage
  CompletionSource : TaskCompletionSource<unit> }

type TakeJob = {
  Data: TakeFunction
  CompletionSource: TaskCompletionSource<unit> }

type Job =
  | CallbackAcceptance of CallbackAcceptanceJob
  | Take               of TakeJob

  
type InputGetResult =
  | Error   of string
  | Success of DateTime

/// <summary>Make the pool of CbMessages used by the stream callback</summary>
let makeCbMessagePool beesConfig =
  let bufSize    = 1024
  let startCount = Environment.ProcessorCount * 4    // many more than number of cores
  let minCount   = 4
  CbMessagePool(bufSize, startCount, minCount, beesConfig)


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream class

type InputStream(beesConfig: BeesConfig, withEcho: bool, withLogging: bool) =
  let startTime = DateTime.Now
  let logger = Logger(8000, startTime)
  let cancellationTokenSource = new CancellationTokenSource()
  let jobQueue = AsyncConcurrentQueue<Job>()
  let cbMessageWorkList = WorkList<CbMessage>()
  let cbMessagePool: CbMessagePool = makeCbMessagePool beesConfig
  let mutable paStream = dummyInstance<PortAudioSharp.Stream>()
  let mutable timeStamp = DateTime.Now
  let mutable seqNum = 0
  let mutable withEcho = false
  let mutable withLogging = false
  let echoEnabled   () = Volatile.Read &withEcho
  let loggingEnabled() = Volatile.Read &withEcho

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

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // CbMessageQueue

  /// <summary>
  ///   Creates and starts a CbMessageQueue that will process CbMessages inserted by callbacks.
  /// </summary>
  /// <param name="workPerCallback">A function that processes a CbMessageQueueMessage</param>
  /// <returns>Returns a started CbMessageQueue</returns>
  let makeAndStartCbMessageQueue workPerCallback  : CbMessageQueue =
    let cbMessageQueueHandler workPerCallback (cbMessageQueue: CbMessageQueue) =
    //let mutable callbackMessage = Unchecked.defaultof<CbMessage>
      let doOne (m: CbMessage) =
        cbMessagePool.ItemUseBegin()
        workPerCallback m
        cbMessagePool.ItemUseEnd   m
      cbMessageQueue.iter doOne
    let cbMessageQueue = CbMessageQueue()
    let handler() = cbMessageQueueHandler workPerCallback cbMessageQueue
    Task.Run handler |> ignore
    cbMessageQueue

  let cbMessageQueue = makeAndStartCbMessageQueue cbMessageWorkList.HandleEvent

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Putting data from the callback into the ring

  let mutable cbSegCur = Seg(nRingFrames, beesConfig.InSampleRate)
  let mutable cbSegOld = Seg(nRingFrames, beesConfig.InSampleRate)

  let exchangeSegs() =
    assert not cbSegOld.Active
    let tmp = cbSegCur  in  cbSegCur <- cbSegOld  ;  cbSegOld <- tmp
    assert (cbSegCur.Head = 0)
    cbSegCur.TimeHead <- tbdDateTime

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
      // The block will fit after cbSegCur.Head
      // state is Empty, AtBegin, Middle, Chasing
      if cbSegOld.Active then
        // state is Chasing
        // cbSegOld is active and ahead of us.
        assert (cbSegCur.Head < cbSegOld.Tail)
        cbSegOld.TrimTail nFrames  // may result in cbSegOld being inactive
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
      // The block will not fit at the cbSegCur.Head.
      exchangeSegs()
      assert (cbSegCur.Head = 0)
      // cbSegCur starts fresh with head = 0, tail = 0, and we trim away cbSegOld.Tail to ensure the gap.
      cbSegOld.Tail <- nFrames + nGapFrames
      // state is Chasing
  
  let debugMaxNumberOfCallbacks = Int32.MaxValue
  // returns = 0 on the last callback, > 0 after the last callback
  let debugHitMaxNumberOfCallbacks n = n - debugMaxNumberOfCallbacks

  // Called from the PortAudio Callback method
  // Must not allocate memory because this is a system-level callback
  let callback input output frameCount timeInfo statusFlags userDataPtr =
    let (input : IntPtr) = input
    let (output: IntPtr) = output
    timeStamp <- DateTime.Now
    seqNum    <- seqNum + 1
    if echoEnabled() then
      let size = uint64 (frameCount * uint32 frameSize)
      Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
    match cbMessagePool.Take() with
    | None -> // Yikes, pool is empty
      logger.Add seqNum timeStamp "cbMessagePool is empty" null
      PortAudioSharp.StreamCallbackResult.Continue
    | Some cbMessage ->
    match cbMessagePool.CountAvail with
    | 0 -> PortAudioSharp.StreamCallbackResult.Complete // should continue?
    | _ when debugHitMaxNumberOfCallbacks seqNum > 0 ->
      PortAudioSharp.StreamCallbackResult.Complete
    | _ ->
    let fillCbMessage() =
      // the callback args
      cbMessage.InputSamples <- input
      cbMessage.Output       <- output
      cbMessage.FrameCount   <- frameCount
      cbMessage.TimeInfo     <- timeInfo
      cbMessage.StatusFlags  <- statusFlags
      cbMessage.UserDataPtr  <- userDataPtr
      // more from the callback
      cbMessage.WithEcho     <- withEcho
      cbMessage.TimeStamp    <- timeStamp
      cbMessage.SeqNum       <- seqNum
    let nFrames = int frameCount
    let copyFrames() =
      let writeCallbackBlockToRing() =
        // Copy from callback data to the head of the ring and return a pointer to the copy.
        let copyToRing()  : IntPtr =
          let fromPtr = input.ToPointer()
          let toPtr   = indexToVoidptr cbSegCur.Head
          let size    = int64 (nFrames * frameSize)
          paTryCatchRethrow (fun () -> Buffer.MemoryCopy(fromPtr, toPtr, size, size))
          IntPtr toPtr
        prepForNewFrames nFrames // may update cbSegCur.Head
        let ptr = copyToRing()
        cbSegCur.AdvanceHead nFrames timeStamp
        ptr
      // Copy the data then Submit a FinshCallback job.
      let ptrToTheCopy = writeCallbackBlockToRing()
      cbMessage.InputSamplesRingCopy <- ptrToTheCopy
    let finish() =
      let submitCallbackAcceptanceJob callbackAcceptanceJob =
        jobQueue.Enqueue(CallbackAcceptance callbackAcceptanceJob)
      cbMessage.SegCur <- cbSegCur.Copy()
      cbMessage.SegOld <- cbSegOld.Copy()
      let callbackAcceptanceJob = {
        CbMessage        = cbMessage
        CompletionSource = TaskCompletionSource<unit>() }
      submitCallbackAcceptanceJob callbackAcceptanceJob
      callbackAcceptanceJob.CompletionSource.SetResult()
    if loggingEnabled() then  logger.Add seqNum timeStamp "cb bufs=" cbMessagePool.PoolStats
    fillCbMessage()
    copyFrames   ()
    finish       ()
    PortAudioSharp.StreamCallbackResult.Continue

  // for debug
  let printCallback (m: CbMessage) =
    let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
    let percentCPU   = paStream.CpuLoad * 100.0
    let sDebug = sprintf "%3d: %A %s" seqNum timeStamp cbMessagePool.PoolStats
    let sWork  = sprintf $"work: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
    Console.WriteLine($"{sDebug}   ––   {sWork}")

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring – not at interrupt time
    
  // The most recent cbMessage
  let mutable cbMessage = dummyInstance<CbMessage>()
  let segOldest() = if cbMessage.SegOld.Active then cbMessage.SegOld else cbMessage.SegCur
  let timeTail() = segOldest()     .TimeTail
  let timeHead() = cbMessage.SegCur.TimeHead
  
  let handleCallbackAcceptance callbackAcceptance =
    cbMessagePool.ItemUseBegin()
    cbMessage <- callbackAcceptance.CbMessage
    Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
    if debugHitMaxNumberOfCallbacks cbMessage.SeqNum >= 0 then
      Console.WriteLine $"No more callbacks – debugging"
      printCallback cbMessage
    // ...
    cbMessagePool.ItemUseEnd(cbMessage)
//  let cbMessage = callbackAcceptance.CbMessage
//  let nFrames = int cbMessage.FrameCount
//  let fromPtr = cbMessage.InputSamples.ToPointer()
//  let ringHeadPtr = indexToPointer cbMessage.SegCur.Head
//  copy fromPtr ringHeadPtr nFrames
 
  
  // let (|TooEarly|SegCur|SegOld|)  (dateTime: DateTime) (duration: TimeSpan) =
    
    
  
  // let getSome timeStart count  : (int * int) seq = seq {
  //   if cbMessage.SegOld.Active then
  //     if timeStart >= segHead then
  //       // return empty sequence
  //     let timeOffset = timeStart - cbMessage.SegOld.TimeTail
  //     assert (timeOffset >= 0)
  //     let nFrames = cbMessage.SegOld.NFramesOf timeOffset
  //     let indexStart = cbMessage.SegOld.Tail + nFrames
  //     if indexStart < cbMessage.SegOld.Head then
  //       yield (indexStart, nFrames)
  //   if cbMessage.SegCur.Active then yield (cbMessage.SegCur.Tail, cbMessage.SegCur.NFrames)
  // }
    
  //   
  // let x = timeTail
  // let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
  //   let now = DateTime.Now
  //   let timeStart = max dateTime timeTail
  //   if timeStart + duration > now then  Error "insufficient buffered data" else
  //   let rec deliver timeStart nFrames =
  //     let nSamples = nFrames / frameSize
  //     let r = worker fromPtr nSamples
  //   let nextIndex = ringIndex timeStart
  //   let count = 
  //   deliver next timeStart
  //   Success timeStart
    

  // let keep (duration: TimeSpan) =
    // assert (duration > TimeSpan.Zero)
    // let now = DateTime.Now
    // let dateTime = now - duration
    // timeTail <- 
    //   if dateTime < timeTail then  timeTail
    //                          else  dateTime
    // timeTail
    
  let locationOfDateTime (dateTime: DateTime)  : Option<Seg * int> =
    if not (timeTail() <= dateTime && dateTime <= timeHead()) then Some (cbMessage.SegCur, 1)
    else None

 
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

   
  member val CbMessagePool  = cbMessagePool
  member val CbMessageQueue = cbMessageQueue
  member val Logger         = logger
  member val StartTime      = startTime
  member val BeesConfig     = beesConfig

  member this.PaStream    with get()     = paStream // filled in after construction (chicken or egg)
                          and  set value = paStream <- value
  member this.WithEcho    with get()     = echoEnabled()
                          and  set value = Volatile.Write(&withEcho, value)
  member this.WithLogging with get()     = loggingEnabled()
                          and  set value = Volatile.Write(&withLogging, value)

  member this.Start() = start()
  member this.Stop () = stop ()
  // Called from the PortAudio callback at interrupt time; internal use.
  member this.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) =
    paTryCatchRethrow(fun () ->
              callback input  output  frameCount  timeInfo  statusFlags  userDataPtr)
//  PortAudioSharp.StreamCallbackResult.Continue

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
      System.Console.WriteLine("Disposing inputStream")
      this.Stop()
      // Explicitly release any other managed resources here if needed


// See Theory of Operation comment before main at the end of this file.


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> CbMessageQueue handler

/// NEEDS WORK
/// Main does the following:
/// - Initialize PortAudio.
/// - Create everything the callback will need.
///   - sampleRate, inputParameters, outputParameters
///   - a CbMessageQueue, which
///     - accepts a CbMessage from each callback
///     - calls the given handler asap for each CbMessage queued
///   - a CbContext struct, which is passed to each callback
/// - runs the cbMessageQueue
/// The audio callback is designed to do as little as possible at interrupt time:
/// - grabs a CbMessage from a preallocated ItemPool
/// - copies the input data buf into the CbMessage
/// - inserts the CbMessage into in the CbMessageQueue for later processing

// <summary>
//   Creates a Stream.Callback that:
//   <list type="bullet">
//     <item><description> Allocates no memory because this is a system-level callback </description></item>
//     <item><description> Gets a <c>CbMessage</c> from the pool and fills it in        </description></item>
//     <item><description> Posts the <c>CbMessage</c> to the <c>cbMessageQueue</c>     </description></item>
//   </list>
// </summary>
// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
// <param name="cbMessageQueue" > The <c>CbMessageQueue</c> to post to           </param>
// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>

//–––––––––––––––––––––––––––––––––––––
// PortAudioSharp.Stream

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                               </param>
/// <param name="outputParameters"> Parameters for output audio stream                              </param>
/// <param name="sampleRate"      > Audio sample rate                                               </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output       </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging         </param>
/// <param name="cbMessageQueue"  > CbMessageQueue object handling audio stream                     </param>
/// <returns>An <c>InputStream</c></returns>
let makeInputStream beesConfig inputParameters outputParameters sampleRate withEcho withLogging  : InputStream =
  initPortAudio()
  let inputStream = new InputStream(beesConfig, withEcho, withLogging)
  let callback = PortAudioSharp.Stream.Callback( // The fun has to be here because of a limitation of the compiler, apparently.
    fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
      inputStream.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) )
  let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                        outParams       = Nullable<_>(outputParameters)        ,
                                                                        sampleRate      = sampleRate                           ,
                                                                        framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                        streamFlags     = StreamFlags.ClipOff                  ,
                                                                        callback        = callback                             ,
                                                                        userData        = Nullable()                           ) )
  inputStream.PaStream <- paStream
  paTryCatchRethrow(fun() -> inputStream.Start())
  inputStream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

