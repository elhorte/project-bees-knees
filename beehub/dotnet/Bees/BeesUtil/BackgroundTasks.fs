module BeesUtil.BackgroundTasks

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks

open BeesUtil.Util

let IsActive  = 1L
let NotActive = 0L

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

/// Background Task
type BgTask = {
  BgTasks        : BackgroundTasks
  Name           : string
  Run            : CancellationTokenSource -> unit
  mutable CTS    : CancellationTokenSource
  mutable Active : int64  }
with

  static member New bgTasks name runFunc =
    let bgTask = {
      BgTasks = bgTasks
      Name    = name
      Run     = runFunc
      CTS     = new CancellationTokenSource()
      Active  = NotActive  }
    bgTask.CTS.Dispose()
    bgTask
  
  /// Starts/Stops a background task.
  /// Returns true if started
  member this.Toggle()  : bool =
    if IsActive = Interlocked.CompareExchange(&this.Active, IsActive, IsActive) then
      this.BgTasks.Stop this  // The bgTask will be set to InActive after bgTask.Run returns.
      false
    else
      if not (this.BgTasks.Start(this)) then
        Console.WriteLine $"{this.Name} is already running."
      true

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
    bgTask.CTS <- new CancellationTokenSource()
    let wrapper() =
      Console.WriteLine $"  {bgTask.Name} starting"
      try
        bgTask.Run bgTask.CTS
      finally
        Console.WriteLine $"  {bgTask.Name} stopped"
        bgTasks.Remove bgTask |> ignore
        bgTask.CTS.Dispose()
        if NotActive = Interlocked.CompareExchange(&bgTask.Active, NotActive, IsActive) then
          Console.WriteLine $"  {bgTask.Name} stopped but was not active – can’t happen"
    Task.Run(wrapper) |> ignore

  let stop bgTask =
    if NotActive = Interlocked.CompareExchange(&bgTask.Active, IsActive, IsActive) then
      Console.WriteLine $"  {bgTask.Name} already stopped"
    else
    // bgTask is actually set to NotActive later when the BgTask has actually stopped.
    try
      bgTask.CTS.Cancel()
    with
    | :? ObjectDisposedException as e -> Console.WriteLine $"{bgTask.Name} trouble canceling: %A{e}."

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // members
  
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
    | None   ->
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
    | None        -> ()
    | Some bgTask ->
    stop bgTask

  /// <summary>
  /// Stops all running background tasks.
  /// </summary>
  member this.StopAll verbose =
    let bgTasksCopy = bgTasks |> Seq.toArray
    if bgTasksCopy.Length = 0 then
      if verbose then printfn "No tasks running."
    else
      for bgTask in bgTasksCopy do
        this.Stop bgTask
