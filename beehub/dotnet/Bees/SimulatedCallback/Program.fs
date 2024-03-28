
open System
open System.Runtime.InteropServices
open System.Threading

open System.Threading.Tasks
open BeesLib
open BeesLib.InputStream
open FSharp.Control
open Microsoft.Win32.SafeHandles
open PortAudioSharp
open BeesUtil.PortAudioUtils
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.Keyboard

// See Theory of Operation comment before main at the end of this file.

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in printfn $"Sample rate = %f{sampleRate} (default)"
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
  System.GC.Collect()
  let starting = GC.GetTotalMemory(true)
  f()
  let m = GC.GetTotalMemory(true) - starting
  Console.WriteLine $"gc memory: %i{ m }";

  
/// Run the stream for a while, then stop it and terminate PortAudio.
let run beesConfig inputStream = task {
  let inputStream = (inputStream: InputStream)
  inputStream.Start()
  
  let test() =
    printfn "calling callback ...\n"
    let frameCount = 4
    let frameSize = (beesConfig: BeesConfig).FrameSize
    let byteCount = frameCount * frameSize
    let input  = getArrayPointer byteCount
    let output = getArrayPointer byteCount
    let timeInfo    = PortAudioSharp.StreamCallbackTimeInfo()
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = IntPtr.Zero
    for i in 1..40 do
      let fc = if i < 20 then  frameCount else  2 * frameCount
      let m = showGC (fun () -> 
        inputStream.callback input output (uint32 fc) timeInfo statusFlags userDataPtr |> ignore 
        Console.WriteLine $"{i}" )
      (Task.Delay 1).Wait()
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
  DebugGlobals.simulatingCallbacks <- true
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
    InSampleRate                = int sampleRate }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    paTryCatchRethrow (fun () ->
      use inputStream = InputStream.New beesConfig inputParameters outputParameters withEcho withLogging
      paTryCatchRethrow (fun () ->
        let t = task {
          do! run beesConfig inputStream 
          inputStream.Logger.Print "Log:" }
        t.Wait() )
      printfn "Task done." )
  finally
    printfn "Exiting with 0."
  0
