
open System
open System.Globalization
open System.Threading.Tasks

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
let roundDown dateTime timeSpan : RoundedDateTime = roundToTimeSpan Down dateTime timeSpan

/// Rounds up a DateTime to the nearest interval specified by the given TimeSpan.
///
/// - Parameters:
///   - dateTime: The DateTime to be rounded up.
///   - timeSpan: The TimeSpan representing the interval to round up to.
/// - Returns: A RoundedDateTime value representing the rounded up DateTime or an error message if the TimeSpan is unsuitable for rounding.
let roundUp   dateTime timeSpan : RoundedDateTime = roundToTimeSpan Up   dateTime timeSpan


//––––––––––––––––––––––––––––––––––––––––––––––––––––

open Utils

let dtToString (dt: DateTime) =
  let format = "yyyy-MM-dd HH:mm:ss.ffffff"
  let ns = nsPerTick * int (dt.Ticks % ticksPerMicrosecond)
  $"%s{dt.ToString(format)}_%03d{ns}"

let tsToString (ts: TimeSpan) =
    sprintf $"%d{ts.Days}.%02d{ts.Hours}:%02d{ts.Minutes}:%02d{ts.Seconds}.%03d{ts.Milliseconds}%03d{ts.Microseconds}_%d{int (ts.Ticks % 10L)}00"

//––––––––––––––––––––––––––––––––––––––––––––––––––––

module BadInputs =

  let data = [|
    day 1 + hr  1
    day 2 + min 1
    day 1 + sec 1
    day 3 + ms  1
    day 4 + us  1
    day 5 + ns 50 // ns 50 rounds to 100
    //–––––––––––
    hr  1 + min 1
    hr  1 + sec 1
    hr  1 + ms  1
    hr  1 + us  1
    hr  1 + ns 50
    //–––––––––––
    min 1 + sec 1
    min 1 + ms  1
    min 1 + us  1
    min 1 + ns 50
    //–––––––––––
    sec 1 + ms  1
    sec 1 + us  1
    sec 1 + ns 50
    //–––––––––––
    ms  1 + us  1
    ms  1 + ns 50
    //–––––––––––
    us  1 + ns 50
    //–––––––––––
    ns 50         |]

//––––––––––––––––––––––––––––––––––––––––––––––––––––

type TestMode =
  | PrintFailures
  | PrintAll

//––––––––––––––––––––––––––––––––––––––––––––––––––––

// module TestClassification =
//
//   type TSClass =
//     | CDays         of int
//     | CHours        of int
//     | CMinutes      of int
//     | CSeconds      of int
//     | CMilliseconds of int
//     | CMicroseconds of int
//     | CBad
//
//   let goodInputs() = [|
//     day  7        , CDays          7
//     hr   8        , CHours         8
//     min  6        , CMinutes       6
//     sec 10        , CSeconds      10
//     ms  10        , CMilliseconds 10
//     us  20        , CMicroseconds 20
//     us  20 + ns 49, CMicroseconds 20 |] // ns 49 rounds to 0
//
//   let badInputs() =
//     BadInputs.data
//     |> Array.map (fun input -> input, CBad)
//
//   let check writer testMode result =
//     let ts,expected,actual = result
//     let passed = actual = expected
//     if not passed  ||  testMode = PrintAll then
//       let ok = if passed then  " √" else  "# "
//       let sTsInput = $"%s{tsToString ts}"
//       fprintf writer $"%s{ok} classify  %-22s{sTsInput} "
//       let printResult result =
//         match result with
//         | CDays         n -> fprintf writer $"%d{n} Days"
//         | CHours        n -> fprintf writer $"%d{n} Hours"
//         | CMinutes      n -> fprintf writer $"%d{n} Minutes"
//         | CSeconds      n -> fprintf writer $"%d{n} Seconds"
//         | CMilliseconds n -> fprintf writer $"%d{n} Milliseconds"
//         | CMicroseconds n -> fprintf writer $"%d{n} Microseconds"
//         | CBad            -> fprintf writer $"bad"
//       printResult actual
//       if not passed then
//         fprintf writer "          –– expected: "
//         printResult expected
//       fprintfn writer ""
//
//   type InputAndExpected    = TimeSpan * TSClass
//   type InputExpectedActual = TimeSpan * TSClass * TSClass
//
//   let test writer testMode =
//     let classifyOne (input: InputAndExpected)  : InputExpectedActual =
//       let classify ts =
//         match ts with
//         | Days         n -> CDays    n
//         | Hours        n -> CHours   n
//         | Minutes      n -> CMinutes n
//         | Seconds      n -> CSeconds n
//         | Milliseconds n -> CMilliseconds n
//         | Microseconds n -> CMicroseconds n
//         | Bad            -> CBad
//       let ts,expected = input
//       let actual = ts |> classify
//       ts,expected,actual
//     let checkOne (result: InputExpectedActual)  : unit =
//       check writer testMode result
//     let runAll generator =
//       generator()
//       |> Seq.map  classifyOne
//       |> Seq.iter checkOne
//     runAll goodInputs
//     runAll badInputs


//––––––––––––––––––––––––––––––––––––––––––––––––––––

