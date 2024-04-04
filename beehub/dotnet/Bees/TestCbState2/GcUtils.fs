module TestCbState.GcUtils

open System
open System.Threading.Tasks


let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait() |> ignore
  if print then Console.Write "}"

let awaitForever() = delayMs false Int32.MaxValue


// A function to consume a lot of memory quickly
let consumeMemory count =
  let rec addSome acc count =
    match count with
    | 0 ->
      acc
    | _ ->
      let acc' = "" :: acc
      addSome acc' (count - 1)
  addSome [] count
  // let mutable data = []
  // data <- (Array.init 1 (fun _ -> "")) :: data
  // Create objects in a list, then discard them.
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> Guid.NewGuid().ToString())) :: data
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> "")) :: data
  // Here, 'data' goes out of scope and becomes eligible for garbage collection

let gcN() =
  Console.Write "\nGC {"
  GC.Collect()
  let nBytes = GC.GetTotalMemory false
  Console.Write $"{nBytes:N0}}}"
  // GC.WaitForPendingFinalizers()
  nBytes

let gc() = gcN |> ignore


let churnGc count =
  let rec foo acc n =
    match n with
    | 0                           -> ()
    | _ when gcN() > 2_000_000_000 -> ()
    | _ ->
      let acc' = consumeMemory 1_000_000 :: acc
      foo acc' (n - 1)
  Console.WriteLine "Churn starting"
  while true do foo [] count
  delayMs true 300
  // GC.WaitForPendingFinalizers()
  Console.Write "\nChurn done."
