
open System
open System.Threading
open BeesUtil.Ranges
open FSharp.Control

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesUtil.DateTimeCalculations
open BeesUtil.AudioUtil
open BeesUtil.SaveAsMp3
open BeesUtil.SaveAsWave
open BeesLib.InputStream
open BeesLib.BeesConfig
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

/// <summary>
/// Saves to an MP3 file from the inputStream buffer at given time for a given duration.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="time">The starting time of the save operation.</param>
/// <param name="duration">The duration of each saved audio file.</param>
let rec save saveFunction ext (inputStream: InputStream) (time: _DateTime) duration =
  let save readResult =
    let samplesArray = InputStream.CopyFromReadResult readResult
    let sDate = time.ToString("o")
    let name1 = $"save-{sDate}.{ext}"
    let namefixed = name1.Replace(":", ".")
    saveToFile saveFunction namefixed readResult.FrameRate readResult.InChannelCount samplesArray
  Console.WriteLine (sprintf $"saveMp3File %A{time.TimeOfDay} %A{duration}")
  let readResult = inputStream.read time duration
  let print() = Console.WriteLine (sprintf $"adcStartTime %A{readResult.Time.TimeOfDay}  %A{readResult.Duration} %A{readResult.RangeClip}")
  match readResult.RangeClip with
  | RangeClip.BeforeData    
  | RangeClip.AfterData       ->  print()
  | RangeClip.ClippedBothEnds
  | RangeClip.ClippedTail    
  | RangeClip.ClippedHead    
  | RangeClip.RangeOK         ->  print()
                                  save readResult
  | _                         ->  failwith "unkonwn result code"

/// <summary>
/// Periodically saves the audio stream to an MP3 file for a specified duration and period.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="duration">The duration of each saved audio file.</param>
/// <param name="period">The interval between each save.</param>
let saveMp3Periodically (inputStream: InputStream) duration period =
  //  ....|.....|.....|....
  //   |<––––––––– Now
  //      |<– startTIme
  //       saveFrom startTime
  //         |<– delayUntil saveTime + duration (actually, slightly after)
  //      |––|   save file 1
  //             saveFrom saveTime + period
  //               |<– delayUntil saveTime + duration 
  //            |––|   save file 2
  match roundUp inputStream.HeadTime period with
  | Error s -> failwith $"%s{s} – unable to calculate start time for saving audio files"
  | Good startTime -> 
  printfn $"startTime %A{startTime.TimeOfDay}  slop %A{startTime - _DateTime.Now}"
  let rec saveFrom saveTime =
    inputStream.WaitUntil (saveTime + duration)
    save saveAsMp3 "mp3" inputStream saveTime duration
    saveFrom (saveTime + period)
  saveFrom startTime

/// Run the stream for a while, then stop it and terminate PortAudio.
let run inputStream = task {
  let inputStream = (inputStream: InputStream)
  inputStream.Start()
  use cts = new CancellationTokenSource()
  printfn "Reading..."
  saveMp3Periodically inputStream (TimeSpan.FromSeconds 4)  (TimeSpan.FromSeconds 5)
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
    LocationId                 = 1
    HiveId                     = 1
    PrimaryDir                 = "primary"
    MonitorDir                 = "monitor"
    PlotDir                    = "plot"
    InputStreamAudioDuration   = _TimeSpan.FromMinutes 16
    InputStreamRingGapDuration = _TimeSpan.FromSeconds 1
    SampleSize                 = sizeof<SampleType>
    InChannelCount             = inputParameters.channelCount
    InFrameRate                = sampleRate  }
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
