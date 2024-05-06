
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
open BeesUtil.Mp3
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

let CreateSampleArray nFrames nChannels = Array.zeroCreate (nFrames * nChannels)

/// save a 5-second mp3 file every 10 seconds
let saveMp3 (inputStream: InputStream) =
  let mutable deliveredArray: float32[] = [||] // samples
  let mutable destIndexNS = 0
  let mutable nDeliveries = 0
  let acceptOneDelivery (array, sizeNF, indexNF, nFrames, nChannels, time, duration) =
    let printRange() = printfn $"index %d{indexNF}  length %d{nFrames}  time %A{time}  duration %A{duration}"
    printRange()
    // if destIndexNS = 0 then  deliveredArray <- CreateSampleArray sizeNF nChannels
    // copy to deliveredArray
    // let inSampleRate   = inputStream.BeesConfig.InSampleRate
    // let inChannelCount = inputStream.BeesConfig.InChannelCount
  let intervalSec = 5
  //  ...|....|....|....
  //   |<––––––––– now
  //          |<– delayUntil startTime
  //     |––––| mp3 file 1
  //               |<– delayUntil startTime + intervalSec 
  //          |––––| mp3 file 2
  let duration = _TimeSpan.FromSeconds intervalSec
  let startTime = getNextSecondBoundary intervalSec _DateTime.Now
  printfn $"%A{startTime - _DateTime.Now}"
  let rec saveMp3File (time: _DateTime) =
    waitUntil (time + duration)
    let resultEnum, deliveredTime, deliveredDuration as result = inputStream.read time duration acceptOneDelivery
    let save() =
    //   saveAsMp3 "save" inSampleRate inChannelCount (samples: float32[])
      ()
    match resultEnum with
    | InputStreamGetResult.ErrorTimeout       
    | InputStreamGetResult.ErrorBeforeData    
    | InputStreamGetResult.ErrorAfterData      ->  printfn $"%A{deliveredTime}  %A{deliveredDuration} %A{resultEnum}"
    | InputStreamGetResult.WarnClippedBothEnds
    | InputStreamGetResult.WarnClippedTail    
    | InputStreamGetResult.WarnClippedHead    
    | InputStreamGetResult.AsRequested         ->  printfn $"%A{deliveredTime}  %A{deliveredDuration} %A{resultEnum}"
                                                   save()
    saveMp3File (time + duration)
  saveMp3File startTime

/// Run the stream for a while, then stop it and terminate PortAudio.
let run inputStream = task {
  let inputStream = (inputStream: InputStream)
  inputStream.Start()
  use cts = new CancellationTokenSource()
  printfn "Reading..."
  saveMp3 inputStream
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
