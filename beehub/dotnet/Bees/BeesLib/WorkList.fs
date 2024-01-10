module BeesLib.WorkList


type Unsubscriber = unit -> unit 
type WorkId       = WorkId of int

type WorkFunc<'T> = 'T -> WorkId -> Unsubscriber -> unit
and  WorkItem<'T> = WorkItem of (WorkId * WorkFunc<'T>)

type WorkList<'T>() =
  
  let subscriptions = ResizeArray<WorkItem<'T>>()
  let mutable idCurrent = 0

  let nextWorkId() =
    idCurrent <- idCurrent + 1
    WorkId idCurrent

  let unsubscribe workItem = subscriptions.Remove workItem |> ignore


  /// Run each subscribed post-callback workItem, not at interrupt time.
  member this.HandleItem(t: 'T)  : unit =
    let workList = subscriptions.ToArray()
    for workItem in workList do
      let unsubscribeMe() = unsubscribe workItem  
      match workItem with WorkItem (workId, workFunc) -> workFunc t workId unsubscribeMe

  /// Subscribe a function to be called after every callback.
  member this.Subscribe(workFunc: WorkFunc<'T>)  : unit =
    let workItem = WorkItem (nextWorkId(), workFunc)
    subscriptions.Add workItem

  /// The number of subscribed WorkItems.
  member this.Count = subscriptions.Count

