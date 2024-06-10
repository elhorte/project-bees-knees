
open System
open BeesUtil.Synchronizer

type Values = {
  mutable I : int  }
with

  member this.Copy() = { I = this.I }

type FooState = {
  mutable V1           : Values
  mutable V2           : Values
  mutable Synchronizer : Synchronizer }
with

  member cbs.Copy() = { cbs with V1 = cbs.V1.Copy() ; V2 = cbs.V2.Copy() }


// This is a class
type Foo() =

  let fooState = {
    V1           = { I = 0 }
    V2           = { I = 0 }
    Synchronizer = Synchronizer.New()  }
  
  member val FS = fooState
  
  member this.CbStateSnapshot timeout  : SynchronizerResult<FooState> =
    let copyFS() = this.FS.Copy()
    this.FS.Synchronizer.WhenStable timeout copyFS



[<EntryPoint>]
let main _ =
  let foo = Foo()
  let incrN1() = foo.FS.Synchronizer.EnterUnstable()
  let incrN2() = foo.FS.Synchronizer.LeaveUnstable()
  let timeout = TimeSpan.FromMilliseconds 10
  let doWork() = "work"
  incrN1()
  incrN2()

  let test work =
    match foo.FS.Synchronizer.WhenStableInternal false timeout work 3 Console.WriteLine with
    | Stable result ->  printfn "%A" result
    | TimedOut s    ->  printfn $"Timed out %s{s}"

  printfn "– success"
  test doWork

  printfn "– stuck in unstable"
  incrN1()
  test doWork
  incrN2()

  printfn "– work interrupted"
  test incrN1
  incrN2()
  
  printfn "– can’t happen"
  test incrN2

  0

(*

– success
"work"
– stuck in unstable
Trying again while unstable
Trying again while unstable
Trying again while unstable
Timed out while unstable
– work interrupted
Trying again while working
Trying again while unstable
Trying again while unstable
Timed out while unstable
– can’t happen
Unhandled exception. System.Exception: SeqSums: N1 ok but N2 changed while running the function

*) 