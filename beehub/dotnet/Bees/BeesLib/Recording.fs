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
  duration          : TimeSpan          
  gap               : TimeSpan option   
  label             : string            
  audioFormat       : AudioFormat       
  fileSampleRate    : int               
  beginDateTime     : DateTime option   
  endDateTime       : DateTime option   
  inputSampleRate   : int               
  cancellationToken : CancellationToken }

let handleFrame (cbMessage: CbMessage) (params: Recording) =
  ()
  // if params.cancellationToken.IsCancellationRequested then
  //   workList.UnregisterWorkToDo params
  // else
  //   let now = DateTime.Now
  //   match params.beginDateTime, params.endDateTime with
  //   | (Some b, Some e) when not (b <= now & now <= e) -> ()
  //   | _ ->
  //   printfn ""  
  //   printfn $"{params.label} recording started at: {now} for {params.duration}, with gap {params.gap}"

//
//    period_start_index = buffer_index 
//    # wait PERIOD seconds to accumulate audio
//    interruptable_sleep(record_period, stop_recording_event)
//
//    period_end_index = buffer_index 
//    ##print(f"Recording length in worker thread: {period_end_index - period_start_index}, after {record_period} seconds")
//    save_start_index = period_start_index % buffer_size
//    save_end_index = period_end_index % buffer_size
//
//    # saving from a circular buffer so segments aren't necessarily contiguous
//    if save_end_index > save_start_index:   # indexing is contiguous
//        audio_data = buffer[save_start_index:save_end_index]
//    else:                                   # ain't contiguous so concatenate to make it contiguous
//        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))
//
//    if target_sample_rate < inputSampleRate:
//        # resample to lower sample rate
//        audio_data = downsample_audio(audio_data, inputSampleRate, target_sample_rate)
//
//    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
//    output_filename = f"{timestamp}_{label}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}"
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

 
let startRecording
    ( duration          : TimeSpan          )
    ( gap               : TimeSpan option   )
    ( label             : string            )
    ( audioFormat       : AudioFormat       )
    ( fileSampleRate    : int               )
    ( beginDateTime     : DateTime option   )
    ( endDateTime       : DateTime option   )
    ( inputSampleRate   : int               )
    ( cancellationToken : CancellationToken ) =

  match beginDateTime with
  | None   -> printfn $"{label} is recording continuously"
  | Some b -> printfn $"Recording started at: {b}"

  // let workToDo cbMessage = handleFrame cbMessage duration gap label audioFormat fileSampleRate beginDateTime endDateTime inputSampleRate cancellationToken
  // registerWorkToDo workToDo