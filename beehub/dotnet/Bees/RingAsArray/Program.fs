
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesLib.CbMessagePool
open CSharpHelpers

let mutable simulatingCallbacks = false

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  if print then Console.Write "}"

let awaitForever() = delayMs false Int32.MaxValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let paTryCatch f (exit: Exception -> unit) =
  try
    f()
  with
  | :? PortAudioException as ex -> 
    Console.WriteLine $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    exit  ex
    raise ex
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    exit  ex
    raise ex

let paTryCatchRethrow f = paTryCatch f (fun e -> ()                 )

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type CallbackHandoff = {
  F            : unit -> unit
  Semaphore    : SemaphoreSlim
  Cts          : CancellationTokenSource
  mutable Task : Task option } with
 
  static member New f = {
    F         = f
    Semaphore = new SemaphoreSlim(0)
    Cts       = new CancellationTokenSource()
    Task      = None }

  member private ch.doHandoffs() =
    let loop() = 
      while not ch.Cts.Token.IsCancellationRequested do
        ch.Semaphore.WaitAsync().Wait()
        ch.F()
      ch.Semaphore.Dispose()
      ch.Cts      .Dispose()
      ch.Task <- None
    match ch.Task with
    | Some _ -> ()
    | None   -> ch.Task <- Some (Task.Run loop)

  member ch.Start   () = ch.doHandoffs()
  member ch.Stop    () = ch.Cts.Cancel()
  member ch.HandOff () = ch.Semaphore.Release() |> ignore

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// The ring buffer comprises two segments, of which 0, 1, or 2 are active.
//
// There is a gap between the segments so that locking is not required to prevent a race condition
// between the interrupt-time callback copying into the ring and a client copying out of the ring.

type State = // |––––––––––––– ring ––––––––––––––|                                                                               
  | Empty    // |               gap               |                                                                               
  | AtBegin  // | SegCur |          gap           | Gap is initially bigger than needed.
  | Moving   // | gapB |  SegCur  |     gapA      | SegCur has grown so much that SegCur.Tail is being trimmed.                  
  | AtEnd    // |      gapB     |  SegCur  | gapA | like Moving but gapA has become too small for more SegCur.Head growth.       
  | Chasing  // | SegCur | gapB |  SegOld  | gapA | As SegCur.Head grows, SegOld.Tail is being trimmed.                          

// Repeating lifecycle:  Empty –> AtBegin –> Moving –> AtEnd –> Chasing –> AtBegin ...
//
//      || time –>                  R               (R = repeat)         R                                    R
//      ||                          |                                    |                                    |
//      || Empty     | AtBegin      | Moving     | AtEnd | Chasing       | Moving     | AtEnd | Chasing       |
// seg0 || inactive  | cur growing  | cur moving         | old shrinking | inactive           | cur growing   |
// seg1 || inactive  | inactive     | inactive           | cur growing   | cur moving         | old shrinking |
//      ||                                               |
//                                                       X (exchange cur with old)
// There are two pairs of segments:
//
//     callback    afterCallback
//       time          time
//    ––––––––––  ––––––––––––––––––––––––––
//    cbs.SegCur  iS.SegCur.Head is overall head of data
//    cbs.SegOld  iS.SegOld.Tail is overall tail of data
// 
// A background task takes over after each callback

let stateIs(state: State, states: State[]) =
  ()

