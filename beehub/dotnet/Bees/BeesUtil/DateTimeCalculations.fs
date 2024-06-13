module BeesUtil.DateTimeCalculations

open System

type RoundedDateTime =
| Good  of DateTime
| Error of string

//––––––––––––––––––––––––––––––––––––––––––––––––––––

module Utils =

  let roundAway value = Math.Round((value: float), MidpointRounding.AwayFromZero)

  let ticksPerMicrosecond = TimeSpan.TicksPerMillisecond / 1000L // 10
  let nsPerTick = 1000 / int ticksPerMicrosecond
  let nsToTicks ns = int64 (roundAway (float ns / float nsPerTick))  // ns 49 rounds to 0, ns 50 rounds to 100

  let day n = TimeSpan.FromDays         (float    n)
  let hr  n = TimeSpan.FromHours        (float    n)
  let min n = TimeSpan.FromMinutes      (float    n)
  let sec n = TimeSpan.FromSeconds      (float    n)
  let ms  n = TimeSpan.FromMilliseconds (float    n)
  let us  n = TimeSpan.FromMicroseconds (float    n)
  let ns  n = TimeSpan.FromTicks        (nsToTicks n)

  let tsNs (ts: TimeSpan) = int (ts.Ticks % TimeSpan.TicksPerSecond) * nsPerTick % 1000


//––––––––––––––––––––––––––––––––––––––––––––––––––––

module Calculations =

  open Utils

  let tsMalformedMessage = "TimeSpan is unsuitable for rounding"
  
  type UpDown = Up | Down

  // Used by roundUp and roundDown below.
  let roundToTimeSpan upDown (dt: DateTime) (ts: TimeSpan)  : RoundedDateTime =
    let tsToAddIfRoundUp = match upDown with Up -> ts | Down -> TimeSpan.Zero
    let newDt day hr min sec ms = DateTime(dt.Year, dt.Month, day, hr, min, sec, ms, dt.Kind) + tsToAddIfRoundUp
    let floor divisor n = n - (n % divisor)
    let err = Error tsMalformedMessage
    if   ts = TimeSpan.Zero        then                                         err
    elif ts.TotalDays         >= 1 then if ts.TotalDays         % 1.0 <> 0 then err else Good (newDt 1      0       0         0         0              + day (floor ts.Days         dt.Day        ))
    elif ts.TotalHours        >= 1 then if ts.TotalHours        % 1.0 <> 0 then err else Good (newDt dt.Day 0       0         0         0              + hr  (floor ts.Hours        dt.Hour       ))
    elif ts.TotalMinutes      >= 1 then if ts.TotalMinutes      % 1.0 <> 0 then err else Good (newDt dt.Day dt.Hour 0         0         0              + min (floor ts.Minutes      dt.Minute     ))
    elif ts.TotalSeconds      >= 1 then if ts.TotalSeconds      % 1.0 <> 0 then err else Good (newDt dt.Day dt.Hour dt.Minute 0         0              + sec (floor ts.Seconds      dt.Second     ))
    elif ts.TotalMilliseconds >= 1 then if ts.TotalMilliseconds % 1.0 <> 0 then err else Good (newDt dt.Day dt.Hour dt.Minute dt.Second 0              + ms  (floor ts.Milliseconds dt.Millisecond))
    elif ts.TotalMicroseconds >= 1 then if tsNs ts                    <> 0 then err else Good (newDt dt.Day dt.Hour dt.Minute dt.Second dt.Millisecond + us  (floor ts.Microseconds dt.Microsecond))
    else                                                                        err

  // Alternative way of coding this:
  
  // /// Classifies the given TimeSpan for rounding.
  // /// Requires exactly one nonzero value of Days, Hours, Minutes, Seconds, Milliseconds or Microseconds.
  // /// ts: The TimeSpan to classify.
  // /// returns: The classification of ts.
  // let (|Days|Hours|Minutes|Seconds|Milliseconds|Microseconds|Bad|) ts =  // Max 7 cases supported by the compiler
  //   if   ts = TimeSpan.Zero        then                                         Bad
  //   elif ts.TotalDays         >= 1 then if ts.TotalDays         % 1.0 <> 0 then Bad else Days         ts.Days
  //   elif ts.TotalHours        >= 1 then if ts.TotalHours        % 1.0 <> 0 then Bad else Hours        ts.Hours
  //   elif ts.TotalMinutes      >= 1 then if ts.TotalMinutes      % 1.0 <> 0 then Bad else Minutes      ts.Minutes
  //   elif ts.TotalSeconds      >= 1 then if ts.TotalSeconds      % 1.0 <> 0 then Bad else Seconds      ts.Seconds
  //   elif ts.TotalMilliseconds >= 1 then if ts.TotalMilliseconds % 1.0 <> 0 then Bad else Milliseconds ts.Milliseconds
  //   elif ts.TotalMicroseconds >= 1 then if tsNs ts                    <> 0 then Bad else Microseconds ts.Microseconds
  //   else                                                                        Bad
  //
  // let roundToTimeSpan upDown (dt: DateTime) (ts: TimeSpan)  : RoundedDateTime =
  //   let tsToAddIfRoundUp = match upDown with Up -> ts | Down -> TimeSpan.Zero
  //   let newDt day hr min sec ms = DateTime(dt.Year, dt.Month, day, hr, min, sec, ms, dt.Kind) + tsToAddIfRoundUp
  //   let floor divisor n = n - (n % divisor)
  //   match ts with
  //   | Days         n -> Good (newDt 1      0       0         0         0              + day (floor n dt.Day        ))
  //   | Hours        n -> Good (newDt dt.Day 0       0         0         0              + hr  (floor n dt.Hour       ))
  //   | Minutes      n -> Good (newDt dt.Day dt.Hour 0         0         0              + min (floor n dt.Minute     ))
  //   | Seconds      n -> Good (newDt dt.Day dt.Hour dt.Minute 0         0              + sec (floor n dt.Second     ))
  //   | Milliseconds n -> Good (newDt dt.Day dt.Hour dt.Minute dt.Second 0              + ms  (floor n dt.Millisecond))
  //   | Microseconds n -> Good (newDt dt.Day dt.Hour dt.Minute dt.Second dt.Millisecond + us  (floor n dt.Microsecond))
  //   | _              -> Error tsMalformedMessage

open Calculations

/// Rounds down a DateTime to the nearest interval specified by the given TimeSpan.
///
/// - Parameters:
///   - dateTime: The DateTime to be rounded up.
///   - timeSpan: The TimeSpan representing the interval to round down to.
/// - Returns: A RoundedDateTime value representing the rounded down DateTime or an error message if the TimeSpan is unsuitable for rounding.
let roundDown dateTime timeSpan  : RoundedDateTime = roundToTimeSpan Down dateTime timeSpan

/// Rounds up a DateTime to the nearest interval specified by the given TimeSpan.
///
/// - Parameters:
///   - dateTime: The DateTime to be rounded up.
///   - timeSpan: The TimeSpan representing the interval to round up to.
/// - Returns: A RoundedDateTime value representing the rounded up DateTime or an error message if the TimeSpan is unsuitable for rounding.
let roundUp   dateTime timeSpan  : RoundedDateTime = roundToTimeSpan Up   dateTime timeSpan
