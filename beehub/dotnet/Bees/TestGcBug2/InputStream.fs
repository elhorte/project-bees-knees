module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.ItemPool
open BeesUtil.SubscriberList
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

type InputStream = {
  startTime                 : DateTime
  Logger                    : Logger
  mutable paStream          : PortAudioSharp.Stream
  mutable timeStamp         : DateTime
  mutable seqNum            : uint64
  mutable withEcho          : bool
  mutable withLogging       : bool
  mutable beesConfig        : BeesConfig // so it’s visible in the debugger
  frameSize                 : int
  ringDuration              : TimeSpan
  nRingFrames               : int
  mutable nUsableRingFrames : int
  nRingBytes                : int
  ringPtr                   : IntPtr
  gapDuration               : TimeSpan
  mutable nGapFrames        : int
  cbMessagePool             : CbMessagePool
  cbMessageWorkList         : SubscriberList<CbMessage>
  mutable cbSegCur          : Seg
  mutable cbSegOld          : Seg
  mutable cbMessageCurrent  : CbMessage
  mutable poolItemCurrent   : PoolItem<CbMessage>
  mutable callbackHandoff   : CallbackHandoff
  BeesConfig                : BeesConfig
  debugMaxCallbacks         : uint64
  mutable debugSimulating   : bool
  mutable debugInCallback   : bool
  mutable debugSubscription : Subscription<CbMessage>
  mutable debugData         : string list  }

let echoEnabled    (is: InputStream) = Volatile.Read &is.withEcho
let loggingEnabled (is: InputStream) = Volatile.Read &is.withEcho

let indexToVoidptr (is: InputStream) index  : voidptr =
  let indexByteOffset = index * is.frameSize
  let intPtr = is.ringPtr + (IntPtr indexByteOffset)
  intPtr.ToPointer()


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
let printCallback (is: InputStream) (m: CbMessage) =
  let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
  let percentCPU   = is.paStream.CpuLoad * 100.0
  let sDebug = sprintf "%3d: %A %s" is.seqNum is.timeStamp.TimeOfDay (is.cbMessagePool.PoolStats)
  let sWork  = sprintf $"microsec: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
  Console.WriteLine($"{sDebug}   ––   {sWork}")

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Subscribing to notifications of data added to the ring

// returns = 0 on the last callback, > 0 after the last callback
let debugExcessOfCallbacks (is: InputStream) = is.seqNum - is.debugMaxCallbacks

let debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
  Console.Write ","
  // let (cbMessage: CbMessage) = cbMessage
  // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
  // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
  // printCallback cbMessage

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Getting data from the ring – not at interrupt time

let afterCallback (is: InputStream) =
  Console.Write ","
  assert (is.debugSimulating || not is.debugInCallback)
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

let handOff (is: InputStream) =
  // cbMessagePool.ItemUseEnd(cbMessageCurrent)
  is.callbackHandoff.HandOff()

let timeTail (is: InputStream) = is.cbMessageCurrent.SegOldest.TimeTail
let timeHead (is: InputStream) = is.cbMessageCurrent.SegCur   .TimeHead



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
  
let locationOfDateTime (is: InputStream) (dateTime: DateTime)  : Option<Seg * int> =
  if not (timeTail is <= dateTime && dateTime <= timeHead is) then Some (is.cbMessageCurrent.SegCur, 1)
  else None


// let take (is: InputStream) inputTake =
//   let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
//   let size = frameCountToByteCount inputTake.FrameCount 
//   System.Buffer.BlockCopy(from, 0, buffer, index, size)
//   advanceIndex inputTake.FrameCount
//   inputTake.CompletionSource.SetResult()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Putting data from the callback into the ring

let exchangeSegs (is:InputStream) nFrames =
  if is.cbSegOld.NFrames < nFrames then
    // callback frameCount has increased and there is some leftover.
    is.cbSegOld.Reset() 
  assert not is.cbSegOld.Active
  let tmp = is.cbSegCur  in  is.cbSegCur <- is.cbSegOld  ;  is.cbSegOld <- tmp
  // if is.cbSegCur.Head <> 0 then  Console.WriteLine "head != 0"
  // assert (is.cbSegCur.Head = 0)
  is.cbSegCur.TimeHead <- tbdDateTime

