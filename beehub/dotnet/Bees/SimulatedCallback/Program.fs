
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp
open BeesUtil.PortAudioUtils
open BeesLib.DebugGlobals
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


let getArrayPointer byteCount =
  let inputArray = Array.create byteCount (float 0.0)
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";
  
/// Run the stream for a while, then stop it and terminate PortAudio.
let run frameSize inputStream = task {
  let inputStream = (inputStream: InputStream)
  inputStream.Start()
  
  let test() =
    printfn "calling callback ...\n"
    let frameCount = 4
    let byteCount = frameCount * frameSize
    let input  = getArrayPointer byteCount
    let output = getArrayPointer byteCount
    let mutable timeInfo    = PortAudioSharp.StreamCallbackTimeInfo()
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(inputStream.CbState))
    for i in 1..40 do
      let fc = if i < 20 then  frameCount else  2 * frameCount
      let m = showGC (fun () ->
        timeInfo.inputBufferAdcTime <- 0.001 * float i
        inputStream.Callback(input, output, uint32 fc, &timeInfo, statusFlags, userDataPtr) |> ignore 
        delayMs false 1
        Console.WriteLine $"{i}" )
      delayMs false 1
    printfn "\n\ncalling callback done"
  
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

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main



[<EntryPoint>]
let main _ =
  let withEcho    = false
  let withLogging = false
  simulatingCallbacks <- true
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  let sampleSize = sizeof<SampleType>
  beesConfig <- {
    LocationId                  = 1
    HiveId                      = 1
    PrimaryDir                  = "primary"
    MonitorDir                  = "monitor"
    PlotDir                     = "plot"
    inputStreamBufferDuration   = TimeSpan.FromMinutes 16
    inputStreamRingGapDuration  = TimeSpan.FromSeconds 1
    SampleSize                  = sampleSize
    InChannelCount              = inputParameters.channelCount
    InSampleRate                = sampleRate }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    paTryCatchRethrow (fun () ->
      use inputStream = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging)
      paTryCatchRethrow (fun () ->
        let t = task {
          do! run beesConfig.FrameSize inputStream 
          inputStream.CbState.Logger.Print "Log:" }
        t.Wait() )
      printfn "Task done." )
  finally
    printfn "Exiting with 0."
  0
