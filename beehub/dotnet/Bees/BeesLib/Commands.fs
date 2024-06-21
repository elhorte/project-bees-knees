module BeesLib.Commands

open System
open System.Threading
open System.Threading.Tasks

open ConsoleReadAsync

open BeesUtil.Util
open BeesUtil.BackgroundTasks
open BeesUtil.SubscriberList
open BeesLib.InputStream


let help = """
  q stop all background tasks and quit
  c check audio pathway for over/underflows
  d one shot process to see device list
  f one shot process to see fft
  i start/stop listening, 0, 1, 2, or 3 to select channel
  m select channel to monitor
  o one shot process to view oscope
  r record audio
  s plot spectrogram of last recording
  t list background tasks
  v start/stop cli vu meter
  ? show this help message
 ^C stop all background tasks"""


let print name = $" -> {name}" |> printfn "%s"

let bgTasks = BackgroundTasks()


let printContinuously msg ctsToken =
  while not (ctsToken: CancellationToken).IsCancellationRequested do
    printfn msg
    (Task.Delay 1000).Wait()


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press q to stop all background tasks and quit
let quit cts =
  print "stopAll and quit"
  bgTasks.StopAll()
  // Tell the caller to quit.
  (cts: CancellationTokenSource).Cancel()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press c to check audio pathway for over/underflows
let checkStreamStatus n =
  print "checkStreamStatus 10"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press d for one shot process to see device list
let showAudioDeviceList() =
  print "showAudioDeviceList"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press f for one shot process to see fft
let triggerFft() =
  print "triggerFft"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press i to start/stop listening, 0, 1, 2, or 3 to select channel
#nowarn "3511" // This state machine is not statically compilable. A 'let rec' occured in the resumable code.
let toggleIntercom consoleRead cts =
  let cr = (consoleRead: ConsoleReadAsync)
  let cts = (cts: CancellationTokenSource)
  print "toggleIntercom"
  let rec loop() = task {
    let! keyInfo = cr.readKeyAsync cts.Token
    if cts.Token.IsCancellationRequested then
      printfn " Intercom canceled"
    else
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
  loop().Wait()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press ^C to stop all background tasks.
let stopAll() =
  print "stopAll"
  bgTasks.StopAll()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press m to select channel to monitor
let changeMonitorChannel() =
  print "changeMonitorChannel"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press o to view oscope
let triggerOscope() =
  print "triggerOscope"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press r to start/stop record

#if USE_FAKE_DATE_TIME

let toggleRecording() = 
  print "toggleRecording"

#else

type Recording(bgTasks: BackgroundTasks, iS: InputStream) =

  let startRecording cts =
    let (cts: CancellationTokenSource) = cts
    SaveAudioFile.saveAudioFilePeriodically iS "mp3" (TimeSpan.FromSeconds 3)  (TimeSpan.FromSeconds 5) cts.Token
  let bgTask = BgTask.New "Recording" startRecording
  
  member this.Toggle() = 
    print "toggleRecording"
    bgTask.Toggle bgTasks |> ignore

#endif

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press s to plot spectrogram of last recording
let triggerSpectrogram() =
  print "triggerSpectrogram"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press t to list background tasks
let listBackgroundTasks() =
  print "listBackgroundTasks"
  let list =
    bgTasks.ListNames
    |> Seq.map (fun s -> "  " + s)
    |> String.concat "\n"
  printf "%s" list

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press v to start/stop cli vu meter

type VuMeter(bgTasks: BackgroundTasks, iS: InputStream) =
  
  let mutable count = 0
  let mutable nextTime = DateTime.Now
  let timesPerSecond = 10.0
  let period = TimeSpan.FromSeconds (1.0 / timesPerSecond)
  let nChars = 20

  let presentation portion =
    let c = int (roundAway (portion * float nChars))
    let empty = '.'
    let full  = '█'
    let ch i = if i <= c then  full else  empty
    // "████████████........" // for 0.6
    String(Array.init nChars ch)

  let startVuMeter cts =
    let (cts: CancellationTokenSource) = cts
    nextTime <- DateTime.Now + period
    let handler (_: InputStream) (workId: SubscriptionId) unsubscribeMe =
  //  if count > 50 then cts.Cancel()  // Shows how to cancel early.
      if cts.Token.IsCancellationRequested then
        unsubscribeMe()
      elif DateTime.Now >= nextTime then
        nextTime <- nextTime + period
        let s = presentation (float (count % nChars) / float nChars) // This is only a demo.
        Console.Write $"  %s{s}\r"
        count <- count + 1
    iS.Subscribe handler |> ignore
    count <- 0
    cts.Token.WaitHandle.WaitOne() |> ignore
    
  let bgTask = BgTask.New "VuMeter" startVuMeter

  member this.Toggle() = 
    print "toggleVuMeter"
    bgTask.Toggle bgTasks |> ignore

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
