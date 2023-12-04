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

type TodRange = {
  Begin: TimeSpan
  End: TimeSpan }

type RangePos =
| Before
| During
| After

type ActivePeriod =
| Continuous
| Range of TodRange

type State =
| Waiting
| Recording
| RecordingUntil of DateTime
| WaitingUntil   of DateTime

type Recording = {
  recordingPeriod   : TimeSpan     // 0 <= x <= 24h
  interval          : TimeSpan     // x >= 0
  label             : string       // thread_id
  filenameExtension : string       // file_format       
  targetSampleRate  : int          // target_sample_rate               
  activePeriod      : ActivePeriod // continuous recording or range of time
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

let inRange todRange now =
  if   now < todRange.Begin then Before
  elif now < todRange.End   then During
                            else After

let isBefore todRange now = inRange todRange now = Before
let isDuring todRange now = inRange todRange now = During
let isAfter  todRange now = inRange todRange now = After

let initState r =
  let now = DateTime.Now
  r.state <-
    match r.activePeriod with
    | Continuous     ->  printfn $"{r.label} is now recording continuously"
                         RecordingUntil (now + r.recordingPeriod)
    | Range todRange when isDuring todRange now ->
      printfn $"{r.label} is now recording until end of daily range"
      let thisSegment = now + r.recordingPeriod
      let endOfRange  = now.Date + todRange.End
      RecordingUntil (min thisSegment endOfRange)
    | Range todRange when isBefore todRange now -> WaitingUntil (now.Date + todRange.Begin)
    | Range todRange -> WaitingUntil (now.Date + todRange.Begin)
  

let determineState r now =
  let recordingUntil dt =
    if now < dt then
      RecordingUntil dt
    else
      if r.interval = TimeSpan.Zero then  RecordingUntil (dt + r.recordingPeriod)
                                    else  WaitingUntil   (dt + r.interval)
  let waitingUntil dt =
    if now < dt then  WaitingUntil    dt
                else  RecordingUntil (dt + r.recordingPeriod)
  match r.activePeriod with
  | Continuous ->
    match r.state with
    | Waiting           ->  Waiting
    | Recording         ->  Recording
    | RecordingUntil dt ->  recordingUntil dt
    | WaitingUntil   dt ->  waitingUntil   dt
  
let startRecording (config: Config) (cbMessageWorkList: CbMessageWorkList) recordingParams =
  let r = recordingParams
  let handleFrame (cbMessage: CbMessage) (workId: WorkId) unregisterMe =
    if r.cancellationToken.IsCancellationRequested then unregisterMe() else
    let now = DateTime.Now
    let writeFile() =
      let audioData =
        if r.targetSampleRate < r.inputSampleRate then
          downsampleAudio cbMessage.InputSamplesCopy inputSampleRate r.targetSampleRate
        else
          cbMessage.InputSamplesCopy
      let timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
      let name = $"%s{timestamp}_%s{r.label}_%A{r.recordingPeriod}_%A{r.interval}_{config.LocationId}_{config.HiveId}"
      let outputFilename = $"%s{name}.{r.filenameExtension.ToLower()}"
      let mutable fullPathName = ""
      printfn ""  
      printfn $"{r.label} recording started at: {now} for {r.recordingPeriod}, with gap {r.interval}"
      match r.filenameExtension.ToUpper() with
      | "MP3" ->
        match r.targetSampleRate with
        | 44100 | 48000 ->
          fullPathName <- osPathJoin config.MonitorDir outputFilename
          pcmToMp3Write audioData fullPathName
        | _ ->
          printfn "mp3 only supports 44.1k and 48k sample rates"
          System.Environment.Exit -1
      | _ ->
        fullPathName <- osPathJoin config.PrimaryDir outputFilename
        sf.write(fullPathName, audioData, r.targetSampleRate, format=r.filenameExtension.ToUpper())
      printfn $"Saved %s{r.label} audio to %s{fullPathName}, period: %A{r.recordingPeriod}, interval %A{r.interval} seconds"
    determineState r now
    match r.state with
    | Recording         -> writeFile()
    | RecordingUntil dt -> writeFile()
    | Waiting           -> ()
    | WaitingUntil   dt -> ()
  initState r
  cbMessageWorkList.RegisterWorkItem handleFrame

