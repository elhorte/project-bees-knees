namespace ConsoleReadAsync

open System
open System.Drawing
open System.Threading
open System.Threading.Tasks

open ConsoleReadAsync.ConcurrentFlag

// https://github.com/tonerdo/readline/issues/67

// System.ReadLine.Read() below comes from the ReadLine NuGet package.

// Scenario:
// - readAsync is in progress
// - user types a partial line xyz on the console
// - readAsync is canceled
// - readAsync is called again and puts out its prompt
// - user will probably be surprised that the line returned by readAsync
//   starts with xyz.
// It would probably be better if the internal buffer kept by ReadLine.Read
// could be cleared when a new readAsync call comes in after a cancellation.
// As of now there is no way to do that in the ReadLine library API.

type Mode =
  | Line = 0
  | Key  = 1


type ConsoleReadAsync() =

  let mutable mode         = Mode.Line
  let mutable prompt       = None
  let mutable input        = ""
  let mutable key          = ConsoleKeyInfo()
  let         allowClient  = new ConcurrentFlag()
  let         allowDaemon  = new ConcurrentFlag()
  let         ctsForDaemon = new CancellationTokenSource()

  let rec daemon() =
    try  allowDaemon.Wait()
    with ex -> printfn "%A" ex
    match mode with
      | Mode.Line ->  input <- match prompt with
                               | Some prompt -> System.ReadLine.Read prompt   // from the ReadLine NuGet package
                               | None        -> Console.ReadLine()
      | Mode.Key  ->  key   <-                  Console.ReadKey()
      | _ -> failwith "unreachable"
    if not ctsForDaemon.IsCancellationRequested then
      allowClient.MakeReady()
      daemon()

  do
    ReadLine.HistoryEnabled <- true
    Task.Run daemon |> ignore


  // for F# members

  let tryReadLineAsync promptOpt (cancellationToken: CancellationToken)  : Task<string option> =
    mode   <- Mode.Line
    prompt <- promptOpt
    if allowDaemon.Ready then
      allowDaemon.MakeReady()
      // The daemon will output the prompt if there is one.
    else
      // Try again knowing that ReadLine.Read was already in progress.
      prompt |> Option.iter (printf "%s")
    task {
      let! ok = allowClient.WaitAsync cancellationToken
      if ok then return Some input else return None }
  
  let readLineFAsync prompt  : Task<string> =
    task {
      let! x = tryReadLineAsync prompt CancellationToken.None
      return
        match x with
        | Some s -> s
        | None   -> failwith "should happen only on cancellation, which is impossible here"  }

  let tryReadKeyAsync (cancellationToken: CancellationToken)  : Task<ConsoleKeyInfo option> =
    mode <- Mode.Key
    if allowDaemon.Ready then
      allowDaemon.MakeReady()
    task {
      let! ok = allowClient.WaitAsync cancellationToken
      if ok then return Some key else return None }

  let readKeyFAsync prompt  : Task<ConsoleKeyInfo> =
    task {
      let! x = tryReadKeyAsync CancellationToken.None
      return
        match x with
        | Some s -> s
        | None   -> failwith "should happen only on cancellation, which is impossible here"  }

  // for C# members

  let TryReadAsync (prompt, cancellationToken)  : Task<string> =
    let promptOption = Option.ofObj prompt
    task {
      let! result = tryReadLineAsync promptOption cancellationToken
      return Option.defaultValue null result  }
  
  // For F# and C# callers

  member this.Mode with get() = mode

  // For F# callers – When returning string option, None means canceled.

  member this.readLineAsync(prompt: string, cancellationToken: CancellationToken)  : Task<string option> = tryReadLineAsync (Some prompt) cancellationToken
  member this.readLineAsync(prompt: string                                      )  : Task<string       > = readLineFAsync   (Some prompt)        
  member this.readLineAsync(                cancellationToken: CancellationToken)  : Task<string option> = tryReadLineAsync  None         cancellationToken
  member this.readLineAsync(                                                    )  : Task<string       > = readLineFAsync    None                

  member this.readKeyAsync                  (cancellationToken: CancellationToken)  : Task<ConsoleKeyInfo option> = tryReadKeyAsync cancellationToken
  member this.readKeyAsync                  (                                    )  : Task<ConsoleKeyInfo       > = readKeyFAsync()

  // For C# callers – When returning string?, null means canceled.

  member this.ReadAsync(prompt: string, cancellationToken: CancellationToken)  : Task<string       > = TryReadAsync  (prompt, cancellationToken  )
  member this.ReadAsync(prompt: string                                      )  : Task<string       > = this.ReadAsync(prompt, CancellationToken())
  member this.ReadAsync(                cancellationToken: CancellationToken)  : Task<string       > = this.ReadAsync(null  , cancellationToken  )
  member this.ReadAsync(                                                    )  : Task<string       > = this.ReadAsync(null  , CancellationToken())

  interface IDisposable with
    member _.Dispose() =
      ctsForDaemon.Cancel()
      allowDaemon.Dispose()
      allowClient.Dispose()
