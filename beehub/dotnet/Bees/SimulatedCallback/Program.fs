
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


let getHandle a =
  let handle = GCHandle.Alloc(a, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

let runTests inputStream =
  let cbs = (inputStream: InputStream).CbState
  let printRange (array, index, length, time, duration) =
    printfn $"index %d{index}  length %d{length}  time %A{time}  duration %A{duration}"
  let testOne time (duration:_TimeSpan) msg =
    let checkDeliveredAray (deliveredArray: float32[]) (deliveredTime: _DateTime) deliveredDuration =
      let extract d = (int d / 100) % 1000
      // resultData
      // |> Seq.mapi (fun i d -> trim d = (time.Milliseconds + i))
      // |> Seq.forall id
      let rec check i  : bool =
        if i < deliveredArray.Length then
          let data = deliveredArray[i]
          let msDelivered = extract data
          let msExpected  = deliveredTime.Millisecond + i
          if msDelivered = msExpected then  check (i + 1)
                                      else  false
        else
          true
      check 0
    let count = duration.Milliseconds
    let mutable deliveredArray: float32[] = [||]
    let mutable startTime = _DateTime.MinValue
    let mutable destIndex = 0
    let mutable nDeliveries = 0
    let acceptOneDelivery (array, size, index, length, time, duration) =
      if destIndex = 0 then
        deliveredArray <- Array.zeroCreate<float32> size
        startTime      <- time
      Array.Copy(array, index, deliveredArray, destIndex, length)
      destIndex   <- destIndex + length
      nDeliveries <- nDeliveries + 1
    let name, deliveredTime, deliveredDuration as result = inputStream.read time duration acceptOneDelivery
    let sPassFail = if checkDeliveredAray deliveredArray deliveredTime deliveredDuration then  "pass" else  "fail"
    printfn $"%s{sPassFail} %d{nDeliveries} %A{result} %s{msg}"
  let sNSegments = if cbs.Segs.Old.Active then  "two segments." else  "one segment."
  cbs.PrintRing $"running get() tests with %s{sNSegments}"
  printfn $"Ring has %s{sNSegments}"
  // BeforeData|AfterData|ClippedTail|ClippedHead|ClippedBothEnds|OK
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 30
    let duration = _TimeSpan.FromMilliseconds 30
    testOne time duration $"{time} {duration}  ErrorBeforeData"
  do
    let time     = cbs.Segs.HeadTime // just beyond
    let duration = _TimeSpan.FromMilliseconds 30
    testOne time duration $"{time} {duration}  ErrorAfterData"
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime - _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testOne time duration $"{time} {duration}  WarnClippedTail"
  do
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testOne time duration $"{time} {duration}  WarnClippedHead"
  do
    let time     = cbs.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = cbs.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testOne time duration $"{time} {duration}  WarnClippedBothEnds"
  do
    let time     = cbs.Segs.TailTime
    let duration = cbs.Segs.Duration
    testOne time duration "OK - all of the data"
  do
    let time     = cbs.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = cbs.Segs.Duration - _TimeSpan.FromMilliseconds 1
    testOne time duration "OK -  all but the first and last 1"
  cbs.PrintTitle()

let makeArray nFrames n ms =
  let nFrames = int nFrames
  let compose i =
    let iVal = 100_000 * n  +  100 * (ms + i)  +  i
    assert (iVal < 16_777_216)
    float32 iVal
  Array.init nFrames compose

/// Run the stream for a while, then stop it and terminate PortAudio.
let run frameSize iS = task {
  let cbs = (iS: InputStream).CbState
  let inputStream = (iS: InputStream)
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
      let durationMs  = 1000 * int frameCount / iS.BeesConfig.InSampleRate
      let durationSec = float durationMs / 1000.0
      let adcTimeMsF  = timeInfo.inputBufferAdcTime * 1000.0
      let adcTimeMs   = cbs.TimeInfoBase.Millisecond + int (round adcTimeMsF)
      let iArray = makeArray frameCount i adcTimeMs
      let oArray = makeArray frameCount i adcTimeMs
      let input  = getHandle iArray
      let output = getHandle oArray
      let m = showGC (fun () -> callback input output frameCount &timeInfo statusFlags userDataPtr |> ignore )
      m |> ignore
      if i = 15 then runTests inputStream
      if i = 26 then runTests inputStream
      if i = 31 then runTests inputStream
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
    InChannelCount              = inputParameters.channelCount
    InSampleRate                = 1000 }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    paTryCatchRethrow (fun () ->
      use inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging, sim)
      paTryCatchRethrow (fun () ->
        let t = task {
          do! run beesConfig.FrameSize inputStream 
          inputStream.CbState.Logger.Print "Log:" }
        t.Wait() )
      printfn "Task done." )
  finally
    printfn "Exiting with 0."
  0
