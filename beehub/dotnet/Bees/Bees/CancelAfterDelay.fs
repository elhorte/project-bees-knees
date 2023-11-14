module Bees.CancelAfterDelay

open System.Threading
open System.Threading.Tasks
open Microsoft.FSharp.Data.UnitSystems.SI.UnitNames

let cancelAfterDelay cts delaySec message =
  let cts = (cts: CancellationTokenSource)
  let worker() =
    let delayMs = (int (delaySec: float<second>)) * 1000
    task { do! Task.Delay delayMs } |> Task.WaitAll
    match message with Some s -> printfn $"{s}" | _ -> ()
    cts.Cancel()
  Task.Run worker