// Not a struct becuase it persists across calls to callback.
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
  mutable State           : State
  mutable IsInCallback    : bool
  mutable NRingFrames     : int
  mutable NDataFrames     : int
  mutable NGapFrames      : int
  mutable CallbackHandoff : CallbackHandoff
  mutable WithEcho        : bool
  mutable WithLogging     : bool
  TimeInfoBase            : _DateTime // for getting UTC from timeInfo.inputBufferAdcTime
  FrameSize               : int
  Ring                    : float32 array
  DebugSimulating         : bool } with
    
  member this.SegOldest = if this.SegOld.Active then this.SegOld else this.SegCur


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Copy data from the audio driver into our ring.

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let cbs = handle.Target :?> CbState
//Console.Write "."
  Volatile.Write(&cbs.IsInCallback, true)
  let nFrames = int frameCount
  let adcStartTime = cbs.TimeInfoBase + _TimeSpan.FromSeconds timeInfo.inputBufferAdcTime
  
  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  cbs.SeqNum       <- cbs.SeqNum + 1UL

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  do
    // Ensure that SegCur.Head is ready for the new data
    // and adjust the segs except for SegCur.Head,
    // which will be updated after copying the data to the ring.
    let mutable newHead = cbs.SegCur.Head + nFrames // provisional
    let mutable newTail = newHead - cbs.NDataFrames // provisional, can be negative
    let printCurAndOld msg =
      if not cbs.DebugSimulating then ()
      else
      let mutable dots = Array.init cbs.NRingFrames (fun i -> if i % 10 = 0 then char ((i/10%10).ToString()) else '.' )
      match cbs.State with
      | Empty   -> ()
      | AtBegin
      | Moving
      | AtEnd ->  for i in (cbs.SegCur.Tail)..(cbs.SegCur.Head-1) do dots[i] <- '◾'
      | Chasing ->
        for i in (cbs.SegCur.Tail)..(cbs.SegCur.Head-1) do dots[i] <- '◾'
        for i in (cbs.SegOld.Tail)..(cbs.SegOld.Head-1) do dots[i] <- '◾'
      Console.Write dots
      let sState = $"{cbs.State}"
      let sCur = cbs.SegCur.ToString()
      let sNewTail = sprintf "%3d" newTail
      let sNew = $"{sNewTail:S3}.{newHead:d2}"
      let sOld = cbs.SegOld.ToString()
      let sTotal =
        let sum = cbs.SegCur.NFrames + cbs.SegOld.NFrames
        $"{cbs.SegCur.NFrames:d2}+{cbs.SegOld.NFrames:d2}={sum:d2}"
      let sGap = if cbs.SegOld.Active then sprintf "%2d" (cbs.SegOld.Tail - cbs.SegCur.Head) else  "  "
      Console.WriteLine $"  cur %s{sCur}  new %s{sNew} old %s{sOld} %s{sTotal}  gap {sGap:s2} %s{sState} %s{msg}"
    let trimCurTail() =
      if newTail > 0 then
        cbs.SegCur.Tail <- newTail
        true
      else
        assert (cbs.SegCur.Tail = 0)
        false
    printCurAndOld ""
    // This test is here instead of below under Moving in case nFrames is bigger than last time.
    if newHead > cbs.NRingFrames then
      // State is AtEnd briefly here because the block will not fit after SegCur.Head.
      assert (cbs.State = Moving)
      assert (not cbs.SegOld.Active)
      cbs.State <- AtEnd  // only for readability here
      do // Exchange Segs
        let tmp = cbs.SegCur  in  cbs.SegCur <- cbs.SegOld  ;  cbs.SegOld <- tmp
      assert (cbs.SegCur.Head = 0)
      // SegCur starts fresh with head = 0, tail = 0.
      // Trim away SegOld.Tail to ensure the gap.
      newHead <- cbs.SegCur.Head + nFrames
      newTail <- newHead - cbs.NDataFrames
      cbs.State <- Chasing
      printCurAndOld "exchanged"
    match cbs.State with
    | Empty ->    
      assert (not cbs.SegCur.Active)
      assert (not cbs.SegOld.Active)
      assert (newHead = nFrames)  // The block will fit at Ring[0]
      cbs.State <- AtBegin
    | AtBegin ->
      assert (not cbs.SegOld.Active)
      assert (cbs.SegCur.Tail = 0)
      assert (cbs.SegCur.Head + cbs.NGapFrames <= cbs.NRingFrames)  // The block will def fit after SegCur.Head
      cbs.State <- if trimCurTail() then  Moving else  AtBegin
    | Moving ->
      assert (not cbs.SegOld.Active)
      trimCurTail() |> ignore
      cbs.State <- Moving
    | Chasing  ->
      assert (cbs.SegOld.Active)
      assert (newHead <= cbs.NRingFrames)  // The block will fit after SegCur.Head
      assert (cbs.SegCur.Tail = 0)
      // SegOld is active.  SegCur.Head is growing toward the SegOld.Tail, which retreats as SegCur.Head grows.
      assert (cbs.SegCur.Head < cbs.SegOld.Tail)
      trimCurTail() |> ignore
      if cbs.SegOld.NFrames > nFrames then
        // Trim nFrames from the SegOld.Tail
        if newHead + cbs.NGapFrames > cbs.SegOld.Tail + nFrames then  Console.WriteLine "bad"
        cbs.SegOld.Tail <- cbs.SegOld.Tail + nFrames
        assert (newHead + cbs.NGapFrames <= cbs.SegOld.Tail)
        cbs.State <- Chasing
      else
      // SegOld is too small; make it inactive.
        cbs.SegOld.Reset()
        cbs.State <- Moving
    | AtEnd ->
      failwith "Can’t happen."
  // state is not AtEnd.
  // cbs.Logger.Add cbs.SeqNum cbs.TimeStamp "cb bufs=" ""
  do
    // Copy the block to the ring.
    // Copy from callback data to the head of the ring and return a pointer to the copy.
    UnsafeHelpers.CopyPtrToArrayAtIndex(input, cbs.Ring, cbs.SegCur.Head, nFrames)
    cbs.SegCur.AdvanceHead nFrames
  cbs.CallbackHandoff.HandOff()
  Volatile.Write(&cbs.IsInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// initPortAudio() must be called before this constructor.
type InputStream( sampleRate       : int              ,
                  frameSize        : int              ,
                  inputParameters  : StreamParameters ,
                  outputParameters : StreamParameters ) =

  let nDataFrames = 56
  let nGapFrames  = 25
  let nRingFrames = nDataFrames + (3 * nGapFrames) / 2
  let startTime   = _DateTime.UtcNow

  let cbState = {
    // callback args  
    Input           = IntPtr.Zero
    Output          = IntPtr.Zero
    FrameCount      = 0u
    TimeInfo        = PortAudioSharp.StreamCallbackTimeInfo()
    StatusFlags     = PortAudioSharp.StreamCallbackFlags()
    // callback result
    SegCur          = Seg.NewEmpty nRingFrames sampleRate
    SegOld          = Seg.NewEmpty nRingFrames sampleRate
    SeqNum          = 0UL
    InputRingCopy   = IntPtr.Zero
    TimeStamp       = _DateTime.MaxValue // placeholder
    // more stuff
    State           = Empty
    IsInCallback    = false
    NRingFrames     = nRingFrames
    NDataFrames     = nDataFrames
    NGapFrames      = nGapFrames
    CallbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
    WithEcho        = false
    WithLogging     = false
    TimeInfoBase    = startTime  // timeInfoBase + adcInputTime -> cbState.TimeStamp
    FrameSize       = frameSize
    Ring            = Array.init<float32> nRingFrames (fun _ -> 0.0f)
//  Logger          = Logger(8000, startTime)
    DebugSimulating = simulatingCallbacks  }

  let streamCallback = PortAudioSharp.Stream.Callback(
    // The intermediate lambda here is required to avoid a compiler error.
    fun        input output frameCount  timeInfo statusFlags userDataPtr ->
      callback input output frameCount &timeInfo statusFlags userDataPtr )
  let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                        outParams       = Nullable<_>(outputParameters)        ,
                                                                        sampleRate      = sampleRate                           ,
                                                                        framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                        streamFlags     = StreamFlags.ClipOff                  ,
                                                                        callback        = streamCallback                       ,
                                                                        userData        = cbState                              ) )
  
  member val PaStream = paStream
  member val CbState  = cbState 
  
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow (fun() -> this.PaStream.Start() )
  
  member this.Stop() =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Stop () )

  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  member this.AfterCallback() =
    ()
