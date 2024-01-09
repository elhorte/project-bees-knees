
open System
open System.Threading
open System.Threading.Tasks

open BeesLib.CbMessageWorkList
open FSharp.Control
open PortAudioSharp
open BeesLib.PortAudioUtils
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.Keyboard
open BeesLib.PaStream

// See Theory of Operation comment before main at the end of this file.

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in printfn $"Sample rate = %f{sampleRate} (default)"
  let inputParameters = StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  printfn $"%s{inputInfo.ToString()}"
  printfn $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in printfn $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  printfn $"%s{outputInfo.ToString()}"
  printfn $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters

// for debug
let printCallback (m: CbMessage) =
  let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
  let percentCPU   = m.CbContext.PaStream.CpuLoad * 100.0
  let sDebug = sprintf "%3d: %A %s" m.SeqNum m.Timestamp m.PoolStats
  let sWork  = sprintf $"work: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
  Console.WriteLine($"{sDebug}   ––   {sWork}")

/// Run the stream for a while, then stop it and terminate PortAudio.
let run cbContext cancellationTokenSource = task {
  let cbContext = (cbContext: CbContext)
  printfn "Starting..."    ; cbContext.PaStream.Start()
  printfn "Reading..."
  do! keyboardKeyInput cancellationTokenSource
  printfn "Stopping..."    ; cbContext.PaStream.Stop()
  printfn "Stopped"
  printfn "Terminating..." ; terminatePortAudio()
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main

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

[<EntryPoint>]
let main _ =
  let mutable withEchoRef    = ref true
  let mutable withLoggingRef = ref false
  let cbMessageWorkList = CbMessageWorkList()
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  beesConfig <- {
    LocationId         = 1
    HiveId             = 1
    PrimaryDir         = "primary"
    MonitorDir         = "monitor"
    PlotDir            = "plot"
    CallbackDuration   = TimeSpan.FromMilliseconds 16
    RingBufferDuration = TimeSpan.FromMinutes 16
    SampleSize         = sizeof<SampleType>
    InChannelCount     = inputParameters.channelCount
    InSampleRate       = int sampleRate  }

  let cbMessageQueue = makeAndStartCbMessageQueue cbMessageWorkList.HandleCbMessage
  let cbContext      = makePaStream beesConfig inputParameters outputParameters sampleRate withEchoRef withLoggingRef cbMessageQueue
  keyboardInputInit()
  task {
    try
      use cts = new CancellationTokenSource()
      do! run cbContext cts
    with
    | :? PortAudioException as e -> exitWithTrouble 2 e "Running PortAudio Stream" }
  |> Task.WaitAll
  printfn "%s" (cbContext.Logger.ToString())
  0
