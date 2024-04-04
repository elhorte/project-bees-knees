
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open PortAudioSharp


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
  mutable input           : IntPtr
  mutable output          : IntPtr
  mutable frameCount      : uint32
  mutable timeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable statusFlags     : PortAudioSharp.StreamCallbackFlags
  // more stuff
  mutable withEcho        : bool
//mutable segCur          : Seg
//mutable segOld          : Seg
  mutable seqNum          : uint64
  mutable inputRingCopy   : IntPtr
//mutable nRingFrames     : int
//mutable nUsableFrames   : int
//mutable nGapFrames      : int
  mutable isInCallback    : bool
  mutable callbackHandoff : CallbackHandoff
  timeInfoBase            : DateTime // from PortAudioSharp TBD
  frameSize               : int
//ringPtr                 : IntPtr
  debugSimulating         : bool }

let handOff cbState =
  let (cbs: CbState) = cbState
  cbs.callbackHandoff.HandOff()

let callback input output frameCount timeInfo statusFlags userDataPtr =
  Console.Write "."
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
  Volatile.Write(&cbs.isInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue


type InputStream = {
  cbState  : CbState
  paStream : PortAudioSharp.Stream } with 
  
  // initPortAudio() must be called before this.
  static member New ( sampleRate       : float            )
                    ( frameSize        : int              )
                    ( inputParameters  : StreamParameters )
                    ( outputParameters : StreamParameters ) =

    let cbState = {
      input           = IntPtr.Zero
      output          = IntPtr.Zero
      frameCount      = 0u
      timeInfo        = dummyInstance<PortAudioSharp.StreamCallbackTimeInfo>()
      statusFlags     = dummyInstance<PortAudioSharp.StreamCallbackFlags>()
      withEcho        = false
  //  segCur          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
  //  segOld          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
      seqNum          = 0UL
      inputRingCopy   = IntPtr.Zero
  //  nRingFrames     = nRingFrames
  //  nUsableFrames   = nUsableRingFrames
  //  nGapFrames      = nGapFrames
      isInCallback    = false
      callbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
      timeInfoBase    = DateTime.Now // probably wrong
      frameSize       = frameSize
  //  ringPtr         = Marshal.AllocHGlobal(nRingBytes)
      debugSimulating = false  }

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
    let iS = {
      cbState  = cbState
      paStream = paStream } 
    cbState.callbackHandoff <- CallbackHandoff.New iS.AfterCallback
    iS

  member is.Start() = paTryCatchRethrow(fun() -> is.cbState.callbackHandoff.Start() ; is.paStream.Start() )
  member is.Stop () = paTryCatchRethrow(fun() -> is.cbState.callbackHandoff.Stop () ; is.paStream.Stop () )
  member is.AfterCallback() = Console.Write "-"

  interface IDisposable with
    member this.Dispose() =
      System.Console.WriteLine("Disposing inputStream")
      this.paStream.Dispose()



//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

PortAudio.LoadNativeLibrary()
PortAudio.Initialize()

let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string else  ()
  let defaultInput = PortAudio.DefaultInputDevice         in log $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in log $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in log $"Sample rate = %f{sampleRate} (default)"
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

let Quiet   = false
let Verbose = true

[<EntryPoint>]
let main _ =
  let sampleRate, frameSize, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  use iS = InputStream.New sampleRate frameSize inputParameters outputParameters
  GC.Collect()
  try
    iS.Start() 
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