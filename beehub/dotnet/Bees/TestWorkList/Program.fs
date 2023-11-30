
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList


let workList = CbMessageWorkList()

let handleCbMessage() =
  dummyCbMessage() |> workList.HandleCbMessage

let workFunc (_: CbMessage) (workId: WorkId) unregisterMe =
  match workId with WorkId id ->  printfn "WorkItem %d runs and unregisters itself." id
  unregisterMe()

let printHowManyRegisteredHandlers() = printfn "%d" workList.Count


printHowManyRegisteredHandlers() // 0

handleCbMessage() // workFunc is not called bc it is not registered yet
printHowManyRegisteredHandlers() // 0

workList.RegisterWorkItem workFunc
printHowManyRegisteredHandlers() // 1

handleCbMessage() // workFunc is called and unregisters itself
printHowManyRegisteredHandlers() // 0

handleCbMessage() // workFunc is not called bc it is no longer registered
printHowManyRegisteredHandlers() // 0
