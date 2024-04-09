
open System
open System.Runtime.InteropServices
open System.Threading.Tasks

open PortAudioSharp
open BeesLib.DebugGlobals
open BeesLib.InputStream
open BeesLib.BeesConfig
open BeesLib.CbMessagePool

// See Theory of Operation comment before main at the end of this file.

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait() |> ignore
  if print then Console.Write "}"

let awaitForever() = delayMs false Int32.MaxValue

PortAudio.LoadNativeLibrary()
PortAudio.Initialize()

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string else  ()
  let defaultInput = PortAudio.DefaultInputDevice         in log $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in log $"Number of channels = %d{nChannels}"
  let sampleRate   = int inputInfo.defaultSampleRate      in log $"Sample rate = %d{sampleRate} (default)"
  let sampleFormat = SampleFormat  .Float32
  let sampleSize   = sizeof<float32>
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = sampleFormat                      ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  log $"%s{inputInfo.ToString()}"
  log $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in log $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = sampleFormat                        ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  log $"%s{outputInfo.ToString()}"
  log $"outputParameters=%A{outputParameters}"
  let frameSize = sampleSize * nChannels
  sampleRate, frameSize, inputParameters, outputParameters


let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

let getArrayPointer byteCount =
  let inputArray = Array.create byteCount (float 0.0)
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main

let test inputStream frameSize =
  let (inputStream: InputStream) = inputStream
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

let Quiet   = false
let Verbose = true

[<EntryPoint>]
let main _ =
  let sampleRate, frameSize, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  let sampleSize = sizeof<SampleType>
  let withEcho    = false
  let withLogging = false
  simulatingCallbacks <- true
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
  use iS = new InputStream(beesConfig, inputParameters, outputParameters, withEcho, withLogging)
  GC.Collect()
  try
    iS.Start()
    if simulatingCallbacks then
      test iS frameSize
    else
      printfn "Reading..."
      printfn "Begin"
      awaitForever()
      printfn "Done"
      printfn "Stopping..."
      iS.Stop() 
      printfn "Stopped"
    printfn "Terminating..."
    PortAudio.Terminate()
    printfn "Terminated"
  with
  | :? PortAudioException as e ->
      printfn "While creating the stream: %A %A" e.ErrorCode e.Message
      Environment.Exit(2)
  
  GC.Collect()
  printfn "inputStream: %A" iS
  0
