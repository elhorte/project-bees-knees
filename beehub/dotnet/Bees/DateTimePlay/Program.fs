module BeesUtil.DateTimeCalculations

open System
open System.Threading.Tasks


let dtToString (dt: DateTime) =
  let format = "yyyy-MM-dd HH:mm:ss.ffffff"
  let ns = int (dt.Ticks % 10000L)
  $"%s{dt.ToString(format)}_%03d{ns}"

let tsToString (ts: TimeSpan) = 
    sprintf $"%d{ts.Days}.%02d{ts.Hours}:%02d{ts.Minutes}:%02d{ts.Seconds}.%03d{ts.Milliseconds}%03d{int (ts.Ticks % 10000L)}"
    
let day n = TimeSpan.FromDays         n
let hr  n = TimeSpan.FromHours        n
let min n = TimeSpan.FromMinutes      n
let sec n = TimeSpan.FromSeconds      n
let ms  n = TimeSpan.FromMilliseconds n
let us  n = TimeSpan.FromMicroseconds n
let ns  n = TimeSpan.FromTicks        (int64 (round (float n / float TimeSpan.TicksPerMillisecond)))

type RoundedDateTime =
| Good  of DateTime
| Error of string

type TsClassification = Choice<int, int, int, int, int, int, unit>

let tsMalformedMessage = "Malformed time period for rounding"

/// Classifies the given TimeSpan for use as a repeating interval.
/// Requires exactly one nonzero value of Days, Hours, Minutes, or Seconds.
/// ts: The TimeSpan to classify.
/// returns: The classification of ts.
let (|Days|Hours|Minutes|Seconds|Milliseconds|Microseconds|Bad|) ts  : TsClassification =
  match (ts: TimeSpan) with
  | _ when ts = TimeSpan.Zero                                               -> Bad
  | _ when ts.TotalDays         >= 1.0  &&  ts.TotalDays         % 1.0 = 0  -> Days         ts.Days
  | _ when ts.TotalHours        >= 1.0  &&  ts.TotalHours        % 1.0 = 0  -> Hours        ts.Hours  
  | _ when ts.TotalMinutes      >= 1.0  &&  ts.TotalMinutes      % 1.0 = 0  -> Minutes      ts.Minutes
  | _ when ts.TotalSeconds      >= 1.0  &&  ts.TotalSeconds      % 1.0 = 0  -> Seconds      ts.Seconds
  | _ when ts.TotalMilliseconds >= 1.0  &&  ts.TotalMilliseconds % 1.0 = 0  -> Milliseconds ts.Milliseconds
  | _ when ts.TotalMicroseconds >= 1.0  &&  ts.TotalMicroseconds % 1.0 = 0  -> Microseconds ts.Microseconds
  | _                                                                       -> Bad

type UpDown = Up | Down

let roundToInterval (upDown: UpDown) (dt: DateTime) (ts: TimeSpan)  : RoundedDateTime =
  let tsIfUp = match upDown with Up -> ts | Down -> TimeSpan.Zero
  let dateTime y M d h m s k  = DateTime(y, M, d, h, m, s, dt.Kind) + tsIfUp
  match ts with
  | Days         n -> Good ((dateTime dt.Year dt.Month 1      0       0         0         0             ) + day n)
  | Hours        n -> Good ((dateTime dt.Year dt.Month dt.Day 0       0         0         0             ) + hr  n)
  | Minutes      n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour 0         0         0             ) + min n)
  | Seconds      n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute 0         0             ) + sec n)
  | Milliseconds n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute dt.Second 0             ) + ms  n) 
  | Microseconds n -> Good ((dateTime dt.Year dt.Month dt.Day dt.Hour dt.Minute dt.Second dt.Millisecond) + us  n)
  | _              -> Error tsMalformedMessage


let roundDownToInterval dt ts : RoundedDateTime = roundToInterval Down dt ts
let roundUpToInterval   dt ts : RoundedDateTime = roundToInterval Up   dt ts


type TSClass =
  | CDays         of int 
  | CHours        of int
  | CMinutes      of int
  | CSeconds      of int
  | CMilliseconds of int
  | CMicroseconds of int
  | CZero   
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
  
let generateGoodInputsC() = seq {
  day 100.0, CDays    100
  hr   23.0, CHours    23
  min  59.0, CMinutes  59
  sec  59.0, CSeconds  59 }

let generateBadInputsC() = seq {
  day 99.001, CBad
  hr  23.001, CBad
  min 59.001, CBad
  sec 59.001, CBad
  sec  0.001, CBad
  sec  0.000, CBad }

let format = "M/d/yyyy HH:mm:ss.ffffff"
let provider = System.Globalization.CultureInfo.InvariantCulture
let start = DateTime.ParseExact("1/13/0001 10:09:14.123456", format, provider) + ns 789
printfn $"%A{dtToString start}"

