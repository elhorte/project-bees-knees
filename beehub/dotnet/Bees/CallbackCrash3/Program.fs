
open System
open System.Threading.Tasks
open PortAudioSharp


//–––––––––––––––––––––––––––––––––––––––––––––––––––

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  if print then Console.Write "}"

let awaitForever() = delayMs false Int32.MaxValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let gcN() = GC.Collect()

let gc() = gcN |> ignore


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

let paTryCatchRethrow f = paTryCatch f (fun _ -> ()                 )

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

let callback input output frameCount timeInfo statusFlags userDataPtr =
  Console.Write "."
  PortAudioSharp.StreamCallbackResult.Continue
  

type InputStream = { paStream : PortAudioSharp.Stream } with 
  
  // initPortAudio() must be called before this.
  static member New ( sampleRate       : float            )
                    ( inputParameters  : StreamParameters )
                    ( outputParameters : StreamParameters ) =

    let callbackStub = PortAudioSharp.Stream.Callback(
      // The intermediate lambda here is required to avoid a compiler error.
      fun        input output frameCount timeInfo statusFlags userDataPtr ->
        callback input output frameCount timeInfo statusFlags userDataPtr )
    let is = { paStream = dummyInstance<PortAudioSharp.Stream>() }
    let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                          outParams       = Nullable<_>(outputParameters)        ,
                                                                          sampleRate      = sampleRate                           ,
                                                                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                          streamFlags     = StreamFlags.ClipOff                  ,
                                                                          callback        = callbackStub                         ,
                                                                          userData        = 17                                   ) )
    { is with paStream = paStream }
  
  member is.Start() = paTryCatchRethrow(fun() -> is.paStream.Start())
  member is.Stop () = paTryCatchRethrow(fun() -> is.paStream.Stop ())

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
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  log $"%s{inputInfo.ToString()}"
  log $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in log $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  log $"%s{outputInfo.ToString()}"
  log $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters

//–––––––––––––––––––––––––––––––––––––
// Main

let Quiet   = false
let Verbose = true

[<EntryPoint>]
let main _ =
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  use iS = InputStream.New sampleRate inputParameters outputParameters
  gc() // if GC.Collect() is here instead of inside two layers of functions, it crashes trying do dispose of iS 
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
  
  gc()
  printfn "inputStream: %A" iS
  0