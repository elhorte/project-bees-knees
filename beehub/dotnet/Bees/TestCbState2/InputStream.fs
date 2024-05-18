module TestCbState.InputStream

open System
open System.Runtime.InteropServices
open System.Threading

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.SubscriberList
open BeesUtil.PortAudioUtils
open BeesUtil.CallbackHandoff
open BeesLib.BeesConfig
open BeesLib.CbMessagePool


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
  | Success of _DateTime


/// <summary>Make the pool of CbMessages used by the stream callback</summary>
// let makeCbMessagePool beesConfig nRingFrames =
//   let startCount = Environment.ProcessorCount * 4    // many more than number of cores
//   let minCount   = 4
//   CbMessagePool.makeCbMessagePool startCount minCount beesConfig nRingFrames


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream


type CbState = {
  // callback args
  mutable Input           : IntPtr
  mutable Output          : IntPtr
  mutable FrameCount      : uint32
  mutable TimeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags     : PortAudioSharp.StreamCallbackFlags
  // callback result
  mutable SegCur          : Seg
  mutable SegOld          : Seg
  mutable SeqNum          : uint64
  mutable InputRingCopy   : IntPtr // where input was copied to
  mutable TimeStamp       : _DateTime
  // more stuff
  mutable IsInCallback    : bool
  mutable NRingFrames     : int
  mutable NUsableFrames   : int
  mutable NGapFrames      : int
  mutable CallbackHandoff : CallbackHandoff
  mutable WithEcho        : bool
  mutable WithLogging     : bool
  TimeInfoBase            : _DateTime
  FrameSize               : int // from PortAudioSharp TBD
  RingPtr                 : IntPtr
  Logger                  : Logger
  DebugSimulating         : bool } with
    
  member this.SegOldest = if this.SegOld.Active then this.SegOld else this.SegCur


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Putting data from the callback into the ring

let exchangeSegs cbState nFrames =
  let (cbs: CbState) = cbState
  if cbs.SegOld.NFrames < nFrames then
    // callback frameCount has increased and there is some leftover.
    cbs.SegOld.Reset() 
  assert not cbs.SegOld.Active
  let tmp = cbs.SegCur  in  cbs.SegCur <- cbs.SegOld  ;  cbs.SegOld <- tmp
  // if this.segCur.Head <> 0 then  Console.WriteLine "head != 0"
  // assert (this.segCur.Head = 0)
  cbs.SegCur.HeadTime <- tbdDateTime

// In case the callback’s nFrames arg varies from one callback to the next,
// adjust nGapFrames for the maximum nFrames arg seen.
// The goal is plenty of room, i.e. time, between cbSegCur.Head and cbSegOld.Tail.
// Code assumes that nRingFrames > 2 * nGapFrames
let adjustNGapFrames cbState nFrames =
  let (cbs: CbState) = cbState
  let gapCandidate = nFrames * 4 // if simulatingCallbacks then nFrames else nFrames * 4
  let nGapNew    = max cbs.NGapFrames gapCandidate
  let nUsableNew = nFrames * (cbs.NRingFrames / nFrames)
  if (cbs.NUsableFrames < nUsableNew  ||  cbs.NGapFrames < nGapNew)  &&  cbs.DebugSimulating then
    Console.WriteLine $"adjusted %d{cbs.NUsableFrames} to %d{nUsableNew}  gap %d{cbs.NGapFrames}"
  if nUsableNew < nGapNew then
    failwith $"nRingFrames is too small. nFrames: {nFrames}  nGapFrames: {cbs.NGapFrames}  nRingFrames: {cbs.NRingFrames}"
  cbs.NGapFrames    <- nGapNew
  cbs.NUsableFrames <- nUsableNew

let printCurAndOld cbState msg = ()
  // let (cbs: CbState) = cbState
  // let sCur = cbs.segCur.Print "cur"
  // let sOld = cbs.segOld.Print "old"
  // Console.WriteLine $"%s{sCur} %s{sOld} %s{msg}"
  

let prepSegs cbState nFrames =
  let (cbs: CbState) = cbState
  printCurAndOld cbs ""
  let nextHead = cbs.SegCur.Head + nFrames
  if nextHead <= cbs.NUsableFrames then
    // The block will fit after is.segCur.Head
    // state is Empty, AtBegin, Middle, Chasing
    let maxNonGapFrames = cbs.NUsableFrames - cbs.NGapFrames
    cbs.SegCur.Tail <- max cbs.SegCur.Tail (nextHead - maxNonGapFrames)
    if cbs.SegOld.Active then
      // state is Chasing
      // is.segOld is active and ahead of us.
      assert (cbs.SegCur.Head < cbs.SegOld.Tail)
      if cbs.SegOld.NFrames > nFrames then
        cbs.SegOld.Tail <- cbs.SegOld.Tail + nFrames
        // state is Chasing
      else
        cbs.SegOld.Reset()
        // state is AtBegin
      // state is AtBegin, Chasing
  else
    // state is Middle
    // The block will not fit at the is.segCur.Head.
    exchangeSegs   cbs nFrames
    printCurAndOld cbs "exchanged"
    assert (cbs.SegCur.Head = 0)
    // is.segCur starts fresh with head = 0, tail = 0, and we trim away is.segOld.Tail to ensure the gap.
    cbs.SegOld.Tail <- nFrames + cbs.NGapFrames
    // state is Chasing

