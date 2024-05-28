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

let truncateToSecond (d: _DateTime) =
  _DateTime(d.Year, d.Month, d.Day, d.Hour, d.Minute, d.Second)

let getMostRecentSecondBoundary sec (d: DateTime) = 
    addSeconds d ((float d.Second % float sec) * -1.0)
    |> truncateToSecond

let getNextSecondBoundary sec (from: _DateTime) =
  let dt = getMostRecentSecondBoundary sec from
  addSeconds dt (double sec)
    
let getMostRecentMinuteBoundary (dt: _DateTime) =
  addSeconds dt (-dt.Second)
