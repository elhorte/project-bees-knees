module BeesLib.Keyboard

open System
open System.Threading
open System.Threading.Tasks
open Microsoft.FSharp.Data.UnitSystems.SI.UnitNames

open CancelAfterDelay
open ConsoleReadAsync
open BeesLib.Commands

printfn "Press Control-C or Control-Break to exit."

let help = """
  c check audio pathway for over/underflows
  d one shot process to see device list
  f one shot process to see fft
  i press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
  m select channel to monitor
  o one shot process to view oscope
  q stop all processes and quit
  s plot spectrogram of last recording
  t see all threads
  v start cli vu meter, press v again to stop"""

/// beehive keyboard triggered management utilities
let performKey keyInfo consoleRead cancellationTokenSource =
  let keyInfo = (keyInfo: ConsoleKeyInfo)
  let cr = (consoleRead: ConsoleReadAsync)
  let keyChar = keyInfo.KeyChar
  let cts = (cancellationTokenSource: CancellationTokenSource)
  task {
    match keyChar with
    | 'q'  ->  cts.Cancel()
               do! stopAll              true   // stop all processes and quit
    | 'c'  ->  do! checkStreamStatus    10     // check audio pathway for over/underflows
    | 'd'  ->  do! showAudioDeviceList  ()     // one shot process to see device list
    | 'f'  ->  do! triggerFft           ()     // one shot process to see fft
    | 'i'  ->  do! toggleIntercomM      cr cts // press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
    | 'm'  ->  do! changeMonitorChannel ()     // select channel to monitor
    | 'o'  ->  do! triggerOscope        ()     // one shot process to view oscope
    | 's'  ->  do! triggerSpectrogram   ()     // plot spectrogram of last recording
    | 't'  ->  do! listAllThreads       ()     // see all threads
    | 'v'  ->  do! toggleVuMeter        ()     // start cli vu meter, press v again to stop
    | '\r' ->  printfn ""
    | '?'  ->  printfn $"%s{help}"
    | c    ->  printfn $"Unknown command: {c}" }
  |> Task.WaitAll
  
let keyboardInputInit() =
  printfn "Initializing keyboard input."
  let ctrlCEventHandler sender (args: ConsoleCancelEventArgs) =
//  printfn "\nConsoleCancelEventHandler called."
//  printfn $"  Key pressed: {args.SpecialKey}"

    stopAll false |> Task.WaitAll

//  printfn $"  Cancel property: {args.Cancel}"
    // Prevent the process from terminating when we return.
    args.Cancel <- true

  Console.CancelKeyPress.AddHandler(ConsoleCancelEventHandler ctrlCEventHandler)
  

let keyboardKeyInput cancellationTokenSource = task {
  let cts = (cancellationTokenSource: CancellationTokenSource)
  let takeKeys() = task {
    use consoleRead = new ConsoleReadAsync()
    printfn "Type a command or q for quit"
    while not cts.IsCancellationRequested do
      let! command = consoleRead.readKeyAsync(cts.Token)
      match command with
      | None -> ()
      | Some c -> performKey c consoleRead cts }
  if false then cancelAfterDelay cts 0.5<second> (Some "canceled") |> ignore else ()
  do! takeKeys()
  printfn "Quitting per ‘q’ keyboard command" }


// /// beehive keyboard triggered management utilities
// let performCommand (command: string) cancellationTokenSource =
//   task {
//     let cts = (cancellationTokenSource: CancellationTokenSource)
//     match command with
//     | "q" ->  stop_all() ; cts.Cancel() // usage: press q to stop all processes
//     | "c" ->  check_stream_status 10    // check audio pathway for over/underflows
//     | "d" ->  show_audio_device_list()  // one shot process to see device list
//     | "f" ->  trigger_fft()             // one shot process to see fft
//     | "i" ->  toggle_intercom_m()       // usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
//     | "m" ->  change_monitor_channel()  // usage: press m to select channel to monitor
//     | "o" ->  trigger_oscope()          // one shot process to view oscope
//     | "s" ->  trigger_spectrogram()     // usage: press s to plot spectrogram of last recording
//     | "t" ->  list_all_threads()        // usage: press t to see all threads
//     | "v" ->  toggle_vu_meter()         // usage: press v to start cli vu meter, press v again to stop
//     | c   ->  printfn $"Unknown command: {c}" }
//   |> Task.WaitAll
//
// let keyboardLineInput cancellationTokenSource = task {
//   let cts = (cancellationTokenSource: CancellationTokenSource)
//   let takeCommands() = task {
//     use consoleRead = new ConsoleReadAsync()
//     printfn "Type a command or q for quit"
//     while not cts.IsCancellationRequested do
//       let! command = consoleRead.readLineAsync("> ", cts.Token)
//       match command with
//       | None -> ()
//       | Some c -> performCommand c cts }
//   if false then cancelAfterDelay cts 0.5<second> (Some "canceled") |> ignore else ()
//   do! takeCommands()
//   printfn "Quitting per ‘q’ keyboard command" }
