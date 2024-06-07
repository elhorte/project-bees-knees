
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.InputStream
open BeesLib.BeesConfig

// See Theory of Operation comment before main at the end of this file.

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait() |> ignore
  if print then Console.Write "}"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels}"
  let sampleRate   = int inputInfo.defaultSampleRate      in printfn $"Sample rate = %d{sampleRate} (default)"
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  printfn $"%s{inputInfo.ToString()}"
  printfn $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in printfn $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  printfn $"%s{outputInfo.ToString()}"
  printfn $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters

// n=15 ms=175 i=1 -> 1517601
let compose inChannelCount n ms i =
//let ms = ms - startMs
  let iMs = i / inChannelCount
  let intVal = 1_000_00 * n  +  100 * (ms + iMs)  +  i
  let inFloat32ContiguousRepresentableRange i = i <= 16_777_216
  assert inFloat32ContiguousRepresentableRange intVal
  float32 intVal

// 1517601 -> ms=176
let decomposeMs x = (int x / 100) % 1000


let makeArray nFrames inChannelCount n ms =
  let compose i = compose inChannelCount n ms i
  let nSamples = int nFrames * inChannelCount
  let array = Array.init nSamples compose
  array

let getHandle a =
  let handle = GCHandle.Alloc(a, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()


let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

let runReadTests inputStream =
  let cbs = (inputStream: InputStream).CbState
  let testRead time (duration:_TimeSpan) msg =
    let checkDeliveredArray deliveredArray deliveredTime deliveredDuration =
      let compare i sample =
        let deliveredMs   = decomposeMs sample
        let deliveredTime = deliveredTime: _DateTime
        let expectedMs    = deliveredTime.Millisecond + i / cbs.InChannelCount
        deliveredMs = expectedMs
      deliveredArray
      |> Seq.mapi compare
      |> Seq.forall id
      // let rec check i  : bool =
      //    if i < Array.length deliveredArray then
      //      let frame = deliveredArray[i]
      //      if compare i frame then  check (i + 1)
      //                         else  false
      //    else
      //      true
      // check 0
    let result = inputStream.read time duration
    let deliveredArray = InputStream.CopyFromReadResult result
    let sPassFail = if checkDeliveredArray deliveredArray result.Time result.Duration then  "pass" else  "fail"
    printfn $"%s{sPassFail} – %s{result.ToString()} %s{msg}"
    ()
  let sNSegments = if cbs.Segs.Old.Active then  "two segments." else  "one segment."
  cbs.PrintAfter $"running Read() tests with %s{sNSegments}"
  printfn $"Ring has %s{sNSegments}"
  // BeforeData AfterData ClippedTail ClippedHead ClippedBothEnds OK
  do // BeforeData
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 30
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}"
  do // AfterData
    let time     = cbs.Segs.HeadTime // just beyond
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}"
  do // ClippedTail
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // ClippedHead
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // ClippedBothEnds
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // RangeOK
    let time     = cbs.Segs.TailTime
    let duration = cbs.Segs.Duration
    testRead time duration "OK - all of the data"
  do // RangeOK
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1"
  do // RangeOK
    let time     = cbs.Segs.TailTime        + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Oldest.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1 of the oldest seg"
  do // RangeOK
    let time     = cbs.Segs.Cur.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Cur.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1 of the current seg"
  cbs.PrintTitle()

/// Run the stream for a while, then stop it and terminate PortAudio.
let run inputStream = task {
  let inputStream = (inputStream: InputStream)
  let cbs         = inputStream.CbState
  inputStream.Start()

  let test() =
    printfn $"Simulating callbacks. Channels: %d{cbs.InChannelCount}\n"
    let startMs = 100
    let initialFrameCount = 5
    let frameRate = 1000
    let mutable totalFrames = 0
    let mutable timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
    assert (timeInfo.inputBufferAdcTime = 0.0)
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(cbs))
    cbs.PrintTitle()
    assert (_DateTime.Now.Millisecond = startMs)
    let ring = cbs.Ring
    for i in 0..32 do
      let frameCount  = uint32 (if i < 25 then  initialFrameCount else  2 * initialFrameCount)
      let sampleCount = int frameCount * cbs.InChannelCount
      let durationMs  = 1000 * int frameCount / frameRate
      let adcTimeMs  =_DateTime.Now.Millisecond // 100
      let iArray = makeArray sampleCount cbs.InChannelCount i adcTimeMs
      let oArray = makeArray sampleCount cbs.InChannelCount i adcTimeMs
      let input  = getHandle iArray
      let output = getHandle oArray
      let _ = showGC (fun () -> callback input output frameCount &timeInfo statusFlags userDataPtr |> ignore )
      if i = 10 then runReadTests inputStream  // AtBegin
      if i = 11 then runReadTests inputStream  // Moving
      if i = 15 then runReadTests inputStream  // Chasing
      if i = 26 then runReadTests inputStream  // Moving  with Segs.Cur.Offset non-0
      if i = 31 then runReadTests inputStream  // Chasing with Segs.Cur.Offset non-0
      totalFrames <- totalFrames + int frameCount
      let totalDurationSec = float totalFrames / 1000.0
      timeInfo.inputBufferAdcTime <- totalDurationSec
      _DateTime.Now <- _DateTime.Now + _TimeSpan.FromMilliseconds durationMs
  //  printfn $"%A{_DateTime.Now} %f{totalDurationSec}"
  test()

  use cts = new CancellationTokenSource()
//printfn "Reading..."
//do! keyboardKeyInput "" cts
  printfn "Stopping..."    ; inputStream.Stop()
  printfn "Stopped"
  printfn "Terminating..." ; terminatePortAudio()
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig

// Reserve a global for this.  It is actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main



[<EntryPoint>]
let main _ =
  if _DateTime.Now.ToString() <> "100" then
    printfn "This program must be run with the fake _DateTime and _TimeSpan classes.  See DateTimeShim.fs"
    2
  else
  printfn "Running with the fake _DateTime and _TimeSpan classes, as required."
  let withEcho    = false
  let withLogging = false
//let sim = SimInts  { NData = 56 ; NGap = 20 }
  // with AudioDuration 56, nFrames 5 increased to 10, GapDuration must be at least 13 so there’s room for at least one callback.
  let sim = SimTimes { AudioDuration = _TimeSpan.FromMilliseconds  56 ; GapDuration = _TimeSpan.FromMilliseconds 15 }
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  let sampleSize = sizeof<SampleType>
  beesConfig <- {
    LocationId                  = 1
    HiveId                      = 1
    PrimaryDir                  = "primary"
    MonitorDir                  = "monitor"
    PlotDir                     = "plot"
    InputStreamAudioDuration    = _TimeSpan.FromMilliseconds 1000 // These are ignored when the SimTimes struct is used, as above
    InputStreamRingGapDuration  = _TimeSpan.FromMilliseconds   20 // These are ignored when the SimTimes struct is used, as above
    SampleSize                  = sampleSize
    InChannelCount              = 1 // inputParameters.channelCount
    InFrameRate                 = 1000 }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    let inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging, sim)
    let t = task {
      do! run inputStream 
      inputStream.CbState.Logger.Print "Log:" }
    t.Wait()
    printfn "Task done."
  with ex ->
    printfn "%A" ex
  printfn "Exiting with 0."
  0
