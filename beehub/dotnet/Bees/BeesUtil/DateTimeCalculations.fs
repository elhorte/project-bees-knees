module BeesUtil.DateTimeCalculations

open System
open System.Threading.Tasks

open BeesUtil.DateTimeShim

let getMostRecentSecondBoundary sec (from: _DateTime) =
  from.AddSeconds(-double(from.Second % sec))

let getNextSecondBoundary sec (from: _DateTime) =
  let dt = getMostRecentSecondBoundary sec from
  dt.AddSeconds(double sec)
    
let getMostRecentStartOfMinute (dt: _DateTime) =
  dt.AddSeconds(-dt.Second)

let getMostRecentStartOfHour (dt: _DateTime) =
  let dt = getMostRecentStartOfMinute dt
  dt.AddMinutes(-dt.Minute)

let waitUntil dateTime =
  let duration = dateTime - _DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()