// In case the callback’s nFrames arg varies from one callback to the next,
// adjust nGapFrames for the maximum nFrames arg seen.
// The goal is plenty of room, i.e. time, between cbSegCur.Head and cbSegOld.Tail.
// Code assumes that nRingFrames > 2 * nGapFrames
let adjustNGapFrames (is: InputStream) nFrames =
  let gapCandidate = if simulatingCallbacks then nFrames else nFrames * 4
  let nGapNew    = max is.nGapFrames gapCandidate
  let nUsableNew = nFrames * (is.nRingFrames / nFrames)
  if (is.nUsableRingFrames < nUsableNew  ||  is.nGapFrames < nGapNew)  &&  is.debugSimulating then
    Console.WriteLine $"adjusted %d{is.nUsableRingFrames} to %d{nUsableNew}  gap %d{is.nGapFrames}"
  if nUsableNew < nGapNew then
    failwith $"nRingFrames is too small. nFrames: {nFrames}  nGapFrames: {is.nGapFrames}  nRingFrames: {is.nRingFrames}"
  is.nGapFrames        <- nGapNew
  is.nUsableRingFrames <- nUsableNew

let printCurAndOld (is: InputStream) msg =
  let sCur = is.cbSegCur.Print "cur"
  let sOld = is.cbSegOld.Print "old"
  Console.WriteLine $"%s{sCur} %s{sOld} %s{msg}"
  

let prepSegs (is: InputStream) nFrames =
  printCurAndOld is ""
  let nextHead = is.cbSegCur.Head + nFrames
  if nextHead <= is.nUsableRingFrames then
    // The block will fit after is.cbSegCur.Head
    // state is Empty, AtBegin, Middle, Chasing
    let maxNonGapFrames = is.nUsableRingFrames - is.nGapFrames
    is.cbSegCur.Tail <- max is.cbSegCur.Tail (nextHead - maxNonGapFrames)
    if is.cbSegOld.Active then
      // state is Chasing
      // is.cbSegOld is active and ahead of us.
      assert (is.cbSegCur.Head < is.cbSegOld.Tail)
      if is.cbSegOld.NFrames > nFrames then
        is.cbSegOld.Tail <- is.cbSegOld.Tail + nFrames
        // state is Chasing
      else
        is.cbSegOld.Reset()
        // state is AtBegin
      // state is AtBegin, Chasing
  else
    // state is Middle
    // The block will not fit at the is.cbSegCur.Head.
    exchangeSegs is nFrames
    printCurAndOld is "exchanged"
    assert (is.cbSegCur.Head = 0)
    // is.cbSegCur starts fresh with head = 0, tail = 0, and we trim away is.cbSegOld.Tail to ensure the gap.
    is.cbSegOld.Tail <- nFrames + is.nGapFrames
    // state is Chasing

// Called from the PortAudio Callback method
// Must not allocate memory because this is a system-level callback
let callbackOther (is: InputStream) input output frameCount timeInfo statusFlags userDataPtr =
  Console.Write(".")
  PortAudioSharp.StreamCallbackResult.Continue

