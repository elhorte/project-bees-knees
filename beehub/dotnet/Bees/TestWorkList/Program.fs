
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList


let handle (m: CbMessage) = ()

let workList = CbMessageWorkList()

let item = workList.RegisterWorkToDo handle

workList.UnregisterWorkToDo item
