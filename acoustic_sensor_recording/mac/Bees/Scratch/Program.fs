
open System.Runtime.InteropServices


type MyObj(v: int) =
    member val S = "x" 
    member val Value = v 

type MyStruct =
  struct
    val Value: MyObj
  end
  new(myObj: MyObj) = {Value = myObj}

let c = MyObj(42)
let s = MyStruct(c)

// Pin s in memory and get a pointer to it.
let handle = GCHandle.Alloc(s, GCHandleType.Pinned)
let pointer = handle.AddrOfPinnedObject()

printfn "Memory address of s: %A" pointer
printfn "Value of s.Value: %d" (Marshal.ReadInt32 pointer)

// Always free the handle once you are done using it.
handle.Free()
