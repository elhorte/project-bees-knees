module BeesUtil.JobsManager

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks

open BeesUtil.Util

let IsActive  = 1L
let NotActive = 0L

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

/// A Task to be backgrounded
type Job = {
  Name           : string
  Run            : CancellationTokenSource -> unit
  JobsManager    : JobsManager
  mutable CTS    : CancellationTokenSource
  mutable Active : int64  }
with

  static member New jobsManager name runFunc =
    let (name: string) = name
    let (runFunc: CancellationTokenSource -> unit) = runFunc
    let job = {
      Name        = name
      Run         = runFunc
      JobsManager = jobsManager
      CTS         = new CancellationTokenSource()
      Active      = NotActive  }
    job.CTS.Dispose()
    Some job
  
  /// <summary>Starts/Stops a background task.</summary>
  /// <returns> true if it causes the job to start</returns>
  member this.Toggle()  : bool =
    if IsActive = Interlocked.CompareExchange(&this.Active, IsActive, IsActive) then
      this.JobsManager.Stop this  // The job will be set to InActive after job.Run returns.
      false
    else
      if not (this.JobsManager.Start(this)) then
        Console.WriteLine $"{this.Name} is already running."
      true

//–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

/// Represents a collection of background tasks, each with a name and a CancellationTokenSource.
/// Only one of each type of Job can be running.
and JobsManager() =
  
  let allJobs    = List<Job>()
  let activeJobs = List<Job>()
  
  let findActiveJob name = activeJobs |> Seq.tryFind (fun {Name = s} -> s = name)

  let start job =
    if IsActive = Interlocked.CompareExchange(&job.Active, IsActive, NotActive) then
      Console.WriteLine $"  {job.Name} already started"
    else
    activeJobs.Add job
    job.CTS <- new CancellationTokenSource()
    let wrapper() =
      Console.WriteLine $"  {job.Name} starting"
      try
        job.Run job.CTS
      finally
        Console.WriteLine $"  {job.Name} finished"
        activeJobs.Remove job |> ignore
        job.CTS.Dispose()
        if NotActive = Interlocked.CompareExchange(&job.Active, NotActive, IsActive) then
          Console.WriteLine $"  {job.Name} stopped but was not active – can’t happen"
    Task.Run(wrapper) |> ignore

  let stop job =
    if NotActive = Interlocked.CompareExchange(&job.Active, IsActive, IsActive) then
      Console.WriteLine $"  {job.Name} already stopped"
    else
    // job is actually set to NotActive later when the Job has actually stopped.
    try
      job.CTS.Cancel()
    with
    | :? ObjectDisposedException as e -> Console.WriteLine $"{job.Name} trouble canceling: %A{e}."

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // members
  
  /// <summary>
  /// Returns a sequence of names of running background tasks.
  /// </summary>
  member this.ListNames() =
    activeJobs
    |> Seq.map (fun {Name = s} -> s)
  
  /// <summary>
  /// Returns a Job by the given name.
  /// </summary>
  /// <returns>
  /// <c>Job option</c>
  /// </returns>
  member this.FindItem name =
    findActiveJob name
    
  /// <summary>Starts a background task if it is not already running.</summary>
  /// <param job="job">The <c>Job</c> to run.</param>
  /// <returns>A boolean, <c>true</c> if the task was started.</returns>
  member this.Start(job: Job) =
    match findActiveJob job.Name with
    | Some _ -> false
    | None   ->
    start job
    true

  /// <summary>
  /// Cancels and the <c>Job</c></c>.
  /// </summary>
  /// <param job="job">The <c>Job</c> to stop.</param>
  /// <remarks>
  /// If the <c>Job</c> is not running, the function does not perform any actions.
  /// The <c>Job</c> is removed from the list when it completes.
  /// </remarks>
  member this.Stop(job: Job) =
    let job = findActiveJob job.Name
    match job with
    | None        -> ()
    | Some job ->
    stop job

  /// <summary>
  /// Stops all running background tasks.
  /// </summary>
  member this.StopAll verbose  : bool =
    let jobsCopy = activeJobs |> Seq.toArray
    if jobsCopy.Length = 0 then
      if verbose then printfn "No tasks running."
      false
    else
      for job in jobsCopy do
        this.Stop job
      true

  /// <summary>
  /// Stops all running background tasks.
  /// </summary>
  member this.StopAllAndWait verbose =
    if this.StopAll verbose then
      printfn "Waiting for one or more tasks to stop." 
      while activeJobs.Count > 0 do (Task.Delay 1).Wait()
      if verbose then printfn "All tasks stopped."
