module BeesLib.CbMessageWorkList

open BeesLib.CbMessagePool


type Unregistrar = unit -> unit 
type WorkId   = WorkId of int
type WorkFunc = CbMessage -> WorkId -> Unregistrar -> unit
and  WorkItem = WorkItem of (WorkId * WorkFunc)

type CbMessageWorkList() =
  
  let list = ResizeArray<WorkItem>()
  let mutable idCurrent = 0

  let nextWorkId() =
    idCurrent <- idCurrent + 1
    WorkId idCurrent

  let unregisterWorkItem workItem = list.Remove workItem |> ignore

  
  /// Run each registered post-callback workItem, not at interrupt time.
  member this.HandleCbMessage (m: CbMessage)  : unit =
    let workList = list.ToArray()
    for workItem in workList do
      let unregisterMe() = unregisterWorkItem workItem  
      match workItem with WorkItem (workId, workFunc) -> workFunc m workId unregisterMe

  /// Register a function to be called after every callback.
  member this.RegisterWorkItem(workFunc: WorkFunc)  : unit =
    let workItem = WorkItem (nextWorkId(), workFunc)
    list.Add workItem

  /// The number of registered WorkItems.
  member this.Count = list.Count