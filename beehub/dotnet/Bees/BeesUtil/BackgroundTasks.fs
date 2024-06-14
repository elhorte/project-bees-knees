module BeesUtil.BackgroundTasks

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks


/// Represents a collection of background tasks, each with a name and a CancellationTokenSource.
type BackgroundTasks() =
  
  let bgTasks = List<string * CancellationTokenSource>()

  let findItem name = bgTasks |> Seq.tryFind (fun (s, _) -> s = name)

  
  /// <summary>
  /// A sequence of names of the background tasks.
  /// </summary>
  member this.ListNames =
    bgTasks
    |> Seq.map (fun (s, _) -> s)

  
  /// <summary>Adds a background task if a task of that name does not already exist.</summary>
  /// <param name="name">The name of the task.</param>
  /// <param name="cancellationTokenSource">A cancellation token source for the task.</param>
  /// <returns>A boolean, <c>true</c> if the task was added.</returns>
  member this.Add(name, cancellationTokenSource) =
    match findItem name with
    | Some _ -> false
    | None ->
    bgTasks.Add(name, cancellationTokenSource)
    true

  /// <summary>
  /// Cancels and removes the background task with <c>name</c>.
  /// </summary>
  /// <param name="name">The name of the background task to cancel.</param>
  /// <remarks>
  /// If a task with the specified name does not exist, the function does not perform any actions.
  /// </remarks>
  member this.Kill(name: string) =
    let bgTask = bgTasks |> Seq.tryFind (fun (s, _) -> s = name)
    match bgTask with
    | Some bgTask -> let _,cts = bgTask
                     cts.Cancel()
                     bgTasks.Remove bgTask |> ignore
    | None        -> ()

  
  /// <summary>
  /// Cancels and removes all background task.
  /// </summary>
  member this.KillAll() =
    for s,_ in bgTasks do
      this.Kill s |> ignore

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

// Background Task
type BgTask = {
  Name           : string
  Func           : CancellationToken -> unit
  mutable CTS    : CancellationTokenSource
  mutable Active : bool  }
with

  /// Starts/Stops a background task.
  member this.Toggle (msg: string) (bgTasks: BackgroundTasks) =
    Console.WriteLine msg
    if this.Active then
      bgTasks.Kill this.Name
      this.Active <- not this.Active
      this.CTS.Dispose()
      printfn $"{this.Name} killed"
    else
      this.CTS.Dispose()
      this.CTS <- new CancellationTokenSource()
      if bgTasks.Add(this.Name, this.CTS) then
        this.Active <- not this.Active
        let f() = this.Func this.CTS.Token
        printfn $"{this.Name} starting"
        Task.Run(f) |> ignore
      else
        printfn $"{this.Name} is already running."
