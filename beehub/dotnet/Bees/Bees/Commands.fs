module Bees.Commands

open System.Threading
open ConsoleReadAsync

let print name = printfn $" -> {name}"


// usage: press q to stop all processes
let stopAll() = task {
  print "stopAll" }


// usage: press c to check audio pathway for over/underflows
let checkStreamStatus n = task {
  print "checkStreamStatus 10" }


// usage: press d one shot process to see device list
let showAudioDeviceList() = task {
  print "showAudioDeviceList" }


// one shot process to see fft
let triggerFft() = task {
  print "triggerFft" }


// usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
let toggleIntercomM consoleRead cts = task {
  let cr = (consoleRead: ConsoleReadAsync)
  let cts = (cts: CancellationTokenSource)
  print "toggleIntercomM"
  let rec loop() = task {
    let! keyInfo = cr.readKeyAsync cts.Token
    match keyInfo with
    | Some keyInfo ->
      match keyInfo.KeyChar.ToString() with
      | "i" -> printfn " Done toggleIntercomM"
      | "0"
      | "1"
      | "2"
      | "3" as s -> printfn " channel %s" s ; do! loop()
      |  s       -> printfn " channel %s unknown" s ; do! loop()
    | None -> () }
  do! loop() }


// usage: press m to select channel to monitor
let changeMonitorChannel() = task {
  print "changeMonitorChannel" }


// one shot process to view oscope
let triggerOscope() = task {
  print "triggerOscope" }
 

// usage: press s to plot spectrogram of last recording
let triggerSpectrogram() = task {
  print "triggerSpectrogram" }


// usage: press t to see all threads
let listAllThreads() = task {
  print "listAllThreads" }


// usage: press v to start cli vu meter, press v again to stop
let toggleVuMeter() = task { 
  print "toggleVuMeter" }
