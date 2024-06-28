module BeesUtil.Util

open System
open System.Threading
open System.Threading.Tasks

open DateTimeShim


//–––––––––––––––––––––––––––––––––––––––––––––––––––

let roundAway value = Math.Round((value: float), MidpointRounding.AwayFromZero)

//–––––––––––––––––––––––––––––––––––––––––––––––––––

// for debugging simulating callbacks
let tsMs timeSpan = (timeSpan:_TimeSpan).TotalMilliseconds
let dtMs dateTime = (dateTime:_DateTime) - _DateTime.MinValue |> tsMs

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let printActualVsExpected actual expected message =
  let op = if actual = expected then "=" else "≠"
  printfn $"%d{actual} %s{op} %d{expected}  %s{message} actual%s{op}expeced"

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let tryCatch f (die: exn -> unit) =
  try
    f()
  with
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    die ex
    raise ex

let tryCatchRethrow f = tryCatch f (fun e -> ()                 )
let tryCatchExit    f = tryCatch f (fun e -> Environment.Exit(2))

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let delayMs ms =
  Console.Write $"Delay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  Console.WriteLine "}"

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let waitUntil dateTime =
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration).Wait()

let waitUntilWithToken dateTime (ctsToken: CancellationToken) =
  let duration = dateTime - DateTime.Now
  if duration > TimeSpan.Zero then  Task.Delay(duration, ctsToken).Wait()

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let gc() =
  Console.Write "GC {"
  GC.Collect()
  Console.WriteLine "}"
  // GC.WaitForPendingFinalizers()

//–––––––––––––––––––––––––––––––––––––––––––––––––––

let blockChar height =
  let blocks = [|" "; "▁"; "▂"; "▃"; "▄"; "▅"; "▆"; "▇"; "█"|]
  let index = int (height * float blocks.Length)
  let indexClipped = min index (blocks.Length - 1)
  blocks[indexClipped]

//–––––––––––––––––––––––––––––––––––––––––––––––––––

open System.Globalization

// Helper function to get time zone abbreviation
let timeZoneAbbreviation (timeZone: TimeZoneInfo) (dateTime: DateTime) =
  let timeZoneName = 
    if timeZone.IsDaylightSavingTime(dateTime) then
      timeZone.DaylightName
    else
      timeZone.StandardName
  // Extract first letter of each word in timeZoneName
  timeZoneName.Split(' ')
  |> Array.map (fun word -> word[0])
  |> fun initials -> String.Concat initials

/// Returns tuple of two trings: formatted date. local timezone abbreviation.
let dateTimeFormattedForLocalTimezone format (dt: DateTime) =
    let tzLocal  = TimeZoneInfo.Local
    let tzString = timeZoneAbbreviation tzLocal dt
    let formattedDateTime = dt.ToString(format, CultureInfo.InvariantCulture)
    formattedDateTime, tzString

//–––––––––––––––––––––––––––––––––––––––––––––––––––
