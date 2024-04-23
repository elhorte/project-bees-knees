
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.PortAudioUtils
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.Keyboard


// A function to consume a lot of memory quickly
let consumeMemory() =
  // let mutable data = []
  // data <- (Array.init 1 (fun _ -> "")) :: data
  "" :: []
  // Create objects in a list, then discard them.
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> Guid.NewGuid().ToString())) :: data
  // for _ in 1..1 do  data <- (Array.init 1 (fun _ -> "")) :: data
  // Here, 'data' goes out of scope and becomes eligible for garbage collection

let churn() =
  Console.WriteLine "Churn starting"
  for _ in 1..1 do 
    // consumeMemory() |> ignore
    // Optionally, force garbage collection to see its effect (though not recommended in production code)
  gc()
  delayMs 300
  // GC.WaitForPendingFinalizers()
  Console.WriteLine "Churn done."
    

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
let run stream = task {
  let inputStream = (stream: Stream)
//inputStream.Start()

  let test() =
    printfn "calling callback ...\n"
    let frameCount = 512
    let input  = foo frameCount
    let output = foo frameCount
    let timeInfo = PortAudioSharp.StreamCallbackTimeInfo()
    let statusFlags = PortAudioSharp.StreamCallbackFlags()
    let userDataPtr = IntPtr.Zero
    for i in 1..9000 do
      // inputStream.TestCallback input output (uint32 frameCount) timeInfo statusFlags userDataPtr |> ignore
      Console.WriteLine $"{i}"
      (Task.Delay 1).Wait()
    printfn "\n\ncalling callback done"
  
  delayMs 300
//DebugGlobals.simulatingCallbacks <- true
  
  Console.WriteLine "Main task start."
  Task.Run(churn).Wait()
  // Task.Run(task)
  Console.WriteLine "Main task done."
  delayMs 300
  
  use cts = new CancellationTokenSource()
  do! keyboardKeyInput "Keyboard ready." cts

 }

//–––––––––––––––––––––––––––––––––––––
// BeesConfig

// pro forma.  Actually set in main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>

//–––––––––––––––––––––––––––––––––––––
// Main

let callback =
  PortAudioSharp.Stream.Callback(
    fun input output frameCount timeInfo statusFlags userDataPtr ->
      PortAudioSharp.StreamCallbackResult.Continue)


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
    InputStreamAudioDuration    = _TimeSpan.FromMinutes 16
    InputStreamRingGapDuration  = _TimeSpan.FromSeconds 1
    SampleSize                  = sizeof<SampleType>
    InChannelCount              = inputParameters.channelCount
    InSampleRate                = int sampleRate  }
  printBeesConfig beesConfig
  keyboardInputInit()
  paTryCatchRethrow (fun () ->
    task {
      use paStream = new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                               outParams       = Nullable<_>(outputParameters)        ,
                                               sampleRate      = sampleRate                           ,
                                               framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                               streamFlags     = StreamFlags.ClipOff                  ,
                                               callback        = callback                             ,
                                               userData        = Nullable()                           )
      do! run paStream
      printfn "%s" (paStream.ToString())
    } |> Task.WaitAny |> ignore )
  0


