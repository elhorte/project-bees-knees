module BeesLib.Commands

open System
open System.Threading
open System.Threading.Tasks

open ConsoleReadAsync

open BeesUtil.Util
open BeesUtil.BackgroundTasks
open BeesUtil.PortAudioUtils
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
let mutable channel = 1

let printContinuously msg ctsToken =
  while not (ctsToken: CancellationToken).IsCancellationRequested do
    printfn msg
    (Task.Delay 1000).Wait()


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type OurBgTask(iS: InputStream, name: string, f: InputStream -> CancellationTokenSource -> unit) =

  let wrapper cts =
    f iS cts

  let bgTask = BgTask.New bgTasks name wrapper
  
  member this.Toggle() =
    match bgTask with
    | None -> printfn $@"A task by the name of ""%s{name}"" already exists."
    | Some bgTask ->  
    print $"Toggle %s{name}"
    bgTask.Toggle() |> ignore

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press q to stop all background tasks and quit
let quit cts =
  print "stopAll and quit"
  bgTasks.StopAllAndWait true
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
let stopAllAndWait() =
  print "stopAll"
  bgTasks.StopAllAndWait true

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

let Recording iS = () 

#else

let Recording iS =
  let startRecording iS cts =
    let (iS : InputStream            ) = iS
    let (cts: CancellationTokenSource) = cts
    SaveAudioFile.saveAudioFilePeriodically iS "mp3" (TimeSpan.FromSeconds 3)  (TimeSpan.FromSeconds 5) cts.Token
  OurBgTask(iS, "Recording", startRecording)

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

#if USE_FAKE_DATE_TIME

let VuMeter iS = () 

#else

let VuMeter iS =
  let startVuMeter iS cts =
    let (iS : InputStream            ) = iS
    let (cts: CancellationTokenSource) = cts
    let mutable count    = 0
    let mutable nextTime = DateTime.Now
    let mutable maxValue = 0.0f
    let timesPerSecond = 10.0
    let period = TimeSpan.FromSeconds (1.0 / timesPerSecond)
    let nChars = 20
    let sawtoothValue() = float (count % nChars) / float nChars
    /// Update maxValue with samples from the most recent callback.
    let updateMaxValue cbs =
      let cbs = (cbs: CbState)
      let first = cbs.Buffer.LatestBlockIndex
      let last  = first + int cbs.FrameCount - 1
      for i in first .. last do  maxValue <- max maxValue (abs cbs.Buffer.Ring[i])
  //  Console.WriteLine $"{first} {last} {maxValue}"
    let updateDisplay (cbs: CbState) value =
      let stringDisplay portion =
        let c = int (roundAway (portion * float nChars))
        let empty = '.'
        let full  = '█'
        let ch i = if i <= c then  full else  empty
        // "████████████........" // for 0.6
        String(Array.init nChars ch)
      let logValue = convertToDb 50.0 (float value)
      let s = stringDisplay logValue
      let dt = cbs.Buffer.LatestStartTime
      let ts = DateTime.Now - dt 
      Console.Write $"  %s{s}\r" //  %A{dt} %A{ts}
  //  Console.WriteLine $"  %f{float maxValue}"
    let afterCallbackHandler (_, cbs: CbState) _ unsubscribeMe =
  //  if count > 50 then cts.Cancel()  // A BgTask can cancel itself.
      if cts.Token.IsCancellationRequested then
        unsubscribeMe()
      else
      updateMaxValue cbs
      do  //if DateTime.Now >= nextTime then
        nextTime <- nextTime + period
    //  Console.Write $"%s{blockChar (abs (float cbs.Ring[cbs.LatestBlockIndex]))}"
    //  updateDisplay cbs (sawtoothValue())
        updateDisplay cbs maxValue
        count    <- count + 1
        maxValue <- 0.0f
    nextTime <- DateTime.Now + period
    let subscription = iS.Subscribe afterCallbackHandler
    cts.Token.WaitHandle.WaitOne() |> ignore
    iS.Unsubscribe subscription |> ignore
  OurBgTask(iS, "VuMeter", startVuMeter)

#endif

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// usage: press x to start/stop sandbox

#if USE_FAKE_DATE_TIME

let Demo iS = () 

#else

let Demo iS =
  let startSandbox iS cts =
    let (cts: CancellationTokenSource) = cts
    waitUntilWithToken (DateTime.Now + (TimeSpan.FromSeconds 5)) cts.Token
    printfn " Delaying done"
  OurBgTask(iS, "Recording", startSandbox) // todo this duplicate name should be handled correctly.

#endif