let generatePrevGoodInputs() = [|
  (start, (day  7.0)), Good (start - (day 6) - (sec start.Second) - (min start.Minute) - (hr start.Hour))
  (start, (hr   8.0)), Good (start - (hr  2) - (sec start.Second) - (min start.Minute))
  (start, (min  6.0)), Good (start - (min 3) - (sec start.Second))
  (start, (sec 10.0)), Good (start - (sec 4)) |]

let generateNextGoodInputs() = [|
  (start, (day  7.0)), Good (start + (day 1) - (sec start.Second) - (min start.Minute) - (hr start.Hour))
  (start, (hr   8.0)), Good (start + (hr  6) - (sec start.Second) - (min start.Minute))
  (start, (min  6.0)), Good (start + (min 3) - (sec start.Second))
  (start, (sec 10.0)), Good (start + (sec 6)) |]
  
let generateBadInputs() = [|
  (start, day 99.001), Error tsMalformedMessage
  (start, hr  23.001), Error tsMalformedMessage
  (start, min 59.001), Error tsMalformedMessage
  (start, sec 59.001), Error tsMalformedMessage
  (start, ms  99.001), Error tsMalformedMessage
  (start, us  99.100), Error tsMalformedMessage |]


type TestMode =
  | PrintFailures
  | PrintAll

let checkC textWriter testMode result =
  let ts,expected,actual = result
  let passed = actual = expected
  if not passed  ||  testMode = PrintAll then
    let ok = if passed then  " √" else  "# "
    let sInput = $"%A{ts}"
    fprintf textWriter $"%s{ok} %-19s{sInput} "
    let printResult result =
      match result with
      | CDays     n -> printf $"%d{n} Days"
      | CHours    n -> printf $"%d{n} Hours"
      | CMinutes  n -> printf $"%d{n} Minutes"
      | CSeconds  n -> printf $"%d{n} Seconds"
      | CZero       -> printf $"zero"
      | CBad        -> printf $"bad"
    printResult actual
    if not passed then
      fprintf textWriter "   –– expected: "
      printResult expected
    fprintfn textWriter ""


let check msg textWriter testMode result =
  let (dt,ts),expected,actual = result
  let passed = actual = expected
  if not passed  ||  testMode = PrintAll then
    let ok = if passed then  " √" else  "# "
    let sTsInput = $"%A{tsToString ts}"
    fprintf textWriter $"%s{ok} %s{msg} %-19s{sTsInput} "
    let printResult result =
      match result with
      | Good  dt  -> printf $"%s{dtToString dt}"
      | Error s   -> printf $"%s{s}"
    printResult actual
    if not passed then
      fprintf textWriter "   –– expected: "
      printResult expected
    fprintfn textWriter ""


type InputAndExpectedC    = TimeSpan * TSClass
type InputExpectedActualC = TimeSpan * TSClass * TSClass

type InputAndExpected    = (DateTime * TimeSpan) * RoundedDateTime
type InputExpectedActual = (DateTime * TimeSpan) * RoundedDateTime * RoundedDateTime

type Output = Stdout | File of string

let waitUntil dateTime =
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()


let runPeriodically period =
  match roundDownToInterval (DateTime.Now - TimeSpan.FromMilliseconds 10) period with
  | Error s -> failwith $"%s{s} – unable to calculate start time for saving audio files"
  | Good startTime -> 
  printfn $"startTime %A{tsToString startTime.TimeOfDay}  slop %A{tsToString (startTime - DateTime.Now)}"
  let rec saveFrom saveTime =
    waitUntil (saveTime + period)
    printfn $"%A{dtToString saveTime}"
    saveFrom (saveTime + period)
  saveFrom startTime


[<EntryPoint>]
let main argv =
  let testMode = match 2 with | 1 -> PrintFailures | 2 -> PrintAll       | _ -> failwith "bad choice"
  let output   = match 1 with | 1 -> Stdout        | 2 -> File "out.txt" | _ -> failwith "bad choice"
  use writer =
    match output with
    | Stdout    ->  System.Console.Out
    | File path ->  new System.IO.StreamWriter(path)
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
    runAll generateBadInputsC
  let testGetPrevNext prevOrNext =
    let get = roundDownToInterval // if prevOrNext = "next" then roundUpToInterval else roundDownToInterval
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
    if prevOrNext = "prev" then runAll generatePrevGoodInputs else runAll generateNextGoodInputs
    if prevOrNext = "next" then runAll generateBadInputs
  testGetPrevNext "prev"
  testGetPrevNext "next"
//runPeriodically (TimeSpan.FromSeconds 2)
  0
 