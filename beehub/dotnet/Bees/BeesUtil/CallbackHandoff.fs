module BeesUtil.CallbackHandoff

open System.Threading
open System.Threading.Tasks


type CallbackHandoff = {
  F            : unit -> unit
  Semaphore    : SemaphoreSlim
  Cts          : CancellationTokenSource
  mutable Task : Task option } with
 
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
      ch.Semaphore.Dispose()
      ch.Cts      .Dispose()
      ch.Task <- None
    match ch.Task with
    | Some _ -> ()
    | None   -> ch.Task <- Some (Task.Run loop)

  member ch.Start   () = ch.doHandoffs()
  member ch.Stop    () = ch.Cts.Cancel()
  member ch.HandOff () = ch.Semaphore.Release() |> ignore

// type  CallbackHandoff(f: unit -> unit) =
//
//   let mutable semaphore = SemaphoreSlim(0)
//
//   let doHandoffs (token: CancellationToken) =
//     let handlerLoop() =
//       while not token.IsCancellationRequested do
//         semaphore.Wait()
//         f()
//     Task.Run(handlerLoop) |> ignore
//   
//   member this.Start(cts: CancellationTokenSource) = doHandoffs cts.Token
//   member this.Stop (cts: CancellationTokenSource) = cts.Cancel
//   
//   member this.HandOff() = semaphore.Release()


// type  CallbackHandoffWithTasks<'T>(f: 'T -> unit) =
//
//   let mutable tcs = TaskCompletionSource<'T>()
//
//   let doHandoffs (token: CancellationToken) =
//     let handlerLoop() = 
//       while not token.IsCancellationRequested do
//         let t = task {
//           let! result =
//             let r = tcs.Task
//             tcs <- TaskCompletionSource<'T>()
//             r
//           f result }
//         t.Wait()
//     Task.Run(handlerLoop) |> ignore
//   
//   member this.Start(cts: CancellationTokenSource) = doHandoffs cts.Token
//   
//   member this.HandOff(t: 'T) = tcs.SetResult(t)

