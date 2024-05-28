module BeesUtil.DateTimeCalculations

open System


let day n = TimeSpan.FromDays    n
let hr  n = TimeSpan.FromHours   n
let min n = TimeSpan.FromMinutes n
let sec n = TimeSpan.FromSeconds n

type TsClassification = Choice<int, int, int, int, unit, unit>

/// Classifies the given TimeSpan for use as a repeating interval.
/// Requires a nonzero integer in exactly one of Days, Hours, Minutes, or Seconds.
/// ts: The TimeSpan to classify.
/// returns: The classification of t.
let (|Days|Hours|Minutes|Seconds|Zero|Bad|) ts  : TsClassification =
  match (ts: TimeSpan) with
  | _ when ts = TimeSpan.Zero    -> Zero
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



type TSClass =
  | CDays    of int 
  | CHours   of int
  | CMinutes of int
  | CSeconds of int
  | CZero   
  | CBad

let classify2 ts =
  match ts with
  | Days     n -> CDays    n
  | Hours    n -> CHours   n
  | Minutes  n -> CMinutes n
  | Seconds  n -> CSeconds n
  | Zero       -> CZero     
  | Bad        -> CBad      

// let classify ts =
//   match ts with
//   | Days     n -> printfn $"Days    %d{n}"
//   | Hours    n -> printfn $"Hours   %d{n}"
//   | Minutes  n -> printfn $"Minutes %d{n}"
//   | Seconds  n -> printfn $"Seconds %d{n}"
//   | Zero       -> printfn $"zero"
//   | Bad        -> printfn $"bad"
  
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

let format = "M/d/yyyy HH:mm:ss"
let provider = System.Globalization.CultureInfo.InvariantCulture
let start = DateTime.ParseExact("1/13/0001 10:09:14", format, provider)

let generatePrevGoodInputs() = [|
  (start, (day  7.0)), Some (start - (day 6) - (sec start.Second) - (min start.Minute) - (hr start.Hour))
  (start, (hr   8.0)), Some (start - (hr  2) - (sec start.Second) - (min start.Minute))
  (start, (min  6.0)), Some (start - (min 3) - (sec start.Second))
  (start, (sec 10.0)), Some (start - (sec 4)) |]

let generateNextGoodInputs() = [|
  (start, (day  7.0)), Some (start + (day 1) - (sec start.Second) - (min start.Minute) - (hr start.Hour))
  (start, (hr   8.0)), Some (start + (hr  6) - (sec start.Second) - (min start.Minute))
  (start, (min  6.0)), Some (start + (min 3) - (sec start.Second))
  (start, (sec 10.0)), Some (start + (sec 6)) |]
  
let generateBadInputs() = [|
  (start, day 99.001), None
  (start, hr  23.001), None
  (start, min 59.001), None
  (start, sec 59.001), None
  (start, sec  0.001), None
  (start, sec  0.000), None |]


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
    let sInput = $"%A{ts}"
    fprintf textWriter $"%s{ok} %s{msg} %-19s{sInput} "
    let printResult result =
      match result with
      | Some dt  -> printf $"%A{dt}"
      | None     -> printf $"bad"
    printResult actual
    if not passed then
      fprintf textWriter "   –– expected: "
      printResult expected
    fprintfn textWriter ""


type InputAndExpectedC    = TimeSpan * TSClass
type InputExpectedActualC = TimeSpan * TSClass * TSClass

type InputAndExpected    = (DateTime * TimeSpan) * DateTime option
type InputExpectedActual = (DateTime * TimeSpan) * DateTime option * DateTime option

type Output = Stdout | File of string

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
      let actual = ts |> classify2
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
    let get = if prevOrNext = "next" then getNextBoundary else getPreviousBoundary
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
  0
  
// let t1 = day 400
// (match t1 with Bad |Zero -> false | _ -> true) |> printfn "%A" 
// let getMostRecentBoundary (d: DateTime) (t1: TimeSpan) =
//   match t1 with 
//   | Bad        -> None
//   | Years    t
//   | Days     t
//   | Hours    t -> None
//   | Minutes  t -> Some getMostRecentMinuteBoundary d t.Minutes
//   | Seconds  t -> Some getMostRecentSecondBoundary d t.Seconds


// let waitUntil dateTime =
// #if USE_FAKE_DATE_TIME
//   ()
// #else
//   let duration = dateTime - DateTime.Now
//   if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()
// #endif
