module BeesUtil.DateTimeCalculations

open System
open System.Globalization
open System.Threading.Tasks

type RoundedDateTime =
| Good  of DateTime
| Error of string

let roundAway value = Math.Round((value: float), MidpointRounding.AwayFromZero)

module Utils = 
  let ticksPerMicrosecond = TimeSpan.TicksPerMillisecond / 1000L // 10
  let nsPerTick = 1000 / int ticksPerMicrosecond

  let day n = TimeSpan.FromDays         (float n)
  let hr  n = TimeSpan.FromHours        (float n)
  let min n = TimeSpan.FromMinutes      (float n)
  let sec n = TimeSpan.FromSeconds      (float n)
  let ms  n = TimeSpan.FromMilliseconds (float n)
  let us  n = TimeSpan.FromMicroseconds (float n)
  let ns  n = TimeSpan.FromTicks        (int64 (roundAway (float n / float nsPerTick)))

  let dtNs (dt: DateTime) = int (dt.Ticks % TimeSpan.TicksPerSecond) * nsPerTick % 1000
  let tsNs (ts: TimeSpan) = int (ts.Ticks % TimeSpan.TicksPerSecond) * nsPerTick % 1000

  let tsMalformedMessage = "TimeSpan is unsuitable for rounding"

  /// Classifies the given TimeSpan for rounding.
  /// Requires exactly one nonzero value of Days, Hours, Minutes, or Seconds.
  /// ts: The TimeSpan to classify.
  /// returns: The classification of ts.
  let (|Days|Hours|Minutes|Seconds|Milliseconds|Microseconds|Bad|) ts =  // Max 7 cases supported by the compiler
    match ts with
    | _ when ts = TimeSpan.Zero          -> Bad
    | _ when ts.TotalDays         >= 1.0         &&  ts.TotalDays         % 1.0 = 0  -> Days         ts.Days
    | _ when ts.TotalDays         >= 1.0 -> Bad                                       
    | _ when ts.TotalHours        >= 1.0         &&  ts.TotalHours        % 1.0 = 0  -> Hours        ts.Hours
    | _ when ts.TotalHours        >= 1.0 -> Bad                                         
    | _ when ts.TotalMinutes      >= 1.0         &&  ts.TotalMinutes      % 1.0 = 0  -> Minutes      ts.Minutes
    | _ when ts.TotalMinutes      >= 1.0 -> Bad                                       
    | _ when ts.TotalSeconds      >= 1.0         &&  ts.TotalSeconds      % 1.0 = 0  -> Seconds      ts.Seconds
    | _ when ts.TotalSeconds      >= 1.0 -> Bad                                       
    | _ when ts.TotalMilliseconds >= 1.0         &&  ts.TotalMilliseconds % 1.0 = 0  -> Milliseconds ts.Milliseconds
    | _ when ts.TotalMilliseconds >= 1.0 -> Bad                                       
    | _ when ts.TotalMicroseconds >= 1.0         &&  tsNs ts                    = 0  -> Microseconds ts.Microseconds
    | _ when ts.TotalMicroseconds >= 1.0 -> Bad                                       
    | _                                  -> Bad

  type UpDown = Up | Down

  let roundToInterval upDown (dt: DateTime) (ts: TimeSpan)  : RoundedDateTime =
    let tsIfUp = match upDown with Up -> ts | Down -> TimeSpan.Zero
    let dateTime y M d h m s k  = DateTime(y, M, d, h, m, s, k, dt.Kind) + tsIfUp
    let floor divisor n = n - (n % divisor)
    match ts with
    | Days         n -> Good ((dateTime dt.Year dt.Month 1      0       0         0         0             ) + day (floor n dt.Day        ))
    | Hours        n -> Good ((dateTime dt.Year dt.Month dt.Day 0       0         0         0             ) + hr  (floor n dt.Hour       ))
    | Minutes      n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour 0         0         0             ) + min (floor n dt.Minute     ))
    | Seconds      n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute 0         0             ) + sec (floor n dt.Second     ))
    | Milliseconds n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute dt.Second 0             ) + ms  (floor n dt.Millisecond)) 
    | Microseconds n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute dt.Second dt.Millisecond) + us  (floor n dt.Microsecond))
    | _              -> Error tsMalformedMessage

open Utils

/// Rounds down a DateTime to the nearest interval specified by the given TimeSpan.
///
/// - Parameters:
///   - dateTime: The DateTime to be rounded up.
///   - timeSpan: The TimeSpan representing the interval to round down to.
/// - Returns: A RoundedDateTime value representing the rounded down DateTime or an error message if the TimeSpan is unsuitable for rounding.
let roundDown dateTime timeSpan : RoundedDateTime = roundToInterval Down dateTime timeSpan

