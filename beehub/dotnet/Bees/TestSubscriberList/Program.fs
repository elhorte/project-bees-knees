
open BeesLib.CbMessagePool
open BeesUtil.SubscriberList
open BeesUtil.Util


let subscriberList = SubscriberList<CbMessage>()

// Exercising

let handleCbMessage() =
  dummyInstance<CbMessage>() |> subscriberList.Broadcast

let printHowManySubscribedHandlers expected =
  printActualVsExpected subscriberList.SubscriberCount expected "subscriberList.Count"

// A demo func to be registered

let workFunc (_: CbMessage) (workId: SubscriptionId) unsubscribeMe =
  match workId with SubscriptionId id ->  printfn "WorkItem %d runs and unsubscribes itself." id
  unsubscribeMe()


printHowManySubscribedHandlers 0

handleCbMessage() // workFunc is not called bc it is not registered yet
printHowManySubscribedHandlers 0

let subscription = subscriberList.Subscribe workFunc
printHowManySubscribedHandlers 1

handleCbMessage() // workFunc is called and unregisters itself
printHowManySubscribedHandlers 0

handleCbMessage() // workFunc is not called bc it is no longer registered
printHowManySubscribedHandlers 0
