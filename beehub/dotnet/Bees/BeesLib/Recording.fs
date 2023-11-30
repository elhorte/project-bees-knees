module BeesLib.Recording

open System
open System.Threading

open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList


type AudioFormat =
  | WAV
  | MP3
  | FLAC
  | AAC
  | OGG

type Recording = {
  recordPeriod      : TimeSpan          
  interval          : TimeSpan option   
  label             : string            
  audioFormat       : AudioFormat       
  targetSampleRate  : int               
  beginDateTime     : DateTime option   
  endDateTime       : DateTime option   
  inputSampleRate   : int
  cancellationToken : CancellationToken }

// let inputSampleRate = 17
// let downsampleAudio audioData inputSampleRate fileSampleRate  :Buf =
//   new Buf(audioData.Length)
 
let startRecording (cbMessageWorkList: CbMessageWorkList) recordingParams =
  let r = recordingParams
  let handleFrame (cbMessage: CbMessage) (workId: WorkId) unregisterMe =
    if r.cancellationToken.IsCancellationRequested then
      unregisterMe()
    else
      let now = DateTime.Now
      match r.beginDateTime, r.endDateTime with
      | (Some b, Some e) when not (b <= now && now <= e) -> ()
      | _ ->
      printfn ""  
      printfn $"{r.label} recording started at: {now} for {r.recordPeriod}, with gap {r.interval}"

//     let audioData =
//       if r.targetSampleRate < r.inputSampleRate then
//         downsampleAudio cbMessage.InputSamplesCopy inputSampleRate r.targetSampleRate
//       else
//         cbMessage.InputSamplesCopy
//     let timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
//     let outputFilename = $"%s{timestamp}_%s{r.label}_%A{r.recordPeriod}_%A{r.interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}"
//     ()

//
//
//    if file_format.upper() == 'MP3':
//        if target_sample_rate == 44100 or target_sample_rate == 48000:
//            full_path_name = os.path.join(MONITOR_DIRECTORY, output_filename)
//            pcm_to_mp3_write(audio_data, full_path_name)
//        else:
//            print("mp3 only supports 44.1k and 48k sample rates")
//            quit(-1)
//    else:
//        full_path_name = os.path.join(PRIMARY_DIRECTORY, output_filename)
//        sf.write(full_path_name, audio_data, target_sample_rate, format=file_format.upper())
//
//    if not stop_recording_event.is_set():
//        print(f"Saved {label} audio to {full_path_name}, period: {record_period}, interval {interval} seconds")
//    # wait "interval" seconds before starting recording again
//    interruptable_sleep(interval, stop_recording_event)

  match r.beginDateTime with
  | None   -> printfn $"{r.label} is recording continuously"
  | Some b -> printfn $"Recording started at: {b}"

  cbMessageWorkList.RegisterWorkItem handleFrame

