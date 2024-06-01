module BeesUtil.CallbackHandoff

open System.Threading
open System.Threading.Tasks


/// Mechanism for calling managed code after each callback.
type CallbackHandoff = {
  F            : unit -> unit
  Semaphore    : SemaphoreSlim
  Cts          : CancellationTokenSource
  mutable Task : Task option } with
 
  /// <summary>
  /// Create a new instance.
  /// </summary>
  /// <param name="f">The function to call after each callback.</param>
  /// <returns>The new instance.</returns>
  static member New f = {
    F         = f
    Semaphore = new SemaphoreSlim(0)
    Cts       = new CancellationTokenSource()
    Task      = None }

  member private ch.doHandoffs() =
    let loop() = 
      while not ch.Cts.Token.IsCancellationRequested do
        ch.Semaphore.WaitAsync().Wait()
        ch.F()
      ch.Task <- None
    match ch.Task with
    | Some _ -> ()
    | None   -> ch.Task <- Some (Task.Run loop)

  /// Ensure that the background task is running.
  member ch.Start   () = ch.doHandoffs()
  
  /// Cancel the background task.
  member ch.Stop    () = ch.Cts.Cancel()
  
  // Signal the end of a callback, so the managed task will run.
  member ch.HandOff () = ch.Semaphore.Release() |> ignore
