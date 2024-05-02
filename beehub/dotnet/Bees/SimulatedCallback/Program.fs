
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.InputStream
open BeesLib.BeesConfig
open BeesLib.CbMessagePool

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
  let i = i / inChannelCount
  let intVal = 1_000_00 * n  +  100 * (ms + i)  +  i
  assert (intVal <= 16_777_216) // max of range of contiguously representable ints in float32
  float32 intVal

// 1517601 -> ms=176
let decomposeMs x = (int x / 100) % 1000


let makeArray nFrames inChannelCount n ms =
  let compose i = compose inChannelCount n ms i
  let nSamples = int nFrames * inChannelCount
  Array.init nSamples compose

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
      let compare i frame =
        let i = i / cbs.InChannelCount
        let deliveredMs   = decomposeMs frame
        let deliveredTime = deliveredTime: _DateTime
        let msExpected    = deliveredTime.Millisecond + i
        deliveredMs = msExpected
      deliveredArray
      |> Seq.mapi compare
      |> Seq.forall id
    let mutable deliveredArray: float32[] = [||] // samples
    let mutable destIndexNS = 0
    let mutable nDeliveries = 0
    let acceptOneDelivery (array, sizeNF, indexNF, nFrames, nChannels, time, duration) =
      let printRange() = printfn $"index %d{indexNF}  length %d{nFrames}  time %A{time}  duration %A{duration}"
      let sizeNS   = sizeNF  * nChannels
      let indexNS  = indexNF * nChannels
      let nSamples = nFrames * nChannels
      if destIndexNS = 0 then  deliveredArray <- Array.zeroCreate<float32> sizeNS
      Array.Copy(array, indexNS, deliveredArray, destIndexNS, nSamples)
      destIndexNS <- destIndexNS + nSamples
      nDeliveries <- nDeliveries + 1
    let resultEnum, deliveredTime, deliveredDuration as result = inputStream.read time duration acceptOneDelivery
    let sPassFail = if checkDeliveredArray deliveredArray deliveredTime deliveredDuration then  "pass" else  "fail"
    printfn $"%s{sPassFail} %d{nDeliveries} %A{result} %s{msg}"
  let sNSegments = if cbs.Segs.Old.Active then  "two segments." else  "one segment."
  cbs.PrintRing $"running get() tests with %s{sNSegments}"
  printfn $"Ring has %s{sNSegments}"
  // BeforeData AfterData ClippedTail ClippedHead ClippedBothEnds OK
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 30
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}  ErrorBeforeData"
  do
    let time     = cbs.Segs.HeadTime // just beyond
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}  ErrorAfterData"
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime - _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}  WarnClippedTail"
  do
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}  WarnClippedHead"
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}  WarnClippedBothEnds"
  do
    let time     = cbs.Segs.TailTime
    let duration = cbs.Segs.Duration
    testRead time duration "OK - all of the data"
  do
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1"
  do
    let time     = cbs.Segs.TailTime        + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Oldest.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1 of the oldest seg"
  do
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
    printfn "Simulating callbacks ...\n"
    let initialFrameCount = 5
    let mutable timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
    assert (timeInfo.inputBufferAdcTime = 0.0)
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(cbs))
    cbs.PrintTitle()
    for i in 0..32 do
      let frameCount  = uint32 (if i < 25 then  initialFrameCount else  2 * initialFrameCount)
      let durationMs  = 1000 * int frameCount / inputStream.BeesConfig.InSampleRate
      let durationSec = float durationMs / 1000.0
      let adcTimeMsF  = (cbs.TimeInfoBase + timeInfo.inputBufferAdcTime) * 1000.0
      let adcTimeMs   = int (round adcTimeMsF)
      let sampleCount = frameCount * uint32 cbs.InChannelCount
      let iArray = makeArray frameCount cbs.InChannelCount i adcTimeMs
      let oArray = makeArray frameCount cbs.InChannelCount i adcTimeMs
      let input  = getHandle iArray
      let output = getHandle oArray
      let _ = showGC (fun () -> callback input output frameCount &timeInfo statusFlags userDataPtr |> ignore )
      if i = 15 then runReadTests inputStream
      if i = 26 then runReadTests inputStream
      if i = 31 then runReadTests inputStream
      timeInfo.inputBufferAdcTime <- timeInfo.inputBufferAdcTime + durationSec
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
    InSampleRate                = 1000 }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    let inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging, sim)
    let t = task {
      do! run inputStream 
      inputStream.CbState.Logger.Print "Log:" }
    t.Wait()
    printfn "Task done."
  finally
    printfn "Exiting with 0."
  0