/// Rounds up a DateTime to the nearest interval specified by the given TimeSpan.
///
/// - Parameters:
///   - dateTime: The DateTime to be rounded up.
///   - timeSpan: The TimeSpan representing the interval to round up to.
/// - Returns: A RoundedDateTime value representing the rounded up DateTime or an error message if the TimeSpan is unsuitable for rounding.
let roundUp   dateTime timeSpan : RoundedDateTime = roundToInterval Up   dateTime timeSpan

//––––––––––––––––––––––––––––––––––––––––––––––––––––

type TSClass =
  | CDays         of int 
  | CHours        of int
  | CMinutes      of int
  | CSeconds      of int
  | CMilliseconds of int
  | CMicroseconds of int
  | CBad

let classify ts =
  match ts with
  | Days         n -> CDays    n
  | Hours        n -> CHours   n
  | Minutes      n -> CMinutes n
  | Seconds      n -> CSeconds n
  | Milliseconds n -> CMilliseconds n
  | Microseconds n -> CMicroseconds n
  | Bad            -> CBad      
  
let generateGoodInputsC() = [|
  day  7        , CDays          7
  hr   8        , CHours         8
  min  6        , CMinutes       6
  sec 10        , CSeconds      10
  ms  10        , CMilliseconds 10 
  us  20        , CMicroseconds 20 
  us  20 + ns 49, CMicroseconds 20 |]

//––––––––––––––––––––––––––––––––––––––––––––––––––––

let format = "M/d/yyyy HH:mm:ss.ffffff"
let provider = CultureInfo.InvariantCulture
let parseDT s nsArg = DateTime.ParseExact(s, format, provider) + ns nsArg
let start = parseDT "02/13/0001 10:09:14.123456" 250

let generatePrevGoodInputs() = [|
  (start, (day  7)), Good (parseDT "02/08/0001 00:00:00.000000"   0)
  (start, (hr   8)), Good (parseDT "02/13/0001 08:00:00.000000"   0)
  (start, (min  6)), Good (parseDT "02/13/0001 10:06:00.000000"   0)
  (start, (sec 10)), Good (parseDT "02/13/0001 10:09:10.000000"   0)
  (start, (ms  10)), Good (parseDT "02/13/0001 10:09:14.120000"   0)
  (start, (us  20)), Good (parseDT "02/13/0001 10:09:14.123440"   0)  |]

let generateNextGoodInputs() = [|
  (start, (day  7)), Good (parseDT "02/15/0001 00:00:00.000000"   0)
  (start, (hr   8)), Good (parseDT "02/13/0001 16:00:00.000000"   0)
  (start, (min  6)), Good (parseDT "02/13/0001 10:12:00.000000"   0)
  (start, (sec 10)), Good (parseDT "02/13/0001 10:09:20.000000"   0)
  (start, (ms  10)), Good (parseDT "02/13/0001 10:09:14.130000"   0)
  (start, (us  20)), Good (parseDT "02/13/0001 10:09:14.123460"   0)  |]

//––––––––––––––––––––––––––––––––––––––––––––––––––––

let bad = [|
  day   1 + hr   1
  day   2 + min  1
  day   1 + sec  1
  day   3 + ms   1
  day   4 + us   1
  day   5 + ns  50
  //––––––––––––––
  hr    1 + min  1
  hr    1 + sec  1
  hr    1 + ms   1
  hr    1 + us   1
  hr    1 + ns  50
  //––––––––––––––
  min   1 + sec  1
  min   1 + ms   1
  min   1 + us   1
  min   1 + ns  50
  //––––––––––––––
  sec   1 + ms   1
  sec   1 + us   1
  sec   1 + ns  50
  //––––––––––––––
  ms    1 + us   1
  ms    1 + ns  50
  //––––––––––––––
  us    1 + ns  50
  //––––––––––––––
  ns   50          |]

let badInputsC() =
  bad
  |> Array.map (fun input -> input, CBad)

let badInputs() =
  bad
  |> Array.map (fun input -> input, Error tsMalformedMessage)

//––––––––––––––––––––––––––––––––––––––––––––––––––––

let dtToString (dt: DateTime) =
  let format = "yyyy-MM-dd HH:mm:ss.ffffff"
  let ns = nsPerTick * int (dt.Ticks % ticksPerMicrosecond)
  $"%s{dt.ToString(format)}_%03d{ns}"

let tsToString (ts: TimeSpan) = 
    sprintf $"%d{ts.Days}.%02d{ts.Hours}:%02d{ts.Minutes}:%02d{ts.Seconds}.%03d{ts.Milliseconds}%03d{ts.Microseconds}_%d{int (ts.Ticks % 10L)}00"

//––––––––––––––––––––––––––––––––––––––––––––––––––––

type TestMode =
  | PrintFailures
  | PrintAll

