
open System
open System.Runtime.InteropServices
open System.Threading

open System.Threading.Tasks
open BeesLib.InputStream
open FSharp.Control
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


let foo count =
  let inputArray = Array.create count (float 0.0)
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

/// Run the stream for a while, then stop it and terminate PortAudio.
let run inputStream = task {
  let inputStream = (inputStream: InputStream)
//inputStream.Start()
  
  let test() =
    printfn "calling callback ...\n"
    let frameCount = 512
    let input  = foo frameCount
    let output = foo frameCount
    let timeInfo    = PortAudioSharp.StreamCallbackTimeInfo()
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = IntPtr.Zero
    for i in 1..9000 do
      inputStream.callback input output (uint32 frameCount) timeInfo statusFlags userDataPtr |> ignore
      Console.WriteLine $"{i}"
      (Task.Delay 1).Wait()
    printfn "\n\ncalling callback done"
  
  
  use cts = new CancellationTokenSource()
//printfn "Reading..."
//do! keyboardKeyInput "" cts
//printfn "Stopping..."    ; inputStream.Stop()
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
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  beesConfig <- {
    LocationId                  = 1
    HiveId                      = 1
    PrimaryDir                  = "primary"
    MonitorDir                  = "monitor"
    PlotDir                     = "plot"
    inputStreamBufferedDuration = TimeSpan.FromMinutes 16
    SampleSize                  = sizeof<SampleType>
    InChannelCount              = inputParameters.channelCount
    InSampleRate                = int sampleRate  }
  printBeesConfig beesConfig
//keyboardInputInit()
  try
    paTryCatchRethrow (fun () ->
      use inputStream = InputStream.New beesConfig inputParameters outputParameters withEcho withLogging
      paTryCatchRethrow (fun () ->
        let t = task {
          do! run inputStream 
          inputStream.Logger.Print "Log:" }
        t.Wait() )
      printfn "Task done." )
  finally
    printfn "Exiting with 0."
  0
