module BeesLib.Util


let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>


let printActualVsExpected actual expected message =
  let op = if actual = expected then "=" else "≠"
  printfn $"%d{actual} %s{op} %d{expected}  %s{message} actual%s{op}expeced"
