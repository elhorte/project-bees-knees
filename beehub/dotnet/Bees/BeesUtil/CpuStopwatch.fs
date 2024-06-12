namespace CpuStopwatch

open System
open System.Diagnostics

type Options = Total | User
type State = Stopped | Running

/// CPU time measurer.
type CpuStopwatch(showTotal :Options) =

  let proc = Process.GetCurrentProcess()

  let now() =
    match showTotal with
    | Total -> proc.TotalProcessorTime
    | User  -> proc.UserProcessorTime

  let mutable state         = Stopped
  let mutable latestNow     = now()
  let mutable latestElapsed = TimeSpan.Zero

  let elapsed() =
    match state with
    | Stopped -> latestElapsed
    | Running -> latestElapsed + now() - latestNow

  let start() = if state = Stopped then latestNow     <- now    () ; state <- Running
  let stop () = if state = Running then latestElapsed <- elapsed() ; state <- Stopped
  
  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // members
  
  member this.Elapsed    with get() = elapsed()
  member this.IsRunning  with get() = state = Running
  member this.IsStopped  with get() = state = Stopped
  
  member this.Start() = start()
  member this.Stop () = stop ()

  static member TimeIt f =
    let sw = CpuStopwatch User
    sw.Start()
    let result = f()
    sw.Stop()
    let ms = string (int sw.Elapsed.TotalMilliseconds)
    Console.WriteLine $"\nCpuStopwatch elapsed milliseconds: {ms}"
    result