let inputBufferAdcTimeOf cbState =
  let (cbs: CbState) = cbState
  cbs.TimeInfoBase + _TimeSpan.FromSeconds cbs.TimeInfo.inputBufferAdcTime
  
let indexToVoidptr cbState index  : voidptr =
  let (cbs: CbState) = cbState
  let indexByteOffset = index * cbs.FrameSize
  let intPtr = cbs.RingPtr + (IntPtr indexByteOffset)
  intPtr.ToPointer()

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Getting data from the ring – not at interrupt time

let handOff cbState =
  let (cbs: CbState) = cbState
  cbs.CallbackHandoff.HandOff()
 
let callback input output frameCount timeInfo statusFlags userDataPtr =
  Console.Write "."
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let cbs = handle.Target :?> CbState
  Volatile.Write(&cbs.IsInCallback, true)

  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  cbs.SeqNum       <- cbs.SeqNum + 1UL

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
// //   let nFrames = int frameCount
// //   adjustNGapFrames cbs nFrames
// //   prepSegs         cbs nFrames // may update is.segCur.Head, used by copyToRing()
// // //is.Logger.Add is.seqNum is.timeStamp "cb bufs=" is.cbMessagePool.PoolStats
// //   do
// //     // Copy the data then Submit a FinshCallback job.
// //     // Copy from callback data to the head of the ring and return a pointer to the copy.
// //     let srcPtr = input.ToPointer()
// //     let dstPtr = indexToVoidptr cbs cbs.segCur.Head
// //     let size   = int64 (nFrames * cbs.frameSize)
// //     Buffer.MemoryCopy(srcPtr, dstPtr, size, size)
// //     cbs.inputRingCopy <- IntPtr dstPtr
// //     let timeHead = inputBufferAdcTimeOf cbs
// //     cbs.segCur.AdvanceHead nFrames timeHead
  handOff cbs
  Volatile.Write(&cbs.IsInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue

// let cbAtomically cbState f =
//   let (cbs: CbState) = cbState
//   let rec spin() =
//     if Volatile.Read &cbs.isInCallback then spin()
//     f cbs // Copy out the stuff needed from cbState.
//     if Volatile.Read &cbs.isInCallback then spin()
//   spin()
  

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// initPortAudio() must be called before this.
type InputStream(beesConfig       : BeesConfig       ,
                 inputParameters  : StreamParameters ,
                 outputParameters : StreamParameters ,
                 withEcho         : bool             ,
                 withLogging      : bool             ) =

  let startTime         = _DateTime.Now
  let ringDuration      = _TimeSpan.FromMilliseconds(200) // beesConfig.InputStreamBufferDuration
  let gapDuration       = _TimeSpan.FromMilliseconds 10   // beesConfig.InputStreamGapDuration
  let nRingFrames       = if BeesLib.DebugGlobals.simulatingCallbacks then 37 else durationToNFrames beesConfig.InFrameRate ringDuration
  let nUsableRingFrames = 0 // calculated later
  let frameSize         = beesConfig.FrameSize
  let nRingBytes        = int nRingFrames * frameSize
  let nGapFrames        = if BeesLib.DebugGlobals.simulatingCallbacks then 2 else durationToNFrames beesConfig.InFrameRate gapDuration 

  // When unmanaged code calls managed code (e.g., a callback from unmanaged to managed),
  // the CLR ensures that the garbage collector will not move referenced managed objects
  // in memory during the execution of that managed code.
  // This happens automatically and does not require manual pinning.
  
  let cbState = {
    Input           = IntPtr.Zero
    Output          = IntPtr.Zero
    FrameCount      = 0u
    TimeInfo        = dummyInstance<PortAudioSharp.StreamCallbackTimeInfo>()
    StatusFlags     = dummyInstance<PortAudioSharp.StreamCallbackFlags>()
    SegCur          = Seg.NewEmpty nRingFrames beesConfig.InFrameRate
    SegOld          = Seg.NewEmpty nRingFrames beesConfig.InFrameRate
    SeqNum          = 0UL
    InputRingCopy   = IntPtr.Zero
    TimeStamp       = _DateTime.MaxValue // placeholder
    IsInCallback    = false
    NRingFrames     = nRingFrames
    NUsableFrames   = nUsableRingFrames
    NGapFrames      = nGapFrames
    CallbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
    WithEcho        = withEcho
    WithLogging     = withLogging   
    TimeInfoBase    = _DateTime.Now  // timeInfoBase + cbState.timeInfo -> cbState.TimeStamp. should come from PortAudioSharp TBD
    FrameSize       = frameSize
    RingPtr         = Marshal.AllocHGlobal(nRingBytes)
    Logger          = Logger(8000, startTime)
    DebugSimulating = false  }

  // let cbMessageWorkList = SubscriberList<CbMessage>()
  // let cbMessagePool     = makeCbMessagePool beesConfig nRingFrames
  // let cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
  // let poolItemCurrent   = PoolItem.New cbMessagePool cbMessageCurrent

  let debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    // let (cbMessage: CbMessage) = cbMessage
    // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
    // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
    // printCallback cbMessage

  let paStream =
    if cbState.DebugSimulating then
      None
    else
      let callbackStub = PortAudioSharp.Stream.Callback(
        // The intermediate lambda here is required to avoid a compiler error.
        fun        input output frameCount timeInfo statusFlags userDataPtr ->
          callback input output frameCount timeInfo statusFlags userDataPtr )
      Some (paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                   outParams       = Nullable<_>(outputParameters)        ,
                                                                   sampleRate      = beesConfig.InFrameRate               ,
                                                                   framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                   streamFlags     = StreamFlags.ClipOff                  ,
                                                                   callback        = callbackStub                         ,
                                                                   userData        = cbState                              ) ) )

  let paStream =
    match paStream with
    | None   -> dummyInstance<PortAudioSharp.Stream>()
    | Some p -> p
  let cbState           = cbState
  let timeStamp         = _DateTime.Now
  // let cbMessagePool     = cbMessagePool
  // let cbMessageWorkList = SubscriberList<CbMessage>()
  // let cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
  // let poolItemCurrent   = poolItemCurrent
  let debugMaxCallbacks = Int32.MaxValue
  let debugSubscription = dummyInstance<Subscription<CbMessage>>()
  
  
  member  this.echoEnabled   () = Volatile.Read &cbState.WithEcho
  member  this.loggingEnabled() = Volatile.Read &cbState.WithEcho

  member this.PaStream          = paStream
  member this.CbState           = cbState
  member val  CbStateLatest     = cbState            with get, set
  member this.TimeStamp         = timeStamp
  member this.BeesConfig        = beesConfig       
  member this.RingDuration      = ringDuration     
  member this.NRingBytes        = nRingBytes       
  member this.GapDuration       = gapDuration      
  // member this.CbMessagePool     = cbMessagePool    
  // member this.CbMessageWorkList = cbMessageWorkList
