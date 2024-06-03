
open BeesUtil.SubscriberList
open BeesUtil.Util
open BeesLib.InputStream


let subscriberList = SubscriberList<InputStream>()

// Exercising

let handleInputStream() =
  dummyInstance<InputStream>()
  |> subscriberList.Broadcast

let printHowManySubscribedHandlers expected =
  printActualVsExpected subscriberList.SubscriberCount expected "subscriberList.Count"

// A demo func to be registered

let workFunc (_: InputStream) (workId: SubscriptionId) unsubscribeMe =
  match workId with SubscriptionId id ->  printfn "WorkItem %d runs and unsubscribes itself." id
  unsubscribeMe()


printHowManySubscribedHandlers 0

handleInputStream() // workFunc is not called bc it is not registered yet
printHowManySubscribedHandlers 0

let subscription = subscriberList.Subscribe workFunc
printHowManySubscribedHandlers 1

handleInputStream() // workFunc is called and unregisters itself
printHowManySubscribedHandlers 0

handleInputStream() // workFunc is not called bc it is no longer registered
printHowManySubscribedHandlers 0