let checkC textWriter testMode result =
  let ts,expected,actual = result
  let passed = actual = expected
  if not passed  ||  testMode = PrintAll then
    let ok = if passed then  " √" else  "# "
    let sTsInput = $"%s{tsToString ts}"
    fprintf textWriter $"%s{ok} classify %-22s{sTsInput} "
    let printResult result =
      match result with
      | CDays         n -> printf $"%d{n} Days"
      | CHours        n -> printf $"%d{n} Hours"
      | CMinutes      n -> printf $"%d{n} Minutes"
      | CSeconds      n -> printf $"%d{n} Seconds"
      | CMilliseconds n -> printf $"%d{n} Milliseconds"
      | CMicroseconds n -> printf $"%d{n} Microseconds"
      | CBad            -> printf $"bad"
    printResult actual
    if not passed then
      fprintf textWriter "          –– expected: "
      printResult expected
    fprintfn textWriter ""


let check msg textWriter testMode result =
  let (dt,ts),expected,actual = result
  let passed = actual = expected
  if not passed  ||  testMode = PrintAll then
    let ok = if passed then  " √" else  "# "
    let sTsInput = $"%s{tsToString ts}"
    fprintf textWriter $"%s{ok} %-8s{msg} %-22s{sTsInput} "
    let printResult result =
      match result with
      | Good  dt  -> printf $"%s{dtToString dt}"
      | Error s   -> printf $"%s{s}"
    printResult actual
    if not passed then
      fprintf textWriter "       –– expected: "
      printResult expected
    fprintfn textWriter ""

//––––––––––––––––––––––––––––––––––––––––––––––––––––

type InputAndExpectedC    = TimeSpan * TSClass
type InputExpectedActualC = TimeSpan * TSClass * TSClass

type InputAndExpected    = (DateTime * TimeSpan) * RoundedDateTime
type InputExpectedActual = (DateTime * TimeSpan) * RoundedDateTime * RoundedDateTime

type Output = Stdout | File of string

//––––––––––––––––––––––––––––––––––––––––––––––––––––

let waitUntil dateTime =
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()

let runPeriodically period count =
  match roundDown (DateTime.Now - TimeSpan.FromMilliseconds 10) period with
  | Error s -> failwith $"%s{s} – unable to calculate start time for saving audio files"
  | Good startTime -> 
  printfn $"startTime %s{tsToString startTime.TimeOfDay}  slop %s{tsToString (startTime - DateTime.Now)}"
  let rec saveFrom saveTime count =
    if count <= 0 then ()
    else
    waitUntil (saveTime + period)
    printfn $"%s{dtToString saveTime}"
    let count' = count - 1
    saveFrom (saveTime + period) count'
  saveFrom startTime count

//––––––––––––––––––––––––––––––––––––––––––––––––––––

[<EntryPoint>]
let main argv =
  printfn $"start is %A{dtToString start}"
  let testMode = match 2 with | 1 -> PrintFailures | 2 -> PrintAll       | _ -> failwith "bad choice"
  let output   = match 1 with | 1 -> Stdout        | 2 -> File "out.txt" | _ -> failwith "bad choice"
  use writer =
    match output with
    | Stdout    ->  Console.Out
    | File path ->  new IO.StreamWriter(path)
  printfn "TestMode is %A" testMode
  printfn "Output   is %A" output
  let testClassify() =
    let classifyOne (input: InputAndExpectedC)  : InputExpectedActualC =
      let ts,expected = input
      let actual = ts |> classify
      ts,expected,actual
    let checkOne (result: InputExpectedActualC)  : unit =
      checkC writer testMode result
    let runAll generator =
      generator()
      |> Seq.map  classifyOne
      |> Seq.iter checkOne
    runAll generateGoodInputsC
    runAll badInputsC
  let testGetPrevNext prevOrNext =
    let get =
      match prevOrNext with
      | "prev" -> roundDown
      | "next" -> roundUp
      | "bad "
      | _      -> roundDown
    let getOne (input: InputAndExpected)  : InputExpectedActual =
      let (dt, ts), expected = input
      let actual = ts |> get dt
      (dt,ts),expected,actual
    let checkOne (result: InputExpectedActual)  : unit =
      check prevOrNext writer testMode result
    let runAll generator =
      generator()
      |> Array.map  getOne
      |> Array.iter checkOne
    match prevOrNext with
    | "prev" -> runAll generatePrevGoodInputs
    | "next" -> runAll generateNextGoodInputs
    | "bad "
    | _      -> runAll badInputs
  testClassify()
  printfn ""
  testGetPrevNext "prev"
  printfn ""
  testGetPrevNext "next"
  printfn ""
  testGetPrevNext "bad "
  runPeriodically (TimeSpan.FromSeconds 2) 3
  0
 