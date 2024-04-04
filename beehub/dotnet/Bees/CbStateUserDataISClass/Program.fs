
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp
open BeesLib.DebugGlobals
open BeesLib.CbMessagePool

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait() |> ignore
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


type CbState = {
  // callback args
  mutable Input           : IntPtr
  mutable Output          : IntPtr
  mutable FrameCount      : uint32
  mutable TimeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags     : PortAudioSharp.StreamCallbackFlags
  // more stuff
  mutable WithEcho        : bool
  mutable SegCur          : Seg
  mutable SegOld          : Seg
  mutable SeqNum          : uint64
  mutable InputRingCopy   : IntPtr
//mutable nRingFrames     : int
//mutable nUsableFrames   : int
//mutable nGapFrames      : int
  mutable IsInCallback    : bool
  mutable CallbackHandoff : CallbackHandoff
  TimeInfoBase            : DateTime // from PortAudioSharp TBD
  FrameSize               : int
//ringPtr                 : IntPtr
  DebugSimulating         : bool }

let callback input output frameCount timeInfo statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let cbs = handle.Target :?> CbState
  if not cbs.DebugSimulating then  Console.Write "."
  Volatile.Write(&cbs.IsInCallback, true)
  let nFrames = int frameCount
  
  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  cbs.SeqNum       <- cbs.SeqNum + 1UL

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

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

  let cbState = {
    Input           = IntPtr.Zero
    Output          = IntPtr.Zero
    FrameCount      = 0u
    TimeInfo        = dummyInstance<PortAudioSharp.StreamCallbackTimeInfo>()
    StatusFlags     = dummyInstance<PortAudioSharp.StreamCallbackFlags>()
    // callback result
    SegCur          = Seg.NewEmpty 36 sampleRate
    SegOld          = Seg.NewEmpty 36 sampleRate
    SeqNum          = 0UL
    InputRingCopy   = IntPtr.Zero
//  TimeStamp       = DateTime.MaxValue // placeholder
    // more stuff
    IsInCallback    = false
//  nRingFrames     = nRingFrames
//  nGapFrames      = nGapFrames
    CallbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
    WithEcho        = false
//  WithLogging     = false
    TimeInfoBase    = DateTime.Now  // timeInfoBase + cbState.timeInfo -> cbState.TimeStamp. should come from PortAudioSharp TBD
    FrameSize       = frameSize
//  ringPtr         = Marshal.AllocHGlobal(nRingBytes)
//  Logger          = Logger(8000, startTime)
    DebugSimulating = simulatingCallbacks  }

  let callbackStub = PortAudioSharp.Stream.Callback(
    // The intermediate lambda here is required to avoid a compiler error.
    fun        input output frameCount timeInfo statusFlags userDataPtr ->
      callback input output frameCount timeInfo statusFlags userDataPtr )
  let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                        outParams       = Nullable<_>(outputParameters)        ,
                                                                        sampleRate      = sampleRate                           ,
                                                                        framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                        streamFlags     = StreamFlags.ClipOff                  ,
                                                                        callback        = callbackStub                         ,
                                                                        userData        = cbState                              ) )
  
  member val CbState  = cbState 
  member val PaStream = paStream
  
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.CbState.CallbackHandoff.Start() ; this.PaStream.Start() )
  
  member this.Stop () =
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.CbState.CallbackHandoff.Stop () ; this.PaStream.Stop () )

  member this.Callback input output frameCount timeInfo statusFlags userDataPtr =
              callback input output frameCount timeInfo statusFlags userDataPtr

  member is.AfterCallback() =
    Console.Write "–"

  
  interface IDisposable with
    member this.Dispose() =
      System.Console.WriteLine("Disposing inputStream")
      this.PaStream.Dispose()



//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

PortAudio.LoadNativeLibrary()
PortAudio.Initialize()

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

//–––––––––––––––––––––––––––––––––––––
// Main

let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

let getArrayPointer byteCount =
  let inputArray = Array.create byteCount (float 0.0)
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

let test inputStream frameSize =
  let (inputStream: InputStream) = inputStream
  printfn "calling callback ...\n"
  let frameCount = 4
  let byteCount = frameCount * frameSize
  let input  = getArrayPointer byteCount
  let output = getArrayPointer byteCount
  let timeInfo    = PortAudioSharp.StreamCallbackTimeInfo()
  let statusFlags = PortAudioSharp.StreamCallbackFlags()
  let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(inputStream.CbState))
  for i in 1..40 do
    let fc = if i < 20 then  frameCount else  2 * frameCount
    let m = showGC (fun () -> 
      inputStream.Callback input output (uint32 fc) timeInfo statusFlags userDataPtr |> ignore 
      Console.WriteLine $"{i}" )
    (Task.Delay 1).Wait()
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