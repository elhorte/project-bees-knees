module BeesUtil.CancelAfterDelay

open System
open System.Threading
open System.Threading.Tasks
open Microsoft.FSharp.Data.UnitSystems.SI.UnitNames

let cancelAfterDelay cancellationTokenSource delay message =
  let cts = (cancellationTokenSource: CancellationTokenSource)
  let delayMs = (delay: TimeSpan).Milliseconds
  let worker() =
    task { do! Task.Delay delayMs } |> Task.WaitAll
    match message with Some s -> printfn $"{s}" | _ -> ()
    cts.Cancel()
  Task.Run worker
