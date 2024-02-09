module BeesUtil.Util

open System
open System.Threading
open System.Threading.Tasks


let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>


let printActualVsExpected actual expected message =
  let op = if actual = expected then "=" else "≠"
  printfn $"%d{actual} %s{op} %d{expected}  %s{message} actual%s{op}expeced"


let tryCatchRethrow f =
  try f()
  with ex ->
    printfn $"Exception: %s{ex.Message}"
    raise ex

let delayMs ms =
  Console.Write $"Delay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  Console.WriteLine "}"


let gc() =
  Console.Write "GC {"
  GC.Collect()
  Console.WriteLine "}"
  // GC.WaitForPendingFinalizers()
