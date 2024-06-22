
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

// A demo subscription handler function

let handler (_: InputStream) (id: SubscriptionId) unsubscribeMe =
  match id with SubscriptionId id ->  printfn "WorkItem %d runs and unsubscribes itself." id
  unsubscribeMe()


printHowManySubscribedHandlers 0

handleInputStream() // handler is not called bc it is not registered yet
printHowManySubscribedHandlers 0

let subscription = subscriberList.Subscribe handler
printHowManySubscribedHandlers 1

handleInputStream() // handler is called and unregisters itself
printHowManySubscribedHandlers 0

handleInputStream() // handler is not called bc it is no longer registered
printHowManySubscribedHandlers 0
