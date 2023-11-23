module BeesLib.CbMessageWorkList

open System.Collections.Generic
open BeesLib.CbMessagePool


type WorkToDo = CbMessage -> unit
type WorkId   = WorkId of int
type WorkItem = WorkId * WorkToDo

type CbMessageWorkList() =
  
  let list = List<WorkItem>([||])
  let mutable idNext = 1


  /// This is the work to do immediately after each callback.
  /// There are no real-time restrictions on this work,
  /// since it is not called during the low-level PortAudio callback.
  member this.HandleCbMessage (m: CbMessage)  : unit =
    let workList = list.ToArray() // so a workItem can remove itself
    for (_, workToDo) in workList do
      workToDo m

  member this.RegisterWorkToDo(workToDo: WorkToDo)  : WorkItem =
    let workId   = WorkId idNext in idNext <- idNext + 1
    let workItem = workId, workToDo
    list.Add workItem
    workItem

  member this.UnregisterWorkToDo(workItem: WorkItem)  : unit =
    list.Remove workItem |> ignore
