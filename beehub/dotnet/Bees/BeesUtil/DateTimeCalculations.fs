module BeesUtil.DateTimeCalculations

open System
open System.Threading.Tasks

open DateTimeDebugging
open BeesUtil.DateTimeShim

let addSeconds dateTime sec =
  let dateTime = (dateTime: _DateTime)
  if UsingFakeDateTime then  dateTime
                       else  dateTime.AddSeconds sec

let getMostRecentSecondBoundary sec (from: _DateTime) =
  addSeconds from (-double(from.Second % sec))

let getNextSecondBoundary sec (from: _DateTime) =
  let dt = getMostRecentSecondBoundary sec from
  addSeconds dt (double sec)
    
let getMostRecentStartOfMinute (dt: _DateTime) =
  addSeconds dt (-dt.Second)

let waitUntil dateTime =
  if UsingFakeDateTime then  ()
  else
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()
