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

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let day n = TimeSpan.FromDays    n
let hr  n = TimeSpan.FromHours   n
let min n = TimeSpan.FromMinutes n
let sec n = TimeSpan.FromSeconds n

type TsClassification = Choice<int, int, int, int, unit, unit>

/// Classifies the given TimeSpan for use as a repeating interval.
/// Requires a nonzero integer in exactly one of Days, Hours, Minutes, or Seconds.
/// ts: The TimeSpan to classify.
/// returns: The classification of ts.
let (|Days|Hours|Minutes|Seconds|Zero|Bad|) ts  : TsClassification =
  match (ts: TimeSpan) with
  | _ when ts = TimeSpan.Zero                                     -> Zero
  | _ when ts.TotalDays    >= 1.0  &&  ts.TotalDays    % 1.0 = 0  -> Days    ts.Days
  | _ when ts.TotalHours   >= 1.0  &&  ts.TotalHours   % 1.0 = 0  -> Hours   ts.Hours  
  | _ when ts.TotalMinutes >= 1.0  &&  ts.TotalMinutes % 1.0 = 0  -> Minutes ts.Minutes
  | _ when ts.TotalSeconds >= 1.0  &&  ts.TotalSeconds % 1.0 = 0  -> Seconds ts.Seconds
  | _ -> Bad

let getPreviousBoundary (dt: DateTime) (ts: TimeSpan)  : DateTime option =
  match ts with
  | Days     d -> Some (dt - day (float (    dt.Day    % d)) - sec dt.Second - min dt.Minute - hr dt.Hour)
  | Hours    h -> Some (dt - hr  (float (    dt.Hour   % h)) - sec dt.Second - min dt.Minute)
  | Minutes  m -> Some (dt - min (float (    dt.Minute % m)) - sec dt.Second)
  | Seconds  s -> Some (dt - sec (float (    dt.Second % s)))
  | _          -> None

let getNextBoundary (dt: DateTime) (ts: TimeSpan)  : DateTime option =
  match ts with
  | Days     d -> Some (dt + day (float (d - dt.Day    % d)) - sec dt.Second - min dt.Minute - hr dt.Hour)
  | Hours    h -> Some (dt + hr  (float (h - dt.Hour   % h)) - sec dt.Second - min dt.Minute)
  | Minutes  m -> Some (dt + min (float (m - dt.Minute % m)) - sec dt.Second)
  | Seconds  s -> Some (dt + sec (float (s - dt.Second % s)))
  | _          -> None