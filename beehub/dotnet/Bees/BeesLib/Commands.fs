module BeesLib.Commands

open System
open System.Threading
open System.Threading.Tasks

open ConsoleReadAsync
open BeesUtil.BackgroundTasks


let help = """
  c check audio pathway for over/underflows
  d one shot process to see device list
  f one shot process to see fft
  i press i to start/stop listening, 0, 1, 2, or 3 to select channel
  m select channel to monitor
  o one shot process to view oscope
  q stop all background tasks and quit
  r record audio
  s plot spectrogram of last recording
  t list background tasks
  v start/stop cli vu meter
  ? show this help message
 ^C stop all background tasks"""


let print name = $" -> {name}" |> printfn "%s"

let bgTasks = BackgroundTasks()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press c to check audio pathway for over/underflows
let checkStreamStatus n = task {
  print "checkStreamStatus 10" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press d for one shot process to see device list
let showAudioDeviceList() = task {
  print "showAudioDeviceList" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press f for one shot process to see fft
let triggerFft() = task {
  print "triggerFft" }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press i to start/stop listening, 0, 1, 2, or 3 to select channel
#nowarn "3511" // This state machine is not statically compilable. A 'let rec' occured in the resumable code.
let toggleIntercom consoleRead cts = task {
  let cr = (consoleRead: ConsoleReadAsync)
  let cts = (cts: CancellationTokenSource)
  print "toggleIntercom"
  let rec loop() = task {
    let! keyInfo = cr.readKeyAsync cts.Token
    match keyInfo with
    | Some keyInfo ->
      match keyInfo.KeyChar.ToString() with
      | "i" -> printfn " Intercom done"
      | "0"
      | "1"
      | "2"
      | "3" as s -> printfn " channel %s" s         ; do! loop()
      |  s       -> printfn " channel %s unknown" s ; do! loop()
    | None -> () }
  do! loop() }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press ^C to stop all background tasks.
let stopAll() = task {
  print "stopAll"
  bgTasks.StopAll()  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press m to select channel to monitor
let changeMonitorChannel() = task {
  print "changeMonitorChannel"  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press o to view oscope
let triggerOscope() = task {
  print "triggerOscope"  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press q to stop all background tasks and quit
let quit cts = task {
  print "stopAll and quit"
  bgTasks.StopAll()
  // Tell the caller to quit.
  (cts: CancellationTokenSource).Cancel()  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press r to start/stop record

#if USE_FAKE_DATE_TIME

let toggleRecording() = task { 
  print "toggleRecording"  }

#else

module Record =
  let doRecording ctsToken =
    SaveAudioFile.saveAudioFilePeriodically "mp3" (TimeSpan.FromSeconds 3)  (TimeSpan.FromSeconds 5) ctsToken
  let bgTask = BgTask.New "Recording" doRecording
  
let toggleRecording() = task { 
  print "toggleRecording"
  Record.bgTask.Toggle bgTasks  }

#endif

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press s to plot spectrogram of last recording
let triggerSpectrogram() = task {
  print "triggerSpectrogram"  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press t to list background tasks
let listBackgroundTasks() = task {
  print "listBackgroundTasks"
  let list =
    bgTasks.ListNames
    |> Seq.map (fun s -> "  " + s)
    |> String.concat "\n"
  printf "%s" list  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press v to start/stop cli vu meter

module VuMeter =
  let doVuMeter ctsToken =
    while not (ctsToken: CancellationToken).IsCancellationRequested do
      printfn "– VuMeter is on"
      (Task.Delay 1000).Wait()
  let bgTask = BgTask.New "VuMeter" doVuMeter
  
let toggleVuMeter() = task { 
  print "toggleVuMeter"
  VuMeter.bgTask.Toggle bgTasks  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
