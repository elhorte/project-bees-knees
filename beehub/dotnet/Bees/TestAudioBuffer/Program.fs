﻿
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.AudioBuffer
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

// n=15 ms=175 i=1 -> 15_176_01   n is callback number, i is 0–n within the callback
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

let runReadTests audioBuffer =
  let ab = (audioBuffer: AudioBuffer)
  let testRead time (duration:_TimeSpan) msg =
    let checkDeliveredArray deliveredArray deliveredTime deliveredDuration =
      let compare i sample =
        let deliveredMs   = decomposeMs sample
        let deliveredTime = deliveredTime: _DateTime
        let expectedMs    = deliveredTime.Millisecond + i / ab.InChannelCount
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
    let result = audioBuffer.read time duration
    let deliveredArray = AudioBuffer.CopyFromReadResult result
    let sPassFail = if checkDeliveredArray deliveredArray result.Time result.Duration then  "pass" else  "fail"
    printfn $"%s{sPassFail} – %s{result.ToString()} %s{msg}"
    ()
  let sNSegments = if ab.Segs.Old.Active then  "two segments." else  "one segment."
  ab.PrintAfter $"running Read() tests with %s{sNSegments}"
  printfn $"Ring has %s{sNSegments}"
  // BeforeData AfterData ClippedTail ClippedHead ClippedBothEnds OK
  do // BeforeData
    let time     = ab.Segs.TailTime - _TimeSpan.FromMilliseconds 30
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}"
  do // AfterData
    let time     = ab.Segs.HeadTime // just beyond
    let duration = _TimeSpan.FromMilliseconds 30
    testRead time duration $"{time} {duration}"
  do // ClippedTail
    let time     = ab.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = ab.Segs.HeadTime
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // ClippedHead
    let time     = ab.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let theEnd   = ab.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // ClippedBothEnds
    let time     = ab.Segs.TailTime - _TimeSpan.FromMilliseconds 1
    let theEnd   = ab.Segs.HeadTime + _TimeSpan.FromMilliseconds 1
    let duration = theEnd - time
    testRead time duration $"{time} {duration}"
  do // RangeOK
    let time     = ab.Segs.TailTime
    let duration = ab.Segs.Duration
    testRead time duration "OK - all of the data"
  do // RangeOK
    let time     = ab.Segs.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = ab.Segs.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1"
  do // RangeOK
    let time     = ab.Segs.TailTime        + _TimeSpan.FromMilliseconds 1
    let duration = ab.Segs.Oldest.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1 of the oldest seg"
  do // RangeOK
    let time     = ab.Segs.Cur.TailTime + _TimeSpan.FromMilliseconds 1
    let duration = ab.Segs.Cur.Duration - _TimeSpan.FromMilliseconds 2
    testRead time duration "OK -  all but the first and last 1 of the current seg"
  ab.PrintTitle()

let testRingPosition (audioBuffer: AudioBuffer) cbNum totalFrames =
  let ab = (audioBuffer: AudioBuffer)
  let frameNum = ab.NFramesTotal - uint64 ab.FrameCount
  let data     = ab.Ring[ab.LatestBlockIndex]
  let nChan = audioBuffer.InChannelCount
  let dataExpected = compose nChan cbNum (100 + int frameNum) 0
  let sPassFail = if data = dataExpected then  "pass" else  "fail"
  printfn $"%s{sPassFail} – access via LatestBlockIndex"

/// Run the stream for a while, then stop it and terminate PortAudio.
let run audioBuffer = task {
  let ab = (audioBuffer: AudioBuffer)

  let test() =
    printfn $"Simulating callbacks. Channels: %d{ab.InChannelCount}\n"
    let startMs = 100
    let initialFrameCount = 5
    let frameRate = 1000
    let mutable totalFrames = 0
    let mutable timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
    assert (timeInfo.inputBufferAdcTime = 0.0)
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(ab))
    ab.PrintTitle()
    assert (_DateTime.Now.Millisecond = startMs)
    let ring = ab.Ring
    for i in 0..32 do
  //  testRingPosition AudioBuffer i totalFrames
      let frameCount  = uint32 (if i < 25 then  initialFrameCount else  2 * initialFrameCount)
      let sampleCount = int frameCount * ab.InChannelCount
      let durationMs  = 1000 * int frameCount / frameRate
      let adcTimeMs  =_DateTime.Now.Millisecond // 100
      let iArray = makeArray sampleCount ab.InChannelCount i adcTimeMs
      let oArray = makeArray sampleCount ab.InChannelCount i adcTimeMs
      let input  = getHandle iArray
      let output = getHandle oArray
      let _ = showGC (fun () -> ab.AddSystemData(input, frameCount, (fun ()-> _DateTime.Now)) )
      if i = 10 then runReadTests ab  // AtBegin
      if i = 11 then runReadTests ab  // Moving
      if i = 15 then runReadTests ab  // Chasing
      if i = 26 then runReadTests ab  // Moving  with Segs.Cur.Offset non-0
      if i = 31 then runReadTests ab  // Chasing with Segs.Cur.Offset non-0
      totalFrames <- totalFrames + int frameCount
      let totalDurationSec = float totalFrames / 1000.0
      _DateTime.Now <- _DateTime.Now + _TimeSpan.FromMilliseconds durationMs
  //  printfn $"%A{_DateTime.Now} %f{totalDurationSec}"
  test()

  use cts = new CancellationTokenSource()
//printfn "Reading..."
//do! keyboardKeyInput "" cts
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig

// Reserve a global for this.  It is actually set in main.
let mutable audioConfig: BufConfig = Unchecked.defaultof<BufConfig>

//–––––––––––––––––––––––––––––––––––––
// Main



[<EntryPoint>]
let main _ =
  if _DateTime.Now.ToString() <> "100" then
    printfn "This program must be run with the fake _DateTime and _TimeSpan classes.  See DateTimeShim.fs"
    printfn "Ucomment USE_FAKE_DATE_TIME in BeesUtil.fsproj and BeesLib.fsproj"
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
  let sampleSize = sizeof<float32>
  audioConfig <- {
    AudioBufferDuration    = _TimeSpan.FromMilliseconds 1000 // These are ignored when the SimTimes struct is used, as above
    AudioBufferGapDuration = _TimeSpan.FromMilliseconds   20 // These are ignored when the SimTimes struct is used, as above
    SampleSize             = sampleSize
    Simulating             = sim 
    InChannelCount         = 1 // inputParameters.channelCount
    InFrameRate            = 1000 }
  printBufConfig audioConfig
//keyboardInputInit()
  try
    let ab = new AudioBuffer(audioConfig)
    let t = task {
      do! run ab } 
    t.Wait()
    printfn "Task done."
  with ex ->
    printfn "%A" ex
  printfn "Exiting with 0."
  0