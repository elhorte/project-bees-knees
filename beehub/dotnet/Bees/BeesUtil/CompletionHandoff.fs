module BeesUtil.CompletionHandoff

open System.Threading
open System.Threading.Tasks


type CompletionHandoff = {
  F         : unit -> unit
  Semaphore : SemaphoreSlim
  Cts       : CancellationTokenSource }

let handleCompletions (ch: CompletionHandoff) =
  let loop() =
    while not ch.Cts.Token.IsCancellationRequested do
      ch.Semaphore.Wait()
      ch.F()
    ch.Semaphore.Dispose()
    ch.Cts      .Dispose()
  Task.Run(loop) |> ignore

let start   (ch: CompletionHandoff) = handleCompletions ch
let stop    (ch: CompletionHandoff) = ch.Cts.Cancel()
let handOff (ch: CompletionHandoff) = ch.Semaphore.Release() |> ignore



// type CompletionHandoff(f: unit -> unit) =
//
//   let mutable semaphore = SemaphoreSlim(0)
//
//   let handleCompletions (token: CancellationToken) =
//     let handlerLoop() =
//       while not token.IsCancellationRequested do
//         semaphore.Wait()
//         f()
//     Task.Run(handlerLoop) |> ignore
//   
//   member this.Start(cts: CancellationTokenSource) = handleCompletions cts.Token
//   member this.Stop (cts: CancellationTokenSource) = cts.Cancel
//   
//   member this.HandOff() = semaphore.Release()


// type CompletionHandoffWithTasks<'T>(f: 'T -> unit) =
//
//   let mutable tcs = TaskCompletionSource<'T>()
//
//   let handleCompletions (token: CancellationToken) =
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
//   member this.Start(cts: CancellationTokenSource) = handleCompletions cts.Token
//   
//   member this.HandOff(t: 'T) = tcs.SetResult(t)