module TestRounding =

  let format = "M/d/yyyy HH:mm:ss.ffffff"
  let provider = CultureInfo.InvariantCulture
  let parseDT s nsArg = DateTime.ParseExact(s, format, provider) + ns nsArg
  let start = parseDT "02/13/0001 10:09:14.123456" 250

  let goodInputsDown = [|
    (start, day  7        ), Good (parseDT "02/08/0001 00:00:00.000000" 0)
    (start, hr   8        ), Good (parseDT "02/13/0001 08:00:00.000000" 0)
    (start, min  6        ), Good (parseDT "02/13/0001 10:06:00.000000" 0)
    (start, sec 10        ), Good (parseDT "02/13/0001 10:09:10.000000" 0)
    (start, ms  10        ), Good (parseDT "02/13/0001 10:09:14.120000" 0)
    (start, us  20        ), Good (parseDT "02/13/0001 10:09:14.123440" 0)
    (start, us  20 + ns 49), Good (parseDT "02/13/0001 10:09:14.123440" 0)  |]

  let goodInputsUp = [|
    (start, day  7        ), Good (parseDT "02/15/0001 00:00:00.000000" 0)
    (start, hr   8        ), Good (parseDT "02/13/0001 16:00:00.000000" 0)
    (start, min  6        ), Good (parseDT "02/13/0001 10:12:00.000000" 0)
    (start, sec 10        ), Good (parseDT "02/13/0001 10:09:20.000000" 0)
    (start, ms  10        ), Good (parseDT "02/13/0001 10:09:14.130000" 0)
    (start, us  20        ), Good (parseDT "02/13/0001 10:09:14.123460" 0)
    (start, us  20 + ns 49), Good (parseDT "02/13/0001 10:09:14.123460" 0)  |]

  let badInputs =
    BadInputs.data
    |> Array.map (fun ts -> (start, ts), Error tsMalformedMessage)

  let check writer msg testMode result =
    let (dt,ts),expected,actual = result
    let passed = actual = expected
    if not passed  ||  testMode = PrintAll then
      let ok = if passed then  " √" else  "# "
      let sTsInput = $"%s{tsToString ts}"
      fprintf writer $"%s{ok} %-5s{msg} %-22s{sTsInput} "
      let printResult result =
        match result with
        | Good  dt  -> fprintf writer $"%s{dtToString dt}"
        | Error s   -> fprintf writer $"%s{s}"
      printResult actual
      if not passed then
        fprintf writer "       –– expected: "
        printResult expected
      fprintfn writer ""

  type InputAndExpected    = (DateTime * TimeSpan) * RoundedDateTime
  type InputExpectedActual = (DateTime * TimeSpan) * RoundedDateTime * RoundedDateTime

  let test writer upOrDown testMode =
    let round =
      match upOrDown with
      | "down" -> roundDown
      | "up  " -> roundUp
      | "bad "
      | _      -> roundDown
    let roundOne (input: InputAndExpected)  : InputExpectedActual =
      let (dt, ts), expected = input
      let actual = ts |> round dt
      (dt,ts),expected,actual
    let checkOne (result: InputExpectedActual)  : unit =
      check writer upOrDown testMode result
    let runAll source =
      source
      |> Array.map  roundOne
      |> Array.iter checkOne
    match upOrDown with
    | "down" -> runAll goodInputsDown
    | "up  " -> runAll goodInputsUp
    | "bad "
    | _      -> runAll badInputs


//––––––––––––––––––––––––––––––––––––––––––––––––––––

module RunPeriodically =

  let waitUntil dateTime =
    let duration = dateTime - DateTime.Now
    if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()

  let test writer period count =
    let now = DateTime.Now
    match roundUp now period with
    | Error s -> failwith s
    | Good startTime ->
    fprintfn writer $"from now %A{tsToString now.TimeOfDay}, wait %s{tsToString (startTime - DateTime.Now)}"
    let rec next (dt: DateTime) count =
      if count <= 0 then ()
      else
      waitUntil (dt + period)
      fprintfn writer $"%s{tsToString dt.TimeOfDay}"
      let count' = count - 1
      next (dt + period) count'
    next startTime count


//––––––––––––––––––––––––––––––––––––––––––––––––––––

type Output = Stdout | File of string

//––––––––––––––––––––––––––––––––––––––––––––––––––––

[<EntryPoint>]
let main argv =
  let testMode = match 2 with | 1 -> PrintFailures | 2 -> PrintAll       | _ -> failwith "bad choice"
  let output   = match 1 with | 1 -> Stdout        | 2 -> File "out.txt" | _ -> failwith "bad choice"
  use writer =
    match output with
    | Stdout    ->  Console.Out
    | File path ->  new IO.StreamWriter(path)
  let nl() = fprintfn writer ""
  fprintfn writer "TestMode is %A" testMode
  fprintfn writer "Output   is %A" output
//nl() ; TestClassification.test writer testMode
  nl() ; fprintfn writer $"start is %A{dtToString TestRounding.start}"
  nl() ; TestRounding.test writer "down" testMode
  nl() ; TestRounding.test writer "up  " testMode
  nl() ; TestRounding.test writer "bad " testMode
  nl() ; RunPeriodically.test writer (TimeSpan.FromSeconds 2) 3
  0