let callback input output frameCount timeInfo statusFlags userDataPtr =
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let is = handle.Target :?> InputStream
  Volatile.Write(&is.debugInCallback, true)
  // is.debugData <- "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"::is.debugData
  // Console.WriteLine $"data length %d{is.debugData.Length}"
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  is.timeStamp <- DateTime.Now
  is.seqNum    <- is.seqNum + 1UL
  if echoEnabled is then
    let size = uint64 (frameCount * uint32 is.frameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
  match is.cbMessagePool.Take() with
  | None ->
    is.Logger.Add is.seqNum is.timeStamp "cbMessagePool is empty" null
    Volatile.Write(&is.debugInCallback, false)
    PortAudioSharp.StreamCallbackResult.Continue
  | Some item ->
  if debugExcessOfCallbacks is > 0UL then
    Volatile.Write(&is.debugInCallback, false)
    PortAudioSharp.StreamCallbackResult.Complete
  else
  let cbMessage = item.Data
  let nFrames   = int frameCount
  adjustNGapFrames is nFrames
  prepSegs is nFrames // may update is.cbSegCur.Head, used by copyToRing()
  is.Logger.Add is.seqNum is.timeStamp "cb bufs=" is.cbMessagePool.PoolStats
  do 
    // the callback args
    cbMessage.InputSamples <- input
    cbMessage.Output       <- output
    cbMessage.FrameCount   <- frameCount
    cbMessage.TimeInfo     <- timeInfo
    cbMessage.StatusFlags  <- statusFlags
    cbMessage.UserDataPtr  <- userDataPtr
    // more from the callback
    cbMessage.WithEcho     <- is.withEcho
    cbMessage.TimeStamp    <- is.timeStamp
    cbMessage.SeqNum       <- is.seqNum
  do
    // Copy the data then Submit a FinshCallback job.
    // Copy from callback data to the head of the ring and return a pointer to the copy.
    let srcPtr = input.ToPointer()
    let dstPtr = indexToVoidptr is is.cbSegCur.Head
    let size   = int64 (nFrames * is.frameSize)
    Buffer.MemoryCopy(srcPtr, dstPtr, size, size)
    cbMessage.InputSamplesRingCopy <- IntPtr dstPtr
    is.cbSegCur.AdvanceHead nFrames is.timeStamp
  do
    cbMessage.SegCur.Head <- is.cbSegCur.Head
    cbMessage.SegCur.Tail <- is.cbSegCur.Tail
    cbMessage.SegOld.Head <- is.cbSegOld.Head
    cbMessage.SegOld.Tail <- is.cbSegOld.Tail
    Volatile.Write(&is.cbMessageCurrent, cbMessage)
    Volatile.Write(&is.poolItemCurrent , item     )
//  Console.Write(".")
  handOff is
  Volatile.Write(&is.debugInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let start (is: InputStream) =
  is.callbackHandoff.Start()
  if is.debugSimulating then ()
  else
  paTryCatchRethrow(fun() -> is.paStream.Start())
  printfn $"InputStream size: {is.nRingBytes / 1_000_000} MB for {is.ringDuration}"
  printfn $"InputStream nFrames: {is.nRingFrames}"

let stop (is: InputStream) =
  is.callbackHandoff.Stop() 
  if is.debugSimulating then ()
  is.paStream.Stop()

// initPortAudio() must be called before this.
let newInputStream( beesConfig       : BeesConfig       )
                  ( inputParameters  : StreamParameters )
                  ( outputParameters : StreamParameters )
                  ( withEcho         : bool             )
                  ( withLogging      : bool             ) =

  let startTime         = DateTime.Now
  let ringDuration      = TimeSpan.FromMilliseconds(200) // beesConfig.RingBufferDuration
  let nRingFrames       = if DebugGlobals.simulatingCallbacks then 37 else durationToNFrames beesConfig.InSampleRate ringDuration
  let nUsableRingFrames = 0 // calculated later
  let frameSize         = beesConfig.FrameSize
  let nRingBytes        = int nRingFrames * frameSize
  let gapDuration       = TimeSpan.FromMilliseconds 10
  let cbMessageWorkList = SubscriberList<CbMessage>()
  let nGapFrames        = if DebugGlobals.simulatingCallbacks then 2 else durationToNFrames beesConfig.InSampleRate gapDuration 
  let cbMessagePool     = makeCbMessagePool beesConfig nRingFrames
  let cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
  let poolItemCurrent   = PoolItem .New cbMessagePool cbMessageCurrent
  
  let is = {
    startTime         = startTime
    Logger            = Logger(8000, startTime)
    paStream          = dummyInstance<PortAudioSharp.Stream>()
    timeStamp         = DateTime.Now
    seqNum            = 0UL
    withEcho          = withEcho
    withLogging       = withLogging   
    beesConfig        = beesConfig // so it’s visible in the debugger
    frameSize         = frameSize
    ringDuration      = ringDuration
    nRingFrames       = nRingFrames
    nUsableRingFrames = nUsableRingFrames
    nRingBytes        = nRingBytes
    ringPtr           = Marshal.AllocHGlobal(nRingBytes)
    gapDuration       = TimeSpan.FromMilliseconds 10
    nGapFrames        = nGapFrames
    cbMessagePool     = cbMessagePool
    cbMessageWorkList = SubscriberList<CbMessage>()
    cbMessageCurrent  = CbMessage.New cbMessagePool beesConfig nRingFrames
    poolItemCurrent   = poolItemCurrent
    cbSegCur          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
    cbSegOld          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
    callbackHandoff   = dummyInstance<CallbackHandoff>()
    BeesConfig        = beesConfig
    debugSimulating   = DebugGlobals.simulatingCallbacks
    debugInCallback   = false
    debugMaxCallbacks = UInt64.MaxValue
    debugSubscription = dummyInstance<Subscription<CbMessage>>()
    debugData         = ["a"] }

  is.callbackHandoff   <- CallbackHandoff.New (fun () -> afterCallback is)

  let debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    // let (cbMessage: CbMessage) = cbMessage
    // Console.WriteLine $"%4d{cbMessage.SegCur.Head}  %d{cbMessage.SeqNum}"
    // if debugExcessOfCallbacks cbMessage.SeqNum >= 0 then  Console.WriteLine $"No more callbacks – debugging"
    // printCallback cbMessage
  is.debugSubscription <- cbMessageWorkList.Subscribe debuggingSubscriber 
  
  if is.debugSimulating then is
  else 
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
                                                                          userData        = is                                   ) )
    is

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
//
// interface IDisposable with
//   member this.Dispose() =
//     System.Console.WriteLine("Disposing inputStream")
//     this.Stop()
//     // Explicitly release any other managed resources here if needed
//


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
