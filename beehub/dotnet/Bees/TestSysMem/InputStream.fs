module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.ItemPool
open BeesUtil.WorkList
open BeesUtil.PortAudioUtils
open BeesUtil.CallbackHandoff
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.DebugGlobals


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
//    cbSegCur  cbMessageCurrent.SegCur.Head is overall head of data
//    cbSegOld  cbMessageCurrent.SegOld.Tail is overall tail of data
// 
// A background task loop takes each job from jobQueue and runs it to completion.
// Each callback    queues a job to copy cbSegCur/cbSegOld to segCur/segOld
// Each client call queues a job to access data from the ring.
// Client calls have to be asynchronous because they have to run in the jobQueue task.


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  
type InputGetResult =
  | Error   of string
  | Success of DateTime


/// <summary>Make the pool of CbMessages used by the stream callback</summary>
let makeCbMessagePool beesConfig nRingFrames =
  let startCount = Environment.ProcessorCount * 4    // many more than number of cores
  let minCount   = 4
  CbMessagePool.makeCbMessagePool startCount minCount beesConfig nRingFrames


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream


type CbState = {
  // callback args
  mutable input           : IntPtr
  mutable output          : IntPtr
  mutable frameCount      : uint32
  mutable timeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable statusFlags     : PortAudioSharp.StreamCallbackFlags
  // more stuff
  mutable withEcho        : bool
  mutable segCur          : Seg
  mutable segOld          : Seg
  mutable seqNum          : uint64
  mutable inputRingCopy   : IntPtr
  mutable nRingFrames     : int
  mutable nUsableFrames   : int
  mutable nGapFrames      : int
  mutable isInCallback    : bool
  mutable handoff         : TaskCompletionSource option 
  timeInfoBase            : DateTime // from PortAudioSharp TBD
  frameSize               : int
  ringPtr                 : IntPtr
  debugSimulating         : bool }

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Putting data from the callback into the ring

let exchangeSegs cbState nFrames =
  let (cbs: CbState) = cbState
  if cbs.segOld.NFrames < nFrames then
    // callback frameCount has increased and there is some leftover.
    cbs.segOld.Reset() 
  assert not cbs.segOld.Active
  let tmp = cbs.segCur  in  cbs.segCur <- cbs.segOld  ;  cbs.segOld <- tmp
  // if this.segCur.Head <> 0 then  Console.WriteLine "head != 0"
  // assert (this.segCur.Head = 0)
  cbs.segCur.TimeHead <- tbdDateTime

// In case the callback’s nFrames arg varies from one callback to the next,
// adjust nGapFrames for the maximum nFrames arg seen.
// The goal is plenty of room, i.e. time, between cbSegCur.Head and cbSegOld.Tail.
// Code assumes that nRingFrames > 2 * nGapFrames
let adjustNGapFrames cbState nFrames =
  let (cbs: CbState) = cbState
  let gapCandidate = if simulatingCallbacks then nFrames else nFrames * 4
  let nGapNew    = max cbs.nGapFrames gapCandidate
  let nUsableNew = nFrames * (cbs.nRingFrames / nFrames)
  if (cbs.nUsableFrames < nUsableNew  ||  cbs.nGapFrames < nGapNew)  &&  cbs.debugSimulating then
    Console.WriteLine $"adjusted %d{cbs.nUsableFrames} to %d{nUsableNew}  gap %d{cbs.nGapFrames}"
  if nUsableNew < nGapNew then
    failwith $"nRingFrames is too small. nFrames: {nFrames}  nGapFrames: {cbs.nGapFrames}  nRingFrames: {cbs.nRingFrames}"
  cbs.nGapFrames    <- nGapNew
  cbs.nUsableFrames <- nUsableNew

let printCurAndOld cbState msg =
  let (cbs: CbState) = cbState
  let sCur = cbs.segCur.Print "cur"
  let sOld = cbs.segOld.Print "old"
  Console.WriteLine $"%s{sCur} %s{sOld} %s{msg}"
  

