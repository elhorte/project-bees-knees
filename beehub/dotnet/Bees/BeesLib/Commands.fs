module BeesLib.Commands

open System.Threading
open ConsoleReadAsync

let print name = printfn $" -> {name}"

let help = """
  c check audio pathway for over/underflows
  d one shot process to see device list
  f one shot process to see fft
  i press i to start/stop listening, 0, 1, 2, or 3 to select channel
  m select channel to monitor
  o one shot process to view oscope
  q stop all background tasks and quit
  s plot spectrogram of last recording
  t list background tasks
  v start/stop cli vu meter"""

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press c to check audio pathway for over/underflows
let checkStreamStatus n = task {
  print "checkStreamStatus 10" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press d for one shot process to see device list
let showAudioDeviceList() = task {
  print "showAudioDeviceList" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// one shot process to see fft
let triggerFft() = task {
  print "triggerFft" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// start/stop listening, 0, 1, 2, or 3 to select channel
#nowarn "3511" // This state machine is not statically compilable. A 'let rec' occured in the resumable code.
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
      | "3" as s -> printfn " channel %s" s         ; do! loop()
      |  s       -> printfn " channel %s unknown" s ; do! loop()
    | None -> () }
  do! loop() }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press m to select channel to monitor
let changeMonitorChannel() = task {
  print "changeMonitorChannel" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// one shot process to view oscope
let triggerOscope() = task {
  print "triggerOscope" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press q to stop all background tasks and quit
let stopAll how = task {
  if how then  print "stopAll and quit"
         else  printfn "^C -> stopAll without quitting" }
 
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press s to plot spectrogram of last recording
let triggerSpectrogram() = task {
  print "triggerSpectrogram" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press t to list background tasks
let listBackgroundTasks() = task {
  print "listBackgroundTasks" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press v to start/stop cli vu meter
let toggleVuMeter() = task { 
  print "toggleVuMeter" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
