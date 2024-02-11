module BeesUtil.Util

open System
open System.Threading.Tasks


//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let printActualVsExpected actual expected message =
  let op = if actual = expected then "=" else "≠"
  printfn $"%d{actual} %s{op} %d{expected}  %s{message} actual%s{op}expeced"

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let tryCatch f (die: exn -> unit) =
  try
    f()
  with
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    die ex
    raise ex

let tryCatchRethrow f = tryCatch f (fun e -> ()                 )
let tryCatchExit    f = tryCatch f (fun e -> Environment.Exit(2))

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let delayMs ms =
  Console.Write $"Delay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  Console.WriteLine "}"

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let gc() =
  Console.Write "GC {"
  GC.Collect()
  Console.WriteLine "}"
  // GC.WaitForPendingFinalizers()

//–––––––––––––––––––––––––––––––––––––––––––––––––––
