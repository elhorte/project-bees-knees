
open System

open CallbackCrash.GcUtils
open CallbackCrash.InputStream
open PortAudioSharp

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
  gc()
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