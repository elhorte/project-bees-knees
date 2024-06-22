module BeesLib.Keyboard

open System
open System.Threading

open ConsoleReadAsync
open BeesLib.InputStream
open BeesLib.Commands


/// <summary>
/// Waits for keys from keyboard input and executes the command associated with each key.
/// </summary>
/// <remarks>
/// Control-C is intercepted so it acts like just another character command.
/// </remarks>
let processKeyboardCommands beesConfig = task {
  let processKeys inputStream = task {
    do // install Control-C handler
      let ctrlCEventHandler _ (args: ConsoleCancelEventArgs) =
        Console.Write "^C"
        stopAll()
        args.Cancel <- true // Prevent the process from terminating when we return.
      Console.CancelKeyPress.AddHandler(ConsoleCancelEventHandler ctrlCEventHandler)
    use cts = new CancellationTokenSource()  // Tells our caller to stop looking for commands from the keyboard.
    use consoleReader = new ConsoleReadAsync()
    let recording = Recording(bgTasks, inputStream)
    let vuMeter   = VuMeter  (bgTasks, inputStream)
    printfn "Reading keyboard..."
    printfn "Type a command letter, q for quit."
    while not cts.IsCancellationRequested do
      let! command = consoleReader.readKeyAsync(cts.Token)
      match command with
      | None         ->  ()
      | Some keyInfo ->
      let cr = consoleReader
      match keyInfo.KeyChar with
      | 'q'  ->  quit                 cts    // stop all background tasks and quit
      | 'c'  ->  checkStreamStatus    10     // check audio pathway for over/underflows
      | 'd'  ->  showAudioDeviceList  ()     // one shot process to see device list
      | 'f'  ->  triggerFft           ()     // one shot process to see fft
      | 'i'  ->  toggleIntercom       cr cts // start/stop listening, 0, 1, 2, or 3 to select channel
      | 'm'  ->  changeMonitorChannel ()     // select channel to monitor
      | 'o'  ->  triggerOscope        ()     // one shot process to view oscope
      | 'r'  ->  recording.Toggle     ()     // record audio
      | 's'  ->  triggerSpectrogram   ()     // plot spectrogram of last recording
      | 't'  ->  listBackgroundTasks  ()     // list background tasks
      | 'v'  ->  vuMeter.Toggle       ()     // start/stop cli vu meter
      | '?'  ->  printfn $"%s{help}"         // show this help message
      | '\r' ->  printfn ""
      | c    ->  printfn $" -> Unknown command: {c}" } 
  use inputStream = new InputStream(beesConfig)
  inputStream.Start() // ; printfn "InputStream started"
  do! processKeys inputStream
  inputStream.Stop () // ; printfn "InputStream stopped"
  }


// Sketch of taking command lines instead of command characters
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