//  Console.Write ","

  
  interface IDisposable with
    member this.Dispose() =
      Console.WriteLine("Disposing inputStream")
      this.PaStream.Dispose()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

PortAudio.LoadNativeLibrary()
PortAudio.Initialize()

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string else  ()
  let defaultInput = PortAudio.DefaultInputDevice         in log $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in log $"Number of channels = %d{nChannels}"
  let sampleRate   = int inputInfo.defaultSampleRate      in log $"Sample rate = %d{sampleRate} (default)"
  let sampleFormat = SampleFormat  .Float32
  let sampleSize   = sizeof<float32>
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = sampleFormat                      ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  log $"%s{inputInfo.ToString()}"
  log $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in log $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = sampleFormat                        ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  log $"%s{outputInfo.ToString()}"
  log $"outputParameters=%A{outputParameters}"
  let frameSize = sampleSize * nChannels
  sampleRate, frameSize, inputParameters, outputParameters

let getArrayPointer byteCount =
  let inputArray = Array.init byteCount (fun i -> float32 (i + 1000))
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

//–––––––––––––––––––––––––––––––––––––
// Main

let test inputStream frameSize =
  let (inputStream: InputStream) = inputStream
  printfn "calling callback ...\n"
  let frameCount = 5
  let byteCount = frameCount * frameSize
  let input  = getArrayPointer byteCount
  let output = getArrayPointer byteCount
  let mutable timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
  let statusFlags = PortAudioSharp.StreamCallbackFlags()
  let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(inputStream.CbState))
  for i in 1..50 do
    let fc = uint32 (if i < 25 then  frameCount else  2 * frameCount)
    let m = showGC (fun () -> 
      timeInfo.inputBufferAdcTime <- 0.001 * float i
      callback input output fc &timeInfo statusFlags userDataPtr |> ignore 
      delayMs false 1
  //  Console.WriteLine $"{i}"
    )
    delayMs false 1
  printfn "\n\ncalling callback done"

let Quiet   = false
let Verbose = true

[<EntryPoint>]
let main _ =
  let sampleRate, frameSize, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  simulatingCallbacks <- true
  use iS = new InputStream(sampleRate, frameSize, inputParameters, outputParameters)
  GC.Collect()
  try
    iS.Start()
    if simulatingCallbacks then
      test iS frameSize
    else
      printfn "Reading..."
      printfn "Begin"
      awaitForever()
      printfn "Done"
      printfn "Stopping..."
      iS.Stop() 
      printfn "Stopped"
    printfn "Terminating..."
    PortAudio.Terminate()
    printfn "Terminated"
  with
  | :? PortAudioException as e ->
      printfn "While creating the stream: %A %A" e.ErrorCode e.Message
      Environment.Exit(2)
  
  GC.Collect()
  printfn "inputStream: %A" iS
  0
