namespace ConsoleReadAsync

open System
open System.Threading
open System.Threading.Tasks

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

type ReadMode =
  | Line = 0
  | Key  = 1

type ConsoleReadAsync() =

  let mutable prompt       = None
  let mutable input        = ""
  let mutable key          = ConsoleKeyInfo()
  let mutable mode         = ReadMode.Line
  let         allowClient  = new SemaphoreSlim(0, 1)
  let         allowDaemon  = new SemaphoreSlim(0, 1)
  let         ctsForDaemon = new CancellationTokenSource()

  let rec daemon() =
    try  allowDaemon.Wait()
    with ex -> printfn "%A" ex
    match mode with
      | ReadMode.Line ->  input <- match prompt with
                                   | Some prompt -> System.ReadLine.Read prompt   // from the ReadLine NuGet package
                                   | None        -> Console.ReadLine()
      | ReadMode.Key  ->  key   <-                  Console.ReadKey()
      | _ -> failwith "unreachable"
    if not ctsForDaemon.IsCancellationRequested then
      allowClient.Release 1 |> ignore
      daemon()

  do
    ReadLine.HistoryEnabled <- true
    Task.Run daemon |> ignore


  let semaphoreWaitAsync semaphore cancellationToken = task {
    try
      let ss = (semaphore: SemaphoreSlim)
      let ct = (cancellationToken : CancellationToken)
      do! ss.WaitAsync(ct)
      return true
    with _ ->
      return false }

  // for F# members

  let tryReadLineAsync promptOpt (cancellationToken: CancellationToken)  : Task<string option> =
    mode   <- ReadMode.Line
    prompt <- promptOpt
    if allowDaemon.CurrentCount = 0 then
      allowDaemon.Release 1 |> ignore
      // The daemon will output the prompt if there is one.
    else
      // Try again knowing that ReadLine.Read was already in progress.
      prompt |> Option.iter (printf "%s")
    task {
      let! ok = semaphoreWaitAsync allowClient cancellationToken
      if ok then return Some input else return None }
  
  let readLineFAsync prompt  : Task<string> =
    task {
      let! x = tryReadLineAsync prompt CancellationToken.None
      return
        match x with
        | Some s -> s
        | None   -> failwith "should happen only on cancellation, which is impossible here"  }

  let tryReadKeyAsync (cancellationToken: CancellationToken)  : Task<ConsoleKeyInfo option> =
    mode <- ReadMode.Key
    if allowDaemon.CurrentCount = 0 then
      allowDaemon.Release 1 |> ignore
    task {
      let! ok = semaphoreWaitAsync allowClient cancellationToken
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

  // For F# callers – returns string option, None means canceled

  member this.readLineAsync(prompt: string, cancellationToken: CancellationToken)  : Task<string option> = tryReadLineAsync (Some prompt) cancellationToken
  member this.readLineAsync(prompt: string                                      )  : Task<string       > = readLineFAsync   (Some prompt)        
  member this.readLineAsync(                cancellationToken: CancellationToken)  : Task<string option> = tryReadLineAsync  None         cancellationToken
  member this.readLineAsync(                                                    )  : Task<string       > = readLineFAsync    None                

  member this.readKeyAsync                  (cancellationToken: CancellationToken)  : Task<ConsoleKeyInfo option> = tryReadKeyAsync cancellationToken
  member this.readKeyAsync                  (                                    )  : Task<ConsoleKeyInfo       > = readKeyFAsync()

  // For C# callers – returns string?, null means canceled

  member this.ReadAsync(prompt: string, cancellationToken: CancellationToken)  : Task<string       > = TryReadAsync  (prompt, cancellationToken  )
  member this.ReadAsync(prompt: string                                      )  : Task<string       > = this.ReadAsync(prompt, CancellationToken())
  member this.ReadAsync(                cancellationToken: CancellationToken)  : Task<string       > = this.ReadAsync(null  , cancellationToken  )
  member this.ReadAsync(                                                    )  : Task<string       > = this.ReadAsync(null  , CancellationToken())

  interface IDisposable with
    member _.Dispose() =
      ctsForDaemon.Cancel()
      allowDaemon.Dispose()
      allowClient.Dispose()
