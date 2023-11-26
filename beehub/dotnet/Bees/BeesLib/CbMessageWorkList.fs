module BeesLib.CbMessageWorkList

open System.Collections.Generic
open BeesLib.CbMessagePool


type Unregistrar = unit -> unit 
type WorkId   = WorkId of int
type WorkFunc = CbMessage -> WorkId -> Unregistrar -> unit
and  WorkItem = WorkItem of (WorkId * WorkFunc)

type CbMessageWorkList() =
  
  let list = ResizeArray<WorkItem>()
  let mutable idLatest = 0

  let nextWorkId() =
    idLatest <- idLatest + 1
    WorkId idLatest

  let unregisterWorkItem workItem = list.Remove workItem |> ignore

  /// Do the registered work post-callback, at non-interrupt time.
  member this.HandleCbMessage (m: CbMessage)  : unit =
    let workList = list.ToArray()
    for workItem in workList do
      let unregisterMe() = unregisterWorkItem workItem  
      match workItem with WorkItem (workId, f) -> f m workId unregisterMe

  /// Register a function to be called after every callback
  member this.RegisterWorkItem(workFunc: WorkFunc) =
    let workItem = WorkItem (nextWorkId(), workFunc)
    list.Add workItem

  // The number of registered WorkItems.
  member this.Count = list.Count