module BeesLib.Recording

open System
open System.Collections.Generic
open System.Threading

open System.Threading.Tasks
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.WorkList

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
  Begin : TimeSpan
  End   : TimeSpan }

type ActivityType =
  | Continuous
  | Range of TodRange

type State =
  | ReadyToRecord
  | RecordingUntil of int
  | WaitingUntil   of DateTime

type Recording = {
  recordingPeriod   : TimeSpan     // 0 <= x <= 24h
  interval          : TimeSpan     // x >= 0
  label             : string       // thread_id
  filenameExtension : string       // file_format       
  targetSampleRate  : int          // target_sample_rate               
  targetChannels    : int          //                
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


type RangePosition =
  | During
  | Before of DateTime // of next During today
  | After  of DateTime // of next During tomorrow

let rangePosition todRange now =
  let today    = DateTime.Today
  let tomorrow = DateTime.Today + (TimeSpan.FromDays 1)
  let todayBegin    = today    + todRange.Begin
  let tomorrowBegin = tomorrow + todRange.Begin
  let todayEnd      = today    + todRange.End
  if   now <  todayBegin then  Before todayBegin
  elif now >= todayEnd   then  After  tomorrowBegin
                         else  During

// let setState r now =
//   let recordingUntil count =
//     let xxxx todRange count =
//       WRONG
//       let dt2 =
//         match rangePosition todRange recEnd with
//         | During    ->  recEnd
//         | Before dt ->  dt
//         | After  dt ->  dt
//       let dt = max recEnd dt2
//       WaitingUntil   dt
//     if   count > 0                  then  RecordingUntil  count
//     elif r.interval = TimeSpan.Zero then  RecordingUntil (recEnd + r.recordingPeriod) // start again
//                                     else  xxxx           (recEnd + r.interval)
//   let waitingUntil dt =
//     let recordingFileSize (duration: TimeSpan) = duration.Seconds * r.targetSampleRate * r.targetChannels 
//     if now < dt then  WaitingUntil    dt
//                 else  RecordingUntil  (recordingFileSize r.recordingPeriod)
//   r.state <-
//     match r.activityType with
//     | Continuous     ->  match r.state with
//                          | RecordingUntil count          ->  recordingUntil count
//                          | WaitingUntil   dt             ->  waitingUntil   dt
//     | Range todRange ->  match r.state, rangePosition todRange now with
//                          | RecordingUntil count, _          ->  recordingUntil count
//                          | WaitingUntil   dt   , Before dt2
//                          | WaitingUntil   dt   , After  dt2 ->  waitingUntil   dt
//
// let initState r now =
//   r.state <-
//     match r.activityType with
//     | Continuous     ->  printfn $"{r.label} will recording continuously"
//                          RecordingUntil (now + r.recordingPeriod)
//     | Range todRange ->  match rangePosition todRange now with
//                          | During    ->  printfn $"{r.label} will record until end of the daily range"
//                                          RecordingUntil (now + r.recordingPeriod)
//                          | Before dt ->  printfn $"{r.label} will start recording at beginning of the daily range"
//                                          WaitingUntil dt
//                          | After  dt ->  printfn $"{r.label} will start recording tomorrow at beginning of the daily range"
//                                          WaitingUntil dt


let doRecording r (queue: Queue<CbMessage option>) =
  let makeFilename beesConfig r =
    let beesConfig = (beesConfig: BeesConfig)
    let timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
    let name = $"%s{timestamp}_%s{r.label}_%A{r.recordingPeriod}_%A{r.interval}_{beesConfig.LocationId}_{beesConfig.HiveId}"
    $"%s{name}.{r.filenameExtension.ToLower()}"
  let downSampleIfNeeded r buf =
    if r.targetSampleRate < r.inputSampleRate then  downsampleAudio buf inputSampleRate r.targetSampleRate
                                              else  buf
  // let record() = seq {
  //   while true do
  //     match queue.Dequeue() with
  //     | Some cbMessage -> //
  //                         yield! record()
  //     | None -> ()
  //     
  // //   let now = DateTime.Now
  //   // let writeFile() =
  //   //   let audioData = downSampleIfNeeded r cbMessage.InputSamplesCopy
  //   //   let outputFilename = makeFilename config r
  //   //   printfn $"\n{r.label} recording started at: {now} for {r.recordingPeriod}, with gap {r.interval}"
  //   //   let mutable fullPathName = ""
  //   //   let fileExt = r.filenameExtension.ToLower()
  //   //   match fileExt with
  //   //   | "mp3" ->
  //   //     match r.targetSampleRate with
  //   //     | 44100 | 48000 ->
  //   //       fullPathName <- osPathJoin config.MonitorDir outputFilename
  //   //       pcmToMp3Write audioData fullPathName
  //   //     | _ ->
  //   //       printfn "mp3 only supports 44.1k and 48k sample rates"
  //   //       System.Environment.Exit -1
  //   //   | _ ->
  //   //     fullPathName <- osPathJoin config.PrimaryDir outputFilename
  //   //     sf.write(fullPathName, audioData, r.targetSampleRate, format=fileExt)
  //   //   printfn $"Saved %s{r.label} audio to %s{fullPathName}, period: %A{r.recordingPeriod}, interval %A{r.interval} seconds"
  //   yield ()
  // }
  // match r.activityType with
  // | Continuous     ->  printfn $"{r.label} will recording continuously"
  //                      yield! record()
  // | Range todRange ->  match rangePosition todRange now with
  //                      | During    ->  printfn $"{r.label} will record until end of the daily range"
  //                                      RecordingUntil (now + r.recordingPeriod)
  //                      | Before dt ->  printfn $"{r.label} will start recording at beginning of the daily range"
  //                                      WaitingUntil dt
  //                      | After  dt ->  printfn $"{r.label} will start recording tomorrow at beginning of the daily range"
  //                                      WaitingUntil dt
  // }     
  ()

  
/// Start recording.
let startRecordingAsync (config: BeesConfig) (cbMessageWorkList: WorkList<CbMessage>) recordingParams = task {
  let r = recordingParams
  let queue = Queue<CbMessage option>()
  let handleFrame (cbMessage: CbMessage) (workId: SubscriptionId) unregisterMe =
    if r.cancellationToken.IsCancellationRequested then
      unregisterMe()
      queue.Enqueue None
    else
      queue.Enqueue (Some cbMessage)
  cbMessageWorkList.Subscribe handleFrame
  doRecording r queue }
