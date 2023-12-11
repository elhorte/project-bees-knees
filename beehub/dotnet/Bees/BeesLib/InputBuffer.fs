module BeesLib.InputBuffer

open System
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList

type Worker = Buf -> int -> int

type InputBuffer(timeSpan: TimeSpan, source: CbMessageWorkList) =
  
  let mutable earliest = DateTime.Now
  
  let callback (cbMessage: CbMessage) (workId: WorkId) (unsubscribeMe: Unsubscriber) =
    ()
    
  do
    source.Subscribe(callback)

  let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
    let now = DateTime.Now
    let beginDt =
      if   dateTime > now      then  now
      elif dateTime < earliest then  earliest
                               else  dateTime
    ()
    
  let keep (duration: TimeSpan) =
    assert (duration > TimeSpan.Zero)
    let now = DateTime.Now
    let dateTime = now - duration
    earliest <- 
      if dateTime < earliest then  earliest
                             else  dateTime
    earliest
    
  /// Reach back as close as possible to a time in the past.
  member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
    get dateTime duration worker

  /// Keep as much as possible of the given TimeSpan
  /// and return the start DateTime of what is currently kept.
  member this.Keep(duration: TimeSpan)  : DateTime = keep duration