let prepSegs cbState nFrames =
  let (cbs: CbState) = cbState
  printCurAndOld cbs ""
  let nextHead = cbs.segCur.Head + nFrames
  if nextHead <= cbs.nUsableFrames then
    // The block will fit after is.segCur.Head
    // state is Empty, AtBegin, Middle, Chasing
    let maxNonGapFrames = cbs.nUsableFrames - cbs.nGapFrames
    cbs.segCur.Tail <- max cbs.segCur.Tail (nextHead - maxNonGapFrames)
    if cbs.segOld.Active then
      // state is Chasing
      // is.segOld is active and ahead of us.
      assert (cbs.segCur.Head < cbs.segOld.Tail)
      cbs.segOld.TrimTail nFrames  // may result in is.segOld being inactive
      // state is AtBegin, Chasing
  else
    // state is Middle
    // The block will not fit at the is.segCur.Head.
    exchangeSegs   cbs nFrames
    printCurAndOld cbs "exchanged"
    assert (cbs.segCur.Head = 0)
    // is.segCur starts fresh with head = 0, tail = 0, and we trim away is.segOld.Tail to ensure the gap.
    cbs.segOld.Tail <- nFrames + cbs.nGapFrames
    // state is Chasing

let inputBufferAdcTimeOf cbState =
  let (cbs: CbState) = cbState
  cbs.timeInfoBase + TimeSpan.FromSeconds cbs.timeInfo.inputBufferAdcTime
  
let indexToVoidptr cbState index  : voidptr =
  let (cbs: CbState) = cbState
  let indexByteOffset = index * cbs.frameSize
  let intPtr = cbs.ringPtr + (IntPtr indexByteOffset)
  intPtr.ToPointer()

let handOff cbState =
  let (cbs: CbState) = cbState
  match cbs.handoff with
  | Some tcs -> tcs.SetResult ()
  | None     -> Console.WriteLine("Callback handoff missed!")
  
