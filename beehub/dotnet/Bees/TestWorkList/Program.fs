
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList

let cbMessage = createDummyCbMessage()

let handler (_: CbMessage) (workItem: WorkId) unregisterMe =
  match workItem with WorkId id ->  printfn "handling WorkId %d" id
  unregisterMe()

let workList = CbMessageWorkList()
printfn "%d" workList.Count

workList.HandleCbMessage cbMessage

workList.RegisterWorkItem handler
printfn "%d" workList.Count

workList.HandleCbMessage cbMessage
printfn "%d" workList.Count
