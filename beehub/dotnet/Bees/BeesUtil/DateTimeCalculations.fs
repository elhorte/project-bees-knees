module BeesUtil.DateTimeCalculations

open System
open System.Threading.Tasks

open BeesUtil.DateTimeShim

let addSeconds dateTime sec =
  let dateTime = (dateTime: _DateTime)
#if USE_FAKE_DATE_TIME
  dateTime
#else
  dateTime.AddSeconds sec
#endif

let getMostRecentSecondBoundary sec (from: _DateTime) =
  addSeconds from (-double(from.Second % sec))

let getNextSecondBoundary sec (from: _DateTime) =
  let dt = getMostRecentSecondBoundary sec from
  addSeconds dt (double sec)
    
let getMostRecentMinuteBoundary (dt: _DateTime) =
  addSeconds dt (-dt.Second)


// // needs work
// /// Classifies the given TimeSpan for use as a repeating interval.
// /// A TimeSpan is good only if 
// ///
// /// t: The TimeSpan to classify.
// /// returns: The classification of t.
// let (|Seconds|Minutes|Hours|Days|Years|Bad|) t =
//   match (t: TimeSpan) with
//   | _ when t = TimeSpan.Zero    -> Bad
//   | _ when t.TotalDays    =  0         -> Years   t
//   | _ when t.TotalHours   =  0         -> Days    t
//   | _ when t.TotalDays    <> 0  -> Bad
//   | _ when t.TotalMinutes =  0         -> Hours   t
//   | _ when t.TotalHours   <> 0  -> Bad
//   | _ when t.TotalSeconds =  0         -> Minutes t
//   | _ when t.TotalMinutes <> 0  -> Bad
//   | _ when t.TotalSeconds =  t.Seconds -> Seconds t
//   | _ -> Bad
//
// let t1 = TimeSpan.FromDays 400 in match t1 with Bad -> false | _ _ -> true |> printfn "%A" 
// let getMostRecentBoundary (d: DateTime) (t1: TimeSpan) =
//   match t1 with 
//   | Bad        -> None
//   | Years    t
//   | Days     t
//   | Hours    t -> None
//   | Minutes  t -> Some getMostRecentMinuteBoundary d t.Minutes
//   | Seconds  t -> Some getMostRecentSecondBoundary d t.Seconds


let waitUntil dateTime =
#if USE_FAKE_DATE_TIME
  ()
#else
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()
#endif