let callback input output frameCount timeInfo statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let cbs = handle.Target :?> CbState
  Volatile.Write(&cbs.isInCallback, true)

  cbs.input        <- input
  cbs.output       <- output
  cbs.frameCount   <- frameCount
  cbs.timeInfo     <- timeInfo
  cbs.statusFlags  <- statusFlags
  cbs.seqNum       <- cbs.seqNum + 1UL

  if cbs.withEcho then
    let size = uint64 (frameCount * uint32 cbs.frameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
  let nFrames = int frameCount
  adjustNGapFrames cbs nFrames
  prepSegs         cbs nFrames // may update is.segCur.Head, used by copyToRing()
//is.Logger.Add is.seqNum is.timeStamp "cb bufs=" is.cbMessagePool.PoolStats
  do
    // Copy the data then Submit a FinshCallback job.
    // Copy from callback data to the head of the ring and return a pointer to the copy.
    let srcPtr = input.ToPointer()
    let dstPtr = indexToVoidptr cbs cbs.segCur.Head
    let size   = int64 (nFrames * cbs.frameSize)
    Buffer.MemoryCopy(srcPtr, dstPtr, size, size)
    cbs.inputRingCopy <- IntPtr dstPtr
    let timeHead = inputBufferAdcTimeOf cbs
    cbs.segCur.AdvanceHead nFrames timeHead
//Console.Write(".")
  handOff cbs
  Volatile.Write(&cbs.isInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue

let cbAtomically cbState f =
  let (cbs: CbState) = cbState
  let rec spin() =
    if Volatile.Read &cbs.isInCallback then spin()
    f cbs // Copy out the stuff needed from cbState.
    if Volatile.Read &cbs.isInCallback then spin()
  spin()
  

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

type InputStream = {
  cbState                   : CbState
  Logger                    : Logger
  mutable paStream          : PortAudioSharp.Stream
  mutable timeStamp         : DateTime
  mutable withLogging       : bool
  mutable beesConfig        : BeesConfig // so it’s visible in the debugger
  ringDuration              : TimeSpan
  nRingBytes                : int
  gapDuration               : TimeSpan
  cbMessagePool             : CbMessagePool
  cbMessageWorkList         : WorkList<CbMessage>
  mutable cbMessageCurrent  : CbMessage
  mutable poolItemCurrent   : PoolItem<CbMessage>
  mutable callbackHandoff   : CallbackHandoff
  BeesConfig                : BeesConfig
  debugMaxCallbacks         : int32
  mutable debugSubscription : Subscription<CbMessage>
  mutable debugData         : string list  } with
  
  // initPortAudio() must be called before this.
  static member New( beesConfig       : BeesConfig       )
                   ( inputParameters  : StreamParameters )
                   ( outputParameters : StreamParameters )
                   ( withEcho         : bool             )
                   ( withLogging      : bool             ) =

    let ringDuration      = TimeSpan.FromMilliseconds(200) // beesConfig.InputStreamBufferDuration
    let gapDuration       = TimeSpan.FromMilliseconds 10   // beesConfig.InputStreamGapDuration
    let nRingFrames       = if DebugGlobals.simulatingCallbacks then 37 else durationToNFrames beesConfig.InSampleRate ringDuration
    let nUsableRingFrames = 0 // calculated later
    let frameSize         = beesConfig.FrameSize
    let nRingBytes        = int nRingFrames * frameSize
    let nGapFrames        = if DebugGlobals.simulatingCallbacks then 2 else durationToNFrames beesConfig.InSampleRate gapDuration 

    let cbState = {
      input           = IntPtr.Zero
      output          = IntPtr.Zero
      frameCount      = 0u
      timeInfo        = dummyInstance<PortAudioSharp.StreamCallbackTimeInfo>()
      statusFlags     = dummyInstance<PortAudioSharp.StreamCallbackFlags>()
      withEcho        = false
      segCur          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
      segOld          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
      seqNum          = 0UL
      inputRingCopy   = IntPtr.Zero
      nRingFrames     = nRingFrames
      nUsableFrames   = nUsableRingFrames
      nGapFrames      = nGapFrames
      isInCallback = false
      timeInfoBase = DateTime.Now // probably wrong
      frameSize       = frameSize
      ringPtr         = Marshal.AllocHGlobal(nRingBytes)
      debugSimulating = false }
    let cbStateHandle = GCHandle.Alloc(cbState, GCHandleType.Pinned)
    cbStateHandle.Free()

    let startTime         = DateTime.Now
    let cbMessageWorkList = WorkList<CbMessage>()
    let cbMessagePool     = makeCbMessagePool beesConfig nRingFrames
    let cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
    let poolItemCurrent   = PoolItem.New cbMessagePool cbMessageCurrent

    let is = {
      cbState           = cbState
      Logger            = Logger(8000, startTime)
      paStream          = dummyInstance<PortAudioSharp.Stream>()
      timeStamp         = DateTime.Now
      withLogging       = withLogging   
      beesConfig        = beesConfig // so it’s visible in the debugger
      ringDuration      = ringDuration
      nRingBytes        = nRingBytes
      gapDuration       = TimeSpan.FromMilliseconds 10
      cbMessagePool     = cbMessagePool
      cbMessageWorkList = WorkList<CbMessage>()
      cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
      poolItemCurrent   = poolItemCurrent
      callbackHandoff   = CallbackHandoff.New (fun () -> ())
      BeesConfig        = beesConfig
      debugMaxCallbacks = Int32.MaxValue
      debugSubscription = dummyInstance<Subscription<CbMessage>>()
      debugData         = ["a"] }
    let inputStreamHandle = GCHandle.Alloc(cbState, GCHandleType.Pinned)
    inputStreamHandle.Free()
    
    let debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
      Console.Write ","
      // let (cbMessage: CbMessage) = cbMessage
      // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
      // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
      // printCallback cbMessage

    is.debugSubscription <- cbMessageWorkList.Subscribe debuggingSubscriber 
    is.callbackHandoff   <- CallbackHandoff.New is.afterCallback

    if is.cbState.debugSimulating then is else 

    let callbackStub = PortAudioSharp.Stream.Callback(
      // The intermediate lambda here is required to avoid a compiler error.
      fun        input output frameCount timeInfo statusFlags userDataPtr ->
        callback input output frameCount timeInfo statusFlags userDataPtr )
    is.paStream <- paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                          outParams       = Nullable<_>(outputParameters)        ,
                                                                          sampleRate      = beesConfig.InSampleRate              ,
                                                                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                          streamFlags     = StreamFlags.ClipOff                  ,
                                                                          callback        = callbackStub                         ,
                                                                          userData        = cbState                              ) )
    is
  
  member  is.echoEnabled   () = Volatile.Read &is.cbState.withEcho
  member  is.loggingEnabled() = Volatile.Read &is.cbState.withEcho


  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // CbMessageQueue

  // /// <summary>
  // ///   Creates and starts a CbMessageQueue that will process CbMessages inserted by callbacks.
  // /// </summary>
  // /// <param name="workPerCallback">A function that processes a CbMessageQueueMessage</param>
  // /// <returns>Returns a started CbMessageQueue</returns>
  // let makeAndStartCbMessageQueue workPerCallback  : CbMessageQueue =
  //   let cbMessageQueueHandler workPerCallback (cbMessageQueue: CbMessageQueue) =
  //   //let mutable callbackMessage = Unchecked.defaultof<CbMessage>
  //     let doOne (m: CbMessage) =
  //       cbMessagePool.ItemUseBegin()
  //       workPerCallback m
  //       cbMessagePool.ItemUseEnd   m
  //     cbMessageQueue.iter doOne
  //   let cbMessageQueue = CbMessageQueue()
  //   let handler() = cbMessageQueueHandler workPerCallback cbMessageQueue
  //   Task.Run handler |> ignore
  //   cbMessageQueue
  //
  // let cbMessageQueue = makeAndStartCbMessageQueue cbMessageWorkList.HandleEvent

  // for debug
  member is.printCallback (m: CbMessage) =
    let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
    let percentCPU   = is.paStream.CpuLoad * 100.0
    let sDebug = sprintf "%3d: %A %s" is.cbState.seqNum is.timeStamp.TimeOfDay (is.cbMessagePool.PoolStats)
    let sWork  = sprintf $"microsec: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
    Console.WriteLine($"{sDebug}   ––   {sWork}")

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Subscribing to notifications of data added to the ring
  
  // returns = 0 on the last callback, > 0 after the last callback
  member private is.debugExcessOfCallbacks() = is.cbState.seqNum - uint64 is.debugMaxCallbacks

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    // let (cbMessage: CbMessage) = cbMessage
    // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
    // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
    // printCallback cbMessage

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring – not at interrupt time
  
  member is.afterCallback() =
    Console.Write ","
    assert (is.cbState.debugSimulating || not is.cbState.isInCallback)
    is.cbMessagePool.ItemUseBegin()
    do
      let cbMessage = Volatile.Read(&is.cbMessageCurrent)
      is.cbMessageWorkList.Broadcast(cbMessage)
    is.cbMessagePool.ItemUseEnd is.poolItemCurrent
