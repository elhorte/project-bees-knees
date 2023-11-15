module Bees.Keyboard

open System
open System.Threading
open System.Threading.Tasks
open Microsoft.FSharp.Data.UnitSystems.SI.UnitNames

open CancelAfterDelay
open ConsoleReadAsync
open Bees.Commands

/// beehive keyboard triggered management utilities
let performKey keyInfo consoleRead cancellationTokenSource =
  let keyInfo = (keyInfo: ConsoleKeyInfo)
  let cr = (consoleRead: ConsoleReadAsync)
  let key = keyInfo.KeyChar.ToString()
  let cts = (cancellationTokenSource: CancellationTokenSource)
  task {
    match key with
    | "q"  ->  cts.Cancel()
               do! stopAll              ()     // usage: press q to stop all processes
    | "c"  ->  do! checkStreamStatus    10     // check audio pathway for over/underflows
    | "d"  ->  do! showAudioDeviceList  ()     // one shot process to see device list
    | "f"  ->  do! triggerFft           ()     // one shot process to see fft
    | "i"  ->  do! toggleIntercomM      cr cts // usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
    | "m"  ->  do! changeMonitorChannel ()     // usage: press m to select channel to monitor
    | "o"  ->  do! triggerOscope        ()     // one shot process to view oscope
    | "s"  ->  do! triggerSpectrogram   ()     // usage: press s to plot spectrogram of last recording
    | "t"  ->  do! listAllThreads       ()     // usage: press t to see all threads
    | "v"  ->  do! toggleVuMeter        ()     // usage: press v to start cli vu meter, press v again to stop
    | "\r" ->  printfn ""
    | c    ->  printfn $"Unknown command: {c}" }
  |> Task.WaitAll

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
