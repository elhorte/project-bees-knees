
open System

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open TestCbState.GcUtils
open TestCbState.InputStream


initPortAudio()

// let defaultInputDevice = PortAudio.DefaultInputDevice
// printfn $"Default input device = %d{defaultInputDevice}"
// let inputInfo = PortAudio.GetDeviceInfo defaultInputDevice
// printfn $"%s{inputInfo.ToString()}"
// let nInputChannels = inputInfo.maxInputChannels
// printfn $"Number of channels = %d{nInputChannels} (max)"
// let sampleRate = inputInfo.defaultSampleRate
// printfn $"Sample rate = %f{sampleRate} (default)"
//
// let sampleFormat = SampleFormat.Float32
//
// let mutable inputParameters = StreamParameters()
// inputParameters.device                    <- defaultInputDevice
// inputParameters.channelCount              <- nInputChannels
// inputParameters.sampleFormat              <- sampleFormat 
// inputParameters.suggestedLatency          <- inputInfo.defaultHighInputLatency
// inputParameters.hostApiSpecificStreamInfo <- IntPtr.Zero
//
// let defaultOutputDevice = PortAudio.DefaultOutputDevice
// printfn $"Default output device = %d{defaultOutputDevice}"
// let outputInfo = PortAudio.GetDeviceInfo defaultOutputDevice
// printfn $"%s{outputInfo.ToString()}"
// let nOutputChannels = outputInfo.maxOutputChannels
// printfn $"Number of channels = %d{nOutputChannels} (max)"
//
// let mutable outputParameters = StreamParameters()
// outputParameters.device                    <- defaultOutputDevice
// outputParameters.channelCount              <- nOutputChannels
// outputParameters.sampleFormat              <- sampleFormat 
// outputParameters.suggestedLatency          <- outputInfo.defaultHighOutputLatency
// outputParameters.hostApiSpecificStreamInfo <- IntPtr.Zero

/// Creates and returns the sample rate and the input parameters.
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
// BeesConfig

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––

  
type Work =
  | Normal
  | Trivial
  | TrivialStartStop
  | GcGcOnly
  | CreateOnly
  | GcNormal

let withStartStop iS withStart f =
    let iS = (iS: InputStream)
    if withStart then
      iS.Start() 
      printfn "Reading..."
    printfn "Begin"
    f()
    printfn "Done"
    if withStart then
      printfn "Stopping..."
      iS.Stop() 
      printfn "Stopped"

let Quiet    = false
let Verbose  = true
let StartYes = true
let StartNo  = false

//–––––––––––––––––––––––––––––––––––––
// Main

[<EntryPoint>]
let main _ =
  let withEcho    = false
  let withLogging = false
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  beesConfig <- {
    LocationId                 = 1
    HiveId                     = 1
    PrimaryDir                 = "primary"
    MonitorDir                 = "monitor"
    PlotDir                    = "plot"
    InputStreamAudioDuration   = _TimeSpan.FromMinutes 16
    InputStreamRingGapDuration = _TimeSpan.FromSeconds 3
    SampleSize                 = sizeof<SampleType>
    InChannelCount             = inputParameters.channelCount
    InFrameRate                = sampleRate  }
//printBeesConfig beesConfig
//keyboardInputInit()
  use inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging)
  gc()
  try
    let work = Normal
    printfn $"\nDoing {work}\n"
    let f() = churnGc 1_000_000
    match work with
    | Trivial          -> ()
    | TrivialStartStop -> withStartStop inputStream StartYes (fun () -> ())
    | CreateOnly       -> withStartStop inputStream StartNo  f
    | GcGcOnly         -> withStartStop inputStream StartYes gc
    | GcNormal         -> withStartStop inputStream StartYes f
    | Normal           -> withStartStop inputStream StartYes awaitForever
    printfn "Terminating..."
    PortAudio.Terminate()
    printfn "Terminated"
  with
  | :? PortAudioException as e ->
      printfn "While creating the stream: %A %A" e.ErrorCode e.Message
      Environment.Exit(2)
  
  gc()
  printfn "inputStream: %A" inputStream
  0