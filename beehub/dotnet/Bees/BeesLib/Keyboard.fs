module BeesLib.Keyboard

open System
open System.Threading

open ConsoleReadAsync
open BeesLib.Commands


/// <summary>
/// Waits for keyboard input and executes associated commands.
/// </summary>
/// <remarks>
/// The function listens for keyboard inputs and each character triggers a certain task.
/// Control-C is intercepted so it is just another character command.
/// </remarks>
let waitForKeyboardCommands() = task {
  printfn "Reading keyboard..."
  printfn "Type a command letter, q for quit."
  do // install Control-C handler
    let ctrlCEventHandler _ (args: ConsoleCancelEventArgs) =
      Console.Write "^C"
      stopAll().Wait()
      args.Cancel <- true // Prevent the process from terminating when we return.
    Console.CancelKeyPress.AddHandler(ConsoleCancelEventHandler ctrlCEventHandler)
  use cts = new CancellationTokenSource()
  use consoleReader = new ConsoleReadAsync()
  /// Keyboard triggered management utilities
  /// Cancel <c>cancellationTokenSource</c> to tell the caller to stop looking for commands from the keyboard.  
  let performKey keyInfo =
    let keyInfo = (keyInfo: ConsoleKeyInfo)
    let cr      = consoleReader
    let dispatch keyChar = task {
      match keyChar with
      | 'q'  ->  do! quit                 cts    // stop all background tasks and quit
      | 'c'  ->  do! checkStreamStatus    10     // check audio pathway for over/underflows
      | 'd'  ->  do! showAudioDeviceList  ()     // one shot process to see device list
      | 'f'  ->  do! triggerFft           ()     // one shot process to see fft
      | 'i'  ->  do! toggleIntercom       cr cts // start/stop listening, 0, 1, 2, or 3 to select channel
      | 'm'  ->  do! changeMonitorChannel ()     // select channel to monitor
      | 'o'  ->  do! triggerOscope        ()     // one shot process to view oscope
      | 'r'  ->  do! toggleRecording      ()     // record audio
      | 's'  ->  do! triggerSpectrogram   ()     // plot spectrogram of last recording
      | 't'  ->  do! listBackgroundTasks  ()     // list background tasks
      | 'v'  ->  do! toggleVuMeter        ()     // start/stop cli vu meter
      | '\r' ->  printfn ""
      | '?'  ->  printfn $"%s{help}"
      | c    ->  printfn $" -> Unknown command: {c}" }
    let dispatcherTask = dispatch keyInfo.KeyChar
    dispatcherTask.Wait()
  while not cts.IsCancellationRequested do
    let! command = consoleReader.readKeyAsync(cts.Token)
    match command with
    | None   ->  ()
    | Some c ->  performKey c 
  printfn "Quitting per ‘q’ keyboard command" }

// Sketch of taking command lines instead of command characters
//
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
