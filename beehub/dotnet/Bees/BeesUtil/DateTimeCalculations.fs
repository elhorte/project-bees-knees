module BeesUtil.DateTimeCalculations

open System
open System.Threading.Tasks

let getMostRecentSecondBoundary (sec: double) =
  let now = System.DateTime.Now
  now.AddSeconds(-double(now.Second % int sec))

let getNextSecondBoundary (sec: double) =
  let dt = getMostRecentSecondBoundary sec
  dt.AddSeconds(double sec)
    
let getMostRecentStartOfMinute (dt: DateTime) =
  dt.AddSeconds(-dt.Second)

let getMostRecentStartOfHour (dt: DateTime) =
  let dt = getMostRecentStartOfMinute dt
  dt.AddMinutes(-dt.Minute)

let waitUntil (future: DateTime) =
  let now = DateTime.Now
  let duration = future - now
  if duration > TimeSpan.Zero then  Task.Delay duration
                              else  Task.CompletedTask
