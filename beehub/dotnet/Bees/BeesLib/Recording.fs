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

type TodRange = {
  Begin: TimeSpan
  End: TimeSpan }

type ActivePeriod =
| Continuous
| Range of TodRange

type RecordingOnOff =
| RecordingUntil of DateTime
| WaitingUntil   of DateTime

type State =
| AlwaysOn of RecordingOnOff
| RightTod of RecordingOnOff
| BeforeTodBegin
| AfterTodEnd

type Recording = {
  recordingPeriod   : TimeSpan     // 0 <= x <= 24h
  interval          : TimeSpan     // x >= 0
  label             : string       // thread_id
  filenameExtension : string       // file_format       
  targetSampleRate  : int          // target_sample_rate               
  activePeriod      : ActivePeriod // start_tod  both = 0 means continuous recording
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

let updateOnOff onOff =
  onOff // todo

let beginRightTod r now =
  
let todIsAfterEnd r state tod =
  match r.activePeriod with
  | Range todRange ->
    match state with
    | AlwaysOn onOff -> failwith "Can't happen"
    | BeforeBegin
    | RightTod
    | AfterEnd    when tod > todRange.End   -> AfterTodEnd 
    | BeforeBegin
    | RightTod
    | AfterEnd    when tod < todRange.Begin -> BeforeBegin
    | BeforeBegin
    | AfterEnd    when tod < todRange.Begin -> BeforeBegin
    | RightTod onOff ->  RightTod onOff 
  | Continuous -> 

let updateState r now =
  let tod = now - DateTime.Today
  match r.state with
  | Continuous onOff -> Continuous (updateOnOff onOff)
  | x ->
  match x with
  | AfterTodEnd
  | BeforeTodBegin when todIsAfterEnd r tod    -> AfterTodEnd
  | Init
  | AfterTodEnd
  | BeforeTodBegin when tod < r.TodBegin -> BeforeTodBegin
  | AfterTodEnd
  | BeforeTodBegin                       -> beginRightTod r now
  | _ ->
  match r.TodBegin, r.TodEnd with
  | Some b, Some e  when now < b ->  BeforeTodBegin
  | Some b, Some e  when e < now ->  AfterTodEnd
  | _ ->
  match r.state with
  | Continuous
  | BeforeTodBegin
  | AfterTodEnd -> r.state
  | RecordingUntil start ->
    if now < start + r.recordingPeriod then Recording start
    else Waiting start
  | Waiting start ->
    if start + r.recordingPeriod + r.interval < now then Recording start
    else Waiting start
    
let startRecording (config: Config) (cbMessageWorkList: CbMessageWorkList) recordingParams =
  let r = recordingParams
  if r.TodBegin.IsNone then
    r.state <- Continuous
    printfn $"{r.label} is recording continuously"
  else
    r.state <- Init
    r.state <- updateState r DateTime.Now
  let handleFrame (cbMessage: CbMessage) (workId: WorkId) unregisterMe =
    if r.cancellationToken.IsCancellationRequested then unregisterMe() else
    let now = DateTime.Now
    let state = updateState r now
    
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

  match r.TodBegin with
  | None   -> printfn $"{r.label} is recording continuously"
  | Some b -> printfn $"Recording started at: {b}"

  cbMessageWorkList.RegisterWorkItem handleFrame

