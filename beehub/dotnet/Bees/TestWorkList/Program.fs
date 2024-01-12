
open BeesLib.CbMessagePool
open BeesLib.WorkList
open BeesLib.Util


let workList = WorkList<CbMessage>()

// Exercising

let handleCbMessage() =
  dummyInstance<CbMessage>() |> workList.HandleItem

let printHowManySubscribedHandlers expected =
  printActualVsExpected workList.SubscriberCount expected "workList.Count"

// A demo func to be registered

let workFunc (_: CbMessage) (workId: SubscriptionId) unsubscribeMe =
  match workId with SubscriptionId id ->  printfn "WorkItem %d runs and unsubscribes itself." id
  unsubscribeMe()


printHowManySubscribedHandlers 0

handleCbMessage() // workFunc is not called bc it is not registered yet
printHowManySubscribedHandlers 0

workList.Subscribe workFunc
printHowManySubscribedHandlers 1

handleCbMessage() // workFunc is called and unregisters itself
printHowManySubscribedHandlers 0

handleCbMessage() // workFunc is not called bc it is no longer registered
printHowManySubscribedHandlers 0
