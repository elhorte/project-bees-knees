module BeesLib.Recording

open System
open System.Threading

open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList

// def recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
//  
//   recording_period    the length of time to record in seconds
//   interval            the time between recordings in seconds if > 0
//   thread_id           a string to label the thread
//   file_format         the format      in which to save the audio file
//   target_sample_rate  the sample rate in which to save the audio file
//   start_tod           the time of day to start recording, if 'None', record continuously
//   end_tod             the time of day to stop  recording, if start_tod == None, ignore & record continuously

// type AudioFormat =
//   | WAV
//   | MP3
//   | FLAC
//   | AAC
//   | OGG

type RecordingOnOff =
| Recording of DateTime
| Waiting   of DateTime

type State =
| Init
| Continuous
| BeforeStartTOD
| AfterEndTOD
| Active of RecordingOnOff

type Recording = {
  recordingPeriod   : TimeSpan        // record_period for each file
  interval          : TimeSpan option 
  label             : string          // thread_id
  filenameExtension : string          // file_format       
  targetSampleRate  : int             // target_sample_rate               
  beginTimeOfDay    : TimeSpan option // start_tod
  endTimeOfDay      : TimeSpan option // end_tod
  inputSampleRate   : int
  mutable state     : State
  cancellationToken : CancellationToken }
    
type sf() =
  static member write(fullPathName: string, audioData: Buf, targetSampleRate: int, ?format: string) = ()
  
let inputSampleRate = 17
let downsampleAudio audioData inputSampleRate fileSampleRate  =
  Buf (Array.init 1024 (fun _ -> 0.0f))
let pcmToMp3Write data name =
  ()
let osPathJoin dir name = $"{dir}/{name}"

let nextState r now =
  match r.state with
  | Continuous        -> Continuous
  | AfterEndTOD -> AfterEndTOD 
  | _ ->
  match r.beginTimeOfDay, r.endTimeOfDay with
  | Some b, Some e  when now < b ->  BeforeStartTOD
  | Some b, Some e  when e < now ->  AfterEndTOD
  | _ ->
  match r.state with
  | Continuous
  | BeforeStartTOD
  | AfterEndTOD -> r.state
  | Recording start ->
    if now < start + r.recordingPeriod then Recording start
    else Waiting start
  | Waiting start ->
    if start + r.recordingPeriod + r.interval < now then Recording start
    else Waiting start
    
let startRecording (config: Config) (cbMessageWorkList: CbMessageWorkList) recordingParams =
  let r = recordingParams
  if r.beginTimeOfDay.IsNone then
    r.state <- Continuous
    printfn $"{r.label} is recording continuously"
  else
    r.state <- Init
    r.state <- nextState r DateTime.Now
  let handleFrame (cbMessage: CbMessage) (workId: WorkId) unregisterMe =
    if r.cancellationToken.IsCancellationRequested then unregisterMe() else
    let now = DateTime.Now
    let state = nextState r now
    
    printfn ""  
    printfn $"{r.label} recording started at: {now} for {r.recordingPeriod}, with gap {r.interval}"

    let audioData =
      if r.targetSampleRate < r.inputSampleRate then
        downsampleAudio cbMessage.InputSamplesCopy inputSampleRate r.targetSampleRate
      else
        cbMessage.InputSamplesCopy
    let timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
    let name = $"%s{timestamp}_%s{r.label}_%A{r.recordingPeriod}_%A{r.interval}_{config.LocationId}_{config.HiveId}"
    let outputFilename = $"%s{name}.{r.filenameExtension.ToLower()}"
    let mutable fullPathName = ""
    if r.filenameExtension.ToUpper() = "MP3" then
      if r.targetSampleRate = 44100 or r.targetSampleRate = 48000 then
        fullPathName <- osPathJoin config.MonitorDir outputFilename
        pcmToMp3Write audioData fullPathName
      else
        printfn "mp3 only supports 44.1k and 48k sample rates"
        System.Environment.Exit -1
    else
      let fullPathName = osPathJoin config.PrimaryDir outputFilename
      sf.write(fullPathName, audioData, r.targetSampleRate, format=r.filenameExtension.ToUpper())

    printfn $"Saved %s{r.label} audio to %s{fullPathName}, period: %A{r.recordingPeriod}, interval %A{r.interval} seconds"
    // wait "interval" seconds before starting recording again
    interruptable_sleep(interval, stop_recording_event)
    ()

  match r.beginTimeOfDay with
  | None   -> printfn $"{r.label} is recording continuously"
  | Some b -> printfn $"Recording started at: {b}"

  cbMessageWorkList.RegisterWorkItem handleFrame

