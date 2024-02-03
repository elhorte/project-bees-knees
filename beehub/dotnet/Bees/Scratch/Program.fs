
open System

let printMemory x =
  let p = System.Diagnostics.Process.GetCurrentProcess()
  p.Refresh()
  printfn "Memory: %4d for %A" p.PrivateMemorySize64 x

let test x =

  // Start recording
  printMemory x

  let y = Some x // Some x on heap

  // End Recording
  printMemory x
 
let x1 = 1
let x2 = "s"
let x3 = (Object())

test x1
test x2
test x3

printfn "%A" [x1, x2, x3]


// Output:
// Memory:    0 for 1
// Memory:    0 for 1
// Memory:    0 for "s"
// Memory:    0 for "s"
// Memory:    0 for System.Object
// Memory:    0 for System.Object
