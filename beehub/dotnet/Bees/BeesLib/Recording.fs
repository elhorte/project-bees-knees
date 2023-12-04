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
  End  : TimeSpan }

type RangePos =
  | Before
  | During
  | After

type ActivityType =
  | Continuous
  | Range of TodRange

type State =
  | Init
  | RecordingUntil of DateTime
  | WaitingUntil   of DateTime

type Recording = {
  recordingPeriod   : TimeSpan     // 0 <= x <= 24h
  interval          : TimeSpan     // x >= 0
  label             : string       // thread_id
  filenameExtension : string       // file_format       
  targetSampleRate  : int          // target_sample_rate               
  activityType      : ActivityType // continuous recording or time or day range
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


let recordingUntil r dt now =
  r.state <-
    if now < dt then  RecordingUntil dt
                else  if r.interval = TimeSpan.Zero then  RecordingUntil (dt + r.recordingPeriod)
                                                    else  WaitingUntil   (dt + r.interval)
let waitingUntil r dt now =
  
  r.state <-
    if now < dt then  WaitingUntil    dt
                else  RecordingUntil (dt + r.recordingPeriod)

let rangePosition todRange now =
  let today = DateTime.Today
  if   now < today + todRange.Begin then  Before
  elif now < today + todRange.End   then  During
                                    else  After

let setState r now =
  match r.activityType with
  | Continuous     ->  match r.state with
                       | RecordingUntil dt ->  recordingUntil r dt now
                       | WaitingUntil   dt ->  waitingUntil   r dt now
  | Range todRange ->  match r.state, rangePosition todRange now with
                       | RecordingUntil dt, During ->  recordingUntil r dt now
                       | WaitingUntil   dt, Before ->  waitingUntil   r dt now
                       | WaitingUntil   dt, After  ->  waitingUntil   r dt now

  // match r.activityType with
  // | Continuous     -> match r.state with
  //                     | Init              ->  printfn $"{r.label} is now recording continuously"
  //                                             r.state <- RecordingUntil (now + r.recordingPeriod)
  //                     | RecordingUntil dt ->  recordingUntil dt
  //                     | WaitingUntil   dt ->  waitingUntil   dt
  // | Range todRange -> match r.state, rangePosition todRange now with
  //                     | Init, During         ->  printfn $"{r.label} is now recording until end of the daily range"
  //                                                r.state <- RecordingUntil (now + r.recordingPeriod)
  //                     | Init, Before         ->  printfn $"{r.label} recording will start at beginning of the daily range"
  //                     | Init, After          ->  printfn $"{r.label} recording will start tomorrow at beginning of the daily range"
  //                     | RecordingUntil dt, _ ->  recordingUntil dt
  //                     | WaitingUntil   dt, _ ->  waitingUntil   dt

let initState r now =
  match r.activityType with
  | Continuous     ->  printfn $"{r.label} is now recording continuously"
                       r.state <- RecordingUntil (now + r.recordingPeriod)
  | Range todRange ->  match rangePosition todRange now with
                       | During ->  printfn $"{r.label} is now recording until end of the daily range"
                                    r.state <- RecordingUntil (now + r.recordingPeriod)
                       | Before ->  printfn $"{r.label} recording will start at beginning of the daily range"
                       | After  ->  printfn $"{r.label} recording will start tomorrow at beginning of the daily range"
  | RecordingUntil dt, _ ->
      match r.activityType, rangePosition todRange now with
                      | Init, During         ->  printfn $"{r.label} is now recording until end of the daily range"
                                                 r.state <- RecordingUntil (now + r.recordingPeriod)
                      | Init, Before         ->  printfn $"{r.label} recording will start at beginning of the daily range"
                      | Init, After          ->  printfn $"{r.label} recording will start tomorrow at beginning of the daily range"

/// Start recording.
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
    setState r now
    match r.state with
    | Init             -> failwith "can’t happen"
    | RecordingUntil _ -> writeFile()
    | WaitingUntil   _ -> ()
  r.state <- Init
  setState r DateTime.Now
  cbMessageWorkList.RegisterWorkItem handleFrame

