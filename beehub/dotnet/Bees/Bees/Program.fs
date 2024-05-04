
open System
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesUtil.DateTimeCalculations
open BeesLib.InputStream
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.Keyboard

// See Theory of Operation comment before main at the end of this file.

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

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

/// save a 5-second mp3 file every 10 seconds
let saveMp3 (inputStream: InputStream) =
  let mutable deliveredArray: float32[] = [||] // samples
  let mutable destIndexNS = 0
  let mutable nDeliveries = 0
  let acceptOneDelivery (array, sizeNF, indexNF, nFrames, nChannels, time, duration) =
    let printRange() = printfn $"index %d{indexNF}  length %d{nFrames}  time %A{time}  duration %A{duration}"
    printRange()
    // let sizeNS   = sizeNF  * nChannels
    // let indexNS  = indexNF * nChannels
    // let nSamples = nFrames * nChannels
    // if destIndexNS = 0 then  deliveredArray <- Array.zeroCreate<float32> sizeNS
    // Array.Copy(array, indexNS, deliveredArray, destIndexNS, nSamples)
    // destIndexNS <- destIndexNS + nSamples
    // nDeliveries <- nDeliveries + 1
  let interval = 5.0
  let startTime = getNextSecondBoundary(interval).AddSeconds(interval)
  Task.Run(fun () -> waitUntil startTime).Wait()
  let rec repeat dt =\
    xxx
    let time = (dt: DateTime).AddSeconds(-interval)
    let duration = TimeSpan.FromSeconds interval
    let resultEnum, deliveredTime, deliveredDuration as result = inputStream.read time duration acceptOneDelivery
    match resultEnum with
    | InputStreamGetResult.ErrorTimeout       
    | InputStreamGetResult.ErrorBeforeData    
    | InputStreamGetResult.ErrorAfterData     
    | InputStreamGetResult.WarnClippedBothEnds
    | InputStreamGetResult.WarnClippedTail    
    | InputStreamGetResult.WarnClippedHead    
    | InputStreamGetResult.AsRequested         -> printfn $"%A{deliveredTime}  %A{deliveredDuration}"
    waitUntil (time.AddSeconds interval)
  repeat startTime

/// Run the stream for a while, then stop it and terminate PortAudio.
let run inputStream = task {
  let inputStream = (inputStream: InputStream)
  inputStream.Start()
  use cts = new CancellationTokenSource()
  printfn "Reading..."
  (saveMp3 inputStream).Wait()
  do! keyboardKeyInput "" cts
  printfn "Stopping..."    ; inputStream.Stop()
  printfn "Stopped"
  printfn "Terminating..." ; terminatePortAudio()
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main



[<EntryPoint>]
let main _ =
  let withEcho    = false
  let withLogging = false
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation false
  beesConfig <- {
    LocationId                  = 1
    HiveId                      = 1
    PrimaryDir                  = "primary"
    MonitorDir                  = "monitor"
    PlotDir                     = "plot"
    InputStreamAudioDuration    = _TimeSpan.FromMinutes 16
    InputStreamRingGapDuration  = _TimeSpan.FromSeconds 1
    SampleSize                  = sizeof<SampleType>
    InChannelCount              = inputParameters.channelCount
    InSampleRate                = int sampleRate  }
  printBeesConfig beesConfig
  keyboardInputInit()
  try
      let inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging, NotSimulating)
      let t = task {
        do! run inputStream 
        inputStream.CbState.Logger.Print "Log:" }
      t.Wait() 
      printfn "Task done." 
  finally
    printfn "Exiting with 0."
  0
