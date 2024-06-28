module BeesLib.SaveAudioFile

open System
open System.Threading
open NAudio.Lame

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.Util
open BeesUtil.DateTimeCalculations
open BeesUtil.RangeClipper
open BeesUtil.SaveAsMp3
open BeesUtil.SaveAsWave
open BeesLib.AudioBuffer
open BeesLib.InputStream


/// <summary>
/// Saves the given audio samples as an MP3 file at the given filePath.
/// </summary>
/// <param name="saveFunction">The function to save in a specific format.</param>
/// <param name="filePath">The path of the MP3 file to save.</param>
/// <param name="frameRate">The sample rate of the audio samples.</param>
/// <param name="nChannels">The number of channels in the audio samples.</param>
/// <param name="samples">The audio samples to save.</param>
let saveToFile f (frameRate: float) (nChannels: int) (filePath: string) (samples: float32[]) =
  try
    f frameRate nChannels filePath samples
  with
  | :? System.IO.IOException as ex ->
    printfn "Failed to write to file %s, Error: %s" filePath ex.Message
  | ex ->
    printfn "An error occurred: %s" ex.Message


/// <summary>
/// Saves to an MP3 file from the inputStream buffer at given time for a given duration.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="time">The starting time of the save operation.</param>
/// <param name="duration">The duration of each saved audio file.</param>
let saveAudioFile ext (inputStream: InputStream) duration (dateTime: _DateTime) =
  let saveFunction =
    match ext with
    | "mp3" ->  (saveAsMp3 LAMEPreset.ABR_128)
    | "wav" ->  saveAsWave
    | _     ->  let msg = $"unknown audio file format: %A{ext}"
                fprintfn Console.Error "ERROR – Can’t save audio files. %s" msg
                failwith msg
  let save readResult =
    let samplesArray = AudioBuffer.CopyFromReadResult readResult
    let sDate, sTz = dateTimeFormattedForLocalTimezone "yyyy-MM-dd_HH꞉mm꞉ss" dateTime // “modifier letter colon”, not ASCII colon, so macOS accepts it.
    let name = $"save-{sDate}_{sTz}.{ext}"
    Console.WriteLine (sprintf $"  saving %s{name}")
    saveToFile saveFunction readResult.FrameRate readResult.InChannelCount name samplesArray
  let readResult = inputStream.Buffer.read dateTime duration
  let print() = () // Console.Write $"adcStartTime %A{readResult.Time.TimeOfDay}  %A{readResult.Duration} %A{readResult.RangeClip}"
  match readResult.RangeClip with
  | RangeClip.BeforeData    
  | RangeClip.AfterData       ->  print()
  | RangeClip.ClippedBothEnds
  | RangeClip.ClippedTail    
  | RangeClip.ClippedHead    
  | RangeClip.RangeOK         ->  print()
                                  save readResult
  | _                         ->  failwith "unkonwn result code"


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudio argument prep

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string
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
// Recording

#if USE_FAKE_DATE_TIME
#else

/// <summary>
/// Periodically saves the audio stream to an MP3 file for a specified duration and period.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="duration">The duration of each saved audio file.</param>
/// <param name="ext">The file type, "mp3" etc.</param>
/// <param name="cancellationToken">The cancellationToken.</param>
let saveAudioFileWithWait (inputStream: InputStream) ext duration startTime (ctsToken: CancellationToken) =
  inputStream.Buffer.WaitUntil(startTime           , ctsToken) ; printf $"Recording ..."
  inputStream.Buffer.WaitUntil(startTime + duration, ctsToken) ; saveAudioFile ext inputStream duration startTime

/// <summary>
/// Periodically saves the audio stream to an MP3 file for a specified duration and period.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="ext">The file type, "mp3" etc.</param>
/// <param name="duration">The duration of each saved audio file.</param>
/// <param name="period">The interval between each save.</param>
/// <param name="cancellationToken">The cancellationToken.</param>
let saveAudioFilePeriodically inputStream ext duration period (ctsToken: CancellationToken) =
  //  ....|.....|.....|....
  //   |<––––––––– Now
  //      |<– startTIme
  //       saveFrom startTime
  //         |<– delayUntil saveTime + duration (actually, slightly after)
  //      |––|   save file 1
  //             saveFrom saveTime + period
  //               |<– delayUntil saveTime + duration 
  //            |––|   save file 2
  match roundUp (inputStream: InputStream).Buffer.HeadTime period with
  | Error s -> failwith $"%s{s} – unable to calculate start time for saving audio files"
  | Good startTime -> 
  let now = DateTime.Now in printfn $"from now %A{now.TimeOfDay}, wait %A{startTime - now}"
  let rec saveAt saveTime num =
    if ctsToken.IsCancellationRequested then ()
    else
    saveAudioFileWithWait inputStream ext duration saveTime ctsToken
    saveAt (saveTime + period) (num+1)
  saveAt startTime 1

#endif
