
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


let getArrayPointer byteCount n ms =
  let inputArray = Array.init byteCount (fun i -> float32 (n * 1_0000_00  +  (ms + i) * 100  +  i))
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
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
  let testOne time (duration:_TimeSpan) =
    let count = duration.Milliseconds
    let result = Array.zeroCreate<float32> count
    let mutable destIndex = 0
    let mutable startTime = 0
    let saveResult (array, index, length, time, duration) =
      if destIndex = 0 then  startTime <- time
      Array.Copy(array, index, result, destIndex, length)
      destIndex <- destIndex + length
    printfn "%A" (inputStream.get time duration saveResult)
  let sCurAndOld = if cbs.Segs.Old.Active then  "Cur and Old" else  "Cur only" 
  inputStream.CbState.PrintRing $"running get() tests with %s{sCurAndOld}"
  // BeforeData|AfterData|ClippedTail|ClippedHead|ClippedBothEnds|OK
  do // BeforeData
    let time     = inputStream.CbState.Segs.TimeTail - _TimeSpan.FromMilliseconds 30
    let duration = _TimeSpan.FromMilliseconds 30
    testOne time duration
  do // AfterData
    let time     = inputStream.CbState.Segs.TimeTail // just beyond
    let duration = _TimeSpan.FromMilliseconds 30
    testOne time duration
  do // ClippedTail – only part of Segs.Old
    let time     = inputStream.CbState.Segs.TimeTail - _TimeSpan.FromMilliseconds 40
    let theEnd   = inputStream.CbState.Segs.TimeTail + _TimeSpan.FromMilliseconds 30
    let duration = theEnd - time
    testOne time duration
  do // ClippedHead – only part of Segs.Cur
    let time     = inputStream.CbState.Segs.TimeHead - _TimeSpan.FromMilliseconds 40
    let theEnd   = inputStream.CbState.Segs.TimeHead + _TimeSpan.FromMilliseconds 30
    let duration = theEnd - time
    testOne time duration
  do // ClippedBothEnds – only part of Segs.Old
    let time     = inputStream.CbState.Segs.TimeTail - _TimeSpan.FromMilliseconds 40
    let theEnd   = inputStream.CbState.Segs.TimeHead + _TimeSpan.FromMilliseconds 30
    let duration = theEnd - time
    testOne time duration
  do // OK - exactly all of both segs
    let time     = inputStream.CbState.Segs.TimeTail
    let duration = inputStream.CbState.Segs.Duration
    testOne time duration
  
/// Run the stream for a while, then stop it and terminate PortAudio.
let run frameSize iS = task {
  let inputStream = (iS: InputStream)
  inputStream.Start()
  
  let test() =
    printfn "calling callback ...\n"
    let frameCount = 5
    let mutable timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
    assert (timeInfo.inputBufferAdcTime = 0.0)
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(inputStream.CbState))
    for i in 0..31 do
      let nFrames = uint32 (if i < 25 then  frameCount else  2 * frameCount)
      let durationSec = float nFrames / float iS.BeesConfig.InSampleRate
      let byteCount = frameCount * frameSize
      let adcTimeMs = int (timeInfo.inputBufferAdcTime * 1000.0)
      let input  = getArrayPointer byteCount i adcTimeMs
      let output = getArrayPointer byteCount i adcTimeMs
      let m = showGC (fun () ->
        callback input output nFrames &timeInfo statusFlags userDataPtr |> ignore
        timeInfo.inputBufferAdcTime <- timeInfo.inputBufferAdcTime + durationSec
        if i = 15 then runTests inputStream
      )
      m |> ignore
    runTests inputStream
  
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
  let withEcho    = false
  let withLogging = false
//let sim = SimInts  { NData = 56 ; NGap = 20 }
  let sim = SimTimes { AudioDuration = _TimeSpan.FromMilliseconds  56 ; GapDuration = _TimeSpan.FromMilliseconds 20 }
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  let sampleSize = sizeof<SampleType>
  beesConfig <- {
    LocationId                  = 1
    HiveId                      = 1
    PrimaryDir                  = "primary"
    MonitorDir                  = "monitor"
    PlotDir                     = "plot"
    InputStreamAudioDuration    = _TimeSpan.FromMilliseconds 1000
    InputStreamRingGapDuration  = _TimeSpan.FromMilliseconds   20
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
