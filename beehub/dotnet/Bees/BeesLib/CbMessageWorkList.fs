module BeesLib.CbMessageWorkList

open BeesLib.CbMessagePool


type Unsubscriber = unit -> unit 
type WorkId   = WorkId of int
type WorkFunc = CbMessage -> WorkId -> Unsubscriber -> unit
and  WorkItem = WorkItem of (WorkId * WorkFunc)

type CbMessageWorkList() =
  
  let subscriptions = ResizeArray<WorkItem>()
  let mutable idCurrent = 0

  let nextWorkId() =
    idCurrent <- idCurrent + 1
    WorkId idCurrent

  let unsubscribe workItem = subscriptions.Remove workItem |> ignore

  
  /// Run each subscribed post-callback workItem, not at interrupt time.
  member this.HandleCbMessage(m: CbMessage)  : unit =
    let workList = subscriptions.ToArray()
    for workItem in workList do
      let unsubscribeMe() = unsubscribe workItem  
      match workItem with WorkItem (workId, workFunc) -> workFunc m workId unsubscribeMe

  /// Subscribe a function to be called after every callback.
  member this.Subscribe(workFunc: WorkFunc)  : unit =
    let workItem = WorkItem (nextWorkId(), workFunc)
    subscriptions.Add workItem

  /// The number of subscribed WorkItems.
  member this.Count = subscriptions.Count
