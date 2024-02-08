
open System

open System.Threading.Tasks
open FSharp.Control
open PortAudioSharp

open System

// A function to consume a lot of memory quickly
let consumeMemory() =
  // let mutable data = []
  // data <- (Array.init 1 (fun _ -> "")) :: data
  "" :: []
  // Create objects in a list, then discard them.
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> Guid.NewGuid().ToString())) :: data
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> "")) :: data
  // Here, 'data' goes out of scope and becomes eligible for garbage collection
  
let churn() =
  for _ in 1..1_000_000 do 
    consumeMemory() |> ignore
    // Optqionally, force garbage collection to see its effect (though not recommended in production code)
    GC.Collect()
    GC.WaitForPendingFinalizers()
  Console.WriteLine "Churn done."
    

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in printfn $"Sample rate = %f{sampleRate} (default)"
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  printfn $"%s{inputInfo.ToString()}"
  printfn $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in printfn $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  printfn $"%s{outputInfo.ToString()}"
  printfn $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters

// let foo count =
//   let inputArray = Array.create count (float 0.0)
//   let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
//   handle.AddrOfPinnedObject()

// /// Run the stream for a while, then stop it and terminate PortAudio.
// let run inputStream = task {
//   let inputStream = (inputStream: InputStream)
// //inputStream.Start()
//
//   let t() =
//     (Task.Delay 100).Wait()
//     printfn "calling callback ...\n"
//     let frameCount = 512
//     let input  = foo frameCount
//     let output = foo frameCount
//     let timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
//     let statusFlags = PortAudioSharp.StreamCallbackFlags()
//     let userDataPtr = IntPtr.Zero
//     for i in 1..9000 do
//       inputStream.TestCallback input output (uint32 frameCount) timeInfo statusFlags userDataPtr
//       Console.WriteLine $"{i}"
//       (Task.Delay 1).Wait()
//     printfn "\n\ncalling callback done"
//   DebugGlobals.simulating = true
//   Task.Run(churn)
//   // Task.Run(t)
//   // t()
//   
//   use cts = new CancellationTokenSource()
//   printfn "Reading..."
//   do! keyboardKeyInput cts
//
//  }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig


//–––––––––––––––––––––––––––––––––––––
// Main

let makeCallback() =
  // The intermediate lambda here is required to avoid a compiler error.
  PortAudioSharp.Stream.Callback(
    fun input output frameCount timeInfo statusFlags userDataPtr ->
      PortAudioSharp.StreamCallbackResult.Continue)

let paTryCatchRethrow f =
  try f()
  with
  | :? PortAudioException as ex -> 
    Console.WriteLine $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    raise ex
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    raise ex

let exitWithTrouble exitValue (e: PortAudioException) message =
  Console.WriteLine "Exiting with trouble: %s{message}: %A{e.ErrorCode} %A{e.Message}"
  Environment.Exit exitValue

[<EntryPoint>]
let main _ =
  PortAudio.LoadNativeLibrary()
  PortAudio.Initialize()

  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  
  let paStream = PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                       outParams       = Nullable<_>(outputParameters)        ,
                                       sampleRate      = sampleRate                           ,
                                       framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                       streamFlags     = StreamFlags.ClipOff                  ,
                                       callback        = makeCallback()                       ,
                                       userData        = Nullable()                           )
  paTryCatchRethrow (fun () ->
    task {
      churn()
    } |> Task.WaitAny |> ignore )
  0


