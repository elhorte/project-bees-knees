module BeesLib.Util


let printActualVsExpected actual expected message =
  let op = if actual = expected then "=" else "≠"
  printfn $"%d{actual} %s{op} %d{expected}  %s{message} actual%s{op}expeced"
