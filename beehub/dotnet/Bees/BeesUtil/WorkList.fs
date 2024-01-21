module BeesUtil.WorkList

open System.Threading
open System.Threading.Tasks
open FSharp.Control
open System.Linq

/// A subscription service for a generic event

type Unsubscriber   = unit -> unit 
type SubscriptionId = SubscriptionId of int

type SubscriberHandler<'Event> = 'Event -> SubscriptionId -> Unsubscriber -> unit
and  Subscription<'Event>   = Subscription of (SubscriptionId * SubscriberHandler<'Event>)


type WorkList<'Event>() =
  
  let subscriptions = ResizeArray<Subscription<'Event>>()
  let mutable idCurrent = 0

  let nextId() =
    idCurrent <- idCurrent + 1
    SubscriptionId idCurrent

  let unsubscribe subscription = subscriptions.Remove subscription |> ignore

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // members
  
  /// Handle the event by running each subscription in order subscribed.
  /// The subscriber handler can remove itself when done.
  member this.HandleEvent(t: 'Event)  : unit =
    for s in subscriptions.ToArray() do
      let unsubscribeMe() = unsubscribe s  
      match s with
      | Subscription (id, handler) -> handler t id unsubscribeMe

  /// Subscribe a handler to be called every time an Event is handled.
  member this.Subscribe(handler: SubscriberHandler<'Event>)  : Subscription<'Event> =
    let s = Subscription (nextId(), handler)
    subscriptions.Add s
    s

  /// Unsubscribe.
  member this.Unsubscribe(s: Subscription<'Event>)  : bool =
    subscriptions.Remove s

  /// The number of subscriptions.
  member this.SubscriberCount = subscriptions.Count
