module Bees.Commands

open System.Threading
open ConsoleReadAsync


// usage: press q to stop all processes
let stop_all() = task {
  printfn "stop_all" }


// usage: press c to check audio pathway for over/underflows
let check_stream_status n = task {
  printfn "check_stream_status 10" }


// usage: press d one shot process to see device list
let show_audio_device_list() = task {
  printfn "show_audio_device_list" }


// one shot process to see fft
let trigger_fft() = task {
  printfn "trigger_fft" }


// usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
let toggle_intercom_m consoleRead cts = task {
  let cr = (consoleRead: ConsoleReadAsync)
  let cts = (cts: CancellationTokenSource)
  printfn "toggle_intercom_m"
  let rec loop() = task {
    let! keyInfo = cr.readKeyAsync cts.Token
    match keyInfo with
    | Some keyInfo ->
      match keyInfo.KeyChar.ToString() with
      | "i" -> printfn "Done toggle_intercom_m"
      | "0"
      | "1"
      | "2"
      | "3" as s -> printfn "%s" s ; do! loop()
      |  s       -> printfn "Unrecognized channel %s" s ; do! loop()
    | None -> () }
  do! loop() }


// usage: press m to select channel to monitor
let change_monitor_channel() = task {
  printfn "change_monitor_channel" }


// one shot process to view oscope
let trigger_oscope() = task {
  printfn "trigger_oscope" }
 

// usage: press s to plot spectrogram of last recording
let trigger_spectrogram() = task {
  printfn "trigger_spectrogram" }


// usage: press t to see all threads
let list_all_threads() = task {
  printfn "list_all_threads" }


// usage: press v to start cli vu meter, press v again to stop
let toggle_vu_meter() = task { 
  printfn "toggle_vu_meter" }