//member this.CbMessageCurrent  = cbMessageCurrent 
  // member this.PoolItemCurrent   = poolItemCurrent  
  member this.DebugMaxCallbacks = debugMaxCallbacks
  member this.DebugSubscription = debugSubscription

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
  // member this.printCallback (m: CbMessage) =
  //   let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
  //   let percentCPU   = this.PaStream.CpuLoad * 100.0
  //   let sDebug = sprintf "%3d: %A %s" this.CbState.seqNum this.CbState.timeStamp.TimeOfDay (this.cbMessagePool.PoolStats)
  //   let sWork  = sprintf $"microsec: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
  //   Console.WriteLine($"{sDebug}   ––   {sWork}")

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Subscribing to notifications of data added to the ring
  
  // returns = 0 on the last callback, > 0 after the last callback
  member private is.debugExcessOfCallbacks() = is.CbState.SeqNum - uint64 is.DebugMaxCallbacks

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    // let (cbMessage: CbMessage) = cbMessage
    // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
    // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
    // printCallback cbMessage
  
  member is.timeTail() = is.CbStateLatest.SegOldest.TailTime
  member is.timeHead() = is.CbStateLatest.SegCur   .HeadTime
 

  
  // let (|TooEarly|SegCur|SegOld|)  (dateTime: _DateTime) (duration: _TimeSpan) =
    
    
  
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
  // let get (dateTime: _DateTime) (duration: _TimeSpan) (worker: Worker) =
  //   let now = _DateTime.Now
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
    

  // let keep (duration: _TimeSpan) =
    // assert (duration > _TimeSpan.Zero)
    // let now = _DateTime.Now
    // let dateTime = now - duration
    // timeTail <- 
    //   if dateTime < timeTail then  timeTail
    //                          else  dateTime
    // timeTail
    
  member private is.offsetOfDateTime (dateTime: _DateTime)  : Option<Seg * int> =
    if not (is.timeTail() <= dateTime && dateTime <= is.timeHead()) then Some (is.CbStateLatest.SegCur, 1)
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
  
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Start())
    printfn $"InputStream size: {this.NRingBytes / 1_000_000} MB for {this.RingDuration}"
    printfn $"InputStream nFrames: {this.CbState.NRingFrames}"

  member is.Stop() =
    is.CbState.CallbackHandoff.Stop() 
    if is.CbState.DebugSimulating then ()
    is.PaStream.Stop()

  member this.AfterCallback() =
    Console.Write "–"
    

  /// Create a stream of samples starting at a past _DateTime.
  /// The stream is exhausted when it gets to the end of buffered data.
  /// The recipient is responsible for separating out channels from the sequence.
  // member this.Get(dateTime: _DateTime, worker: Worker)  : SampleType seq option = seq {
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

