module BeesLib.SaveAudioFile

open System
open System.Threading
open NAudio.Lame

open BeesUtil.DateTimeShim

open BeesUtil.DateTimeCalculations
open BeesUtil.Ranges
open BeesUtil.SaveAsMp3
open BeesUtil.SaveAsWave
open BeesLib.InputStream


/// <summary>
/// Saves the given audio samples as an MP3 file at the given filePath.
/// </summary>
/// <param name="saveFunction">The function to save in a specific format.</param>
/// <param name="filePath">The path of the MP3 file to save.</param>
/// <param name="frameRate">The sample rate of the audio samples.</param>
/// <param name="nChannels">The number of channels in the audio samples.</param>
/// <param name="samples">The audio samples to save.</param>
let saveToFile f (filePath: string) (frameRate: float) (nChannels: int) (samples: float32[]) =
  try
    f filePath frameRate nChannels samples
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
let rec saveAudioFile ext (inputStream: InputStream) (dateTime: _DateTime) duration =
  let saveFunction =
    match ext with
    | "mp3" ->  (saveAsMp3 LAMEPreset.ABR_128)
    | "wav" ->  saveAsWave
    | _     ->  let msg = $"unknown audio file format: %A{ext}"
                fprintfn Console.Error "ERROR – Can’t save audio files. %s" msg
                failwith msg
  let save readResult =
    let samplesArray = InputStream.CopyFromReadResult readResult
    let sDate = dateTime.ToString("yyyy-MM-dd_HH꞉mm꞉sszzz")  // “modifier letter colon”, not ASCII colon, so macOS accepts it.
    let name = $"save-{sDate}.{ext}"
    Console.WriteLine (sprintf $"  saving %s{name}")
    saveToFile saveFunction name readResult.FrameRate readResult.InChannelCount samplesArray
  let readResult = inputStream.read dateTime duration
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


/// <summary>
/// Periodically saves the audio stream to an MP3 file for a specified duration and period.
/// </summary>
/// <param name="inputStream">The audio input stream to save.</param>
/// <param name="duration">The duration of each saved audio file.</param>
/// <param name="period">The interval between each save.</param>
let saveAudioFilePeriodically ext (inputStream: InputStream) duration period (ctsToken: CancellationToken) =
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
    let now = DateTime.Now in printfn $"from now %A{now.TimeOfDay}, wait %A{startTime - now}"
    inputStream.WaitUntil startTime
    let rec saveAt saveTime num =
      if ctsToken.IsCancellationRequested then ()
      else
      inputStream.WaitUntil  saveTime             ; printf $"Recording {num} ..."
      inputStream.WaitUntil (saveTime + duration) ; saveAudioFile ext inputStream saveTime duration
      saveAt (saveTime + period) (num+1)
    saveAt startTime 1


