module BeesUtil.SubscriberList


type Unsubscriber   = unit -> unit 
type SubscriptionId = SubscriptionId of int

type SubscriberHandler<'Event> = 'Event -> SubscriptionId -> Unsubscriber -> unit
and  Subscription<'Event>      = Subscription of (SubscriptionId * SubscriberHandler<'Event>)


/// A subscription service for a generic event.
/// A subscribed event handler can remove itself when done.
type SubscriberList<'Event>() =
  
  let         subscriptions = ResizeArray<Subscription<'Event>>()
  let mutable idCurrent     = 0

  let nextId() =
    idCurrent <- idCurrent + 1
    SubscriptionId idCurrent

  let unsubscribe subscription = subscriptions.Remove subscription |> ignore

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // members
  
  /// Handles the event by running each subscription in order subscribed.
  member this.Broadcast(t: 'Event)  : unit =
    for s in subscriptions.ToArray() do
      let unsubscribeMe() = unsubscribe s  
      match s with
      | Subscription (id, handler) -> handler t id unsubscribeMe

  /// Subscribes a handler to be called every time an Event is handled.
  member this.Subscribe(handler: SubscriberHandler<'Event>)  : Subscription<'Event> =
    let s = Subscription (nextId(), handler)
    subscriptions.Add s
    s

  /// Unsubscribes a handler.
  member this.Unsubscribe(s: Subscription<'Event>)  : bool =
    subscriptions.Remove s

  /// Returns the number of subscriptions.
  member this.SubscriberCount = subscriptions.Count