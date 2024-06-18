module BeesUtil.BackgroundTasks

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks

open BeesUtil.Util

let IsActive  = 1L
let NotActive = 0L

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

// Background Task
type BgTask = {
  Name           : string
  Func           : CancellationToken -> unit
  mutable CTS    : CancellationTokenSource
  mutable Active : int64  }
with

  static member New name func =
    let bgTask = {
      Name   = name
      Func   = func
      CTS    = new CancellationTokenSource()
      Active = NotActive  }
    bgTask.CTS.Dispose()
    bgTask
  
  /// Starts/Stops a background task.
  member this.Toggle (bgTasks: BackgroundTasks) =
    if IsActive = Interlocked.CompareExchange(&this.Active, IsActive, IsActive) then
      bgTasks.Stop this
    else
      if not (bgTasks.Start(this)) then
        Console.WriteLine $"{this.Name} is already running."

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

/// Represents a collection of background tasks, each with a name and a CancellationTokenSource.
and BackgroundTasks() =
  
  let bgTasks = List<BgTask>()

  let findItem name = bgTasks |> Seq.tryFind (fun {Name = s} -> s = name)

  let start bgTask =
    if IsActive = Interlocked.CompareExchange(&bgTask.Active, IsActive, NotActive) then
      Console.WriteLine $"  {bgTask.Name} already started"
    else
    bgTasks.Add(bgTask)
    bgTask.CTS    <- new CancellationTokenSource()
    let f() =
      Console.WriteLine $"  {bgTask.Name} starting"
      try
        bgTask.Func bgTask.CTS.Token
      finally
        Console.WriteLine $"  {bgTask.Name} stopped"
        bgTasks.Remove bgTask |> ignore
        bgTask.CTS.Dispose()
        if NotActive = Interlocked.CompareExchange(&bgTask.Active, NotActive, IsActive) then
          Console.WriteLine $"  {bgTask.Name} stopped but was not active – can’t happen"
    Task.Run(f) |> ignore


  let stop bgTask =
    if NotActive = Interlocked.CompareExchange(&bgTask.Active, IsActive, IsActive) then
      Console.WriteLine $"  {bgTask.Name} already stopped"
    else
    // Actually set to NotActive later when the BgTask has actually stopped.
    try
      bgTask.CTS.Cancel()
    with
    | :? ObjectDisposedException as e -> Console.WriteLine $"{bgTask.Name} trouble canceling: %A{e}."
    
  
  /// <summary>
  /// Returns a sequence of names of running background tasks.
  /// </summary>
  member this.ListNames =
    bgTasks
    |> Seq.map (fun {Name = s} -> s)

  
  /// <summary>Starts a background task if it is not already running.</summary>
  /// <param bgTask="bgTask">The <c>BgTask</c> to run.</param>
  /// <returns>A boolean, <c>true</c> if the task was started.</returns>
  member this.Start(bgTask: BgTask) =
    match findItem bgTask.Name with
    | Some _ -> false
    | None ->
    start bgTask
    true

  /// <summary>
  /// Cancels and the <c>BgTask</c></c>.
  /// </summary>
  /// <param bgTask="bgTask">The <c>BgTask</c> to stop.</param>
  /// <remarks>
  /// If the <c>BgTask</c> is not running, the function does not perform any actions.
  /// The <c>BgTask</c> is removed from the list when it completes.
  /// </remarks>
  member this.Stop(bgTask: BgTask) =
    let bgTask = findItem bgTask.Name
    match bgTask with
    | Some bgTask -> stop bgTask
    | None        -> ()

  
  /// <summary>
  /// Stops all running background tasks.
  /// </summary>
  member this.StopAll() =
    let bgTasksCopy = bgTasks |> Seq.toArray
    for bgTask in bgTasksCopy do
      this.Stop bgTask