//  let cbMessage = callbackAcceptance.CbMessage
//  let nFrames = int cbMessage.FrameCount
//  let fromPtr = cbMessage.InputSamples.ToPointer()
//  let ringHeadPtr = indexToPointer cbMessage.SegCur.Head
//  copy fromPtr ringHeadPtr nFrames

  member private is.handOff() =
    // cbMessagePool.ItemUseEnd(cbMessageCurrent)
    is.callbackHandoff.HandOff()
  
  member is.timeTail() = is.cbMessageCurrent.SegOldest.TimeTail
  member is.timeHead() = is.cbMessageCurrent.SegCur   .TimeHead
 

  
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
  //   if timeStart + duration > now then  Error "insufficient buffered data"
  //   else
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
    
  member private is.offsetOfDateTime (dateTime: DateTime)  : Option<Seg * int> =
    if not (is.timeTail() <= dateTime && dateTime <= is.timeHead()) then Some (is.cbMessageCurrent.SegCur, 1)
    else None

 
  // member private is.take inputTake =
  //   let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
  //   let size = frameCountToByteCount inputTake.FrameCount 
  //   System.Buffer.BlockCopy(from, 0, buffer, index, size)
  //   advanceIndex inputTake.FrameCount
  //   inputTake.CompletionSource.SetResult()
  
  // Called from the PortAudio Callback method
  // Must not allocate memory because this is a system-level callback
  member private is.callbackOther input output frameCount timeInfo statusFlags userDataPtr =
    Console.Write(".")
    PortAudioSharp.StreamCallbackResult.Continue

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  
  member is.Start() =
    is.callbackHandoff.Start()
    if is.cbState.debugSimulating then ()
    else
    paTryCatchRethrow(fun() -> is.paStream.Start())
    printfn $"InputStream size: {is.nRingBytes / 1_000_000} MB for {is.ringDuration}"
    printfn $"InputStream nFrames: {is.cbState.nRingFrames}"

  member is.Stop() =
    is.callbackHandoff.Stop() 
    if is.cbState.debugSimulating then ()
    is.paStream.Stop()


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
// let makeInputStream beesConfig inputParameters outputParameters sampleRate withEcho withLogging  : InputStream =
//   initPortAudio()
//   let inputStream = new InputStream(beesConfig, withEcho, withLogging)
//   let callback = PortAudioSharp.Stream.Callback( // The fun has to be here because of a limitation of the compiler, apparently.
//     fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
//       // inputStream.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) )
//       Console.Write(".\007")
//       PortAudioSharp.StreamCallbackResult.Continue )
//   let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
//                                                                         outParams       = Nullable<_>(outputParameters)        ,
//                                                                         sampleRate      = sampleRate                           ,
//                                                                         framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
//                                                                         streamFlags     = StreamFlags.ClipOff                  ,
//                                                                         callback        = callback                             ,
//                                                                         userData        = Nullable()                           ) )
//   inputStream.PaStream <- paStream
//   paTryCatchRethrow(fun() -> inputStream.Start())
//   inputStream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

