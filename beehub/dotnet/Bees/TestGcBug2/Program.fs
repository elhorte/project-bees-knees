
open System
open System.Runtime.InteropServices

open PortAudioSharp
open BeesUtil.ItemPool
open TestGcBug.GcUtils
open BeesUtil.PortAudioUtils
open BeesLib.InputStream
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
//open BeesLib.Keyboard

initPortAudio()

// let defaultInputDevice = PortAudio.DefaultInputDevice
// printfn $"Default input device = %d{defaultInputDevice}"
// let inputInfo = PortAudio.GetDeviceInfo defaultInputDevice
// printfn $"%s{inputInfo.ToString()}"
// let nInputChannels = inputInfo.maxInputChannels
// printfn $"Number of channels = %d{nInputChannels} (max)"
// let sampleRate = inputInfo.defaultSampleRate
// printfn $"Sample rate = %f{sampleRate} (default)"
//
// let sampleFormat = SampleFormat.Float32
//
// let mutable inputParameters = StreamParameters()
// inputParameters.device                    <- defaultInputDevice
// inputParameters.channelCount              <- nInputChannels
// inputParameters.sampleFormat              <- sampleFormat 
// inputParameters.suggestedLatency          <- inputInfo.defaultHighInputLatency
// inputParameters.hostApiSpecificStreamInfo <- IntPtr.Zero
//
// let defaultOutputDevice = PortAudio.DefaultOutputDevice
// printfn $"Default output device = %d{defaultOutputDevice}"
// let outputInfo = PortAudio.GetDeviceInfo defaultOutputDevice
// printfn $"%s{outputInfo.ToString()}"
// let nOutputChannels = outputInfo.maxOutputChannels
// printfn $"Number of channels = %d{nOutputChannels} (max)"
//
// let mutable outputParameters = StreamParameters()
// outputParameters.device                    <- defaultOutputDevice
// outputParameters.channelCount              <- nOutputChannels
// outputParameters.sampleFormat              <- sampleFormat 
// outputParameters.suggestedLatency          <- outputInfo.defaultHighOutputLatency
// outputParameters.hostApiSpecificStreamInfo <- IntPtr.Zero

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string else  ()
  let defaultInput = PortAudio.DefaultInputDevice         in log $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in log $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in log $"Sample rate = %f{sampleRate} (default)"
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  log $"%s{inputInfo.ToString()}"
  log $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in log $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  log $"%s{outputInfo.ToString()}"
  log $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters


let withStartStop stream withStart f =
    let stream = (stream: Stream)
    if withStart then
      stream.Start() 
      printfn "Reading..."
    f()
    if withStart then
      printfn "Stopping..."
      stream.Stop() 
      printfn "Stopped"
  
type Work =
  | Normal
  | Trivial
  | GcGcOnly
  | GcCreateOnly
  | GcNormal


let pool = ItemPool.New<int> 1000 500 (fun _ -> 17)

let callbackIndirect input output frameCount timeInfo statusflags userDataPtr =
  Console.Write (".")
  match pool.Take() with
  | None ->
    Console.Write ("#")
    PortAudioSharp.StreamCallbackResult.Continue
  | Some item ->
    pool.ItemUseBegin()
    pool.ItemUseEnd item
    PortAudioSharp.StreamCallbackResult.Continue
  

let enoughForBiggestFrameCount = 20_000
let samples = Array.zeroCreate<single> (int enoughForBiggestFrameCount)

// Compiler sez:
//   This function value is being used to construct a delegate type whose signature includes a byref argument.
//   You must use an explicit lambda expression taking 6 arguments.
let callback = Stream.Callback(
  fun input output frameCount timeInfo statusflags userDataPtr ->
    //  Console.Write "-"
    Marshal.Copy(input, samples, 0, (int frameCount))
    callbackIndirect input output frameCount timeInfo statusflags userDataPtr ) 
printfn "Opening..."
let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation false


// let stream = new Stream(inParams        = inputParameters    ,
//                         outParams       = outputParameters   ,
//                         sampleRate      = sampleRate         ,
//                         framesPerBuffer = uint32 0           ,
//                         streamFlags     = StreamFlags.ClipOff,
//                         callback        = callback           ,
//                         userData        = IntPtr.Zero        )

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
//printBeesConfig beesConfig
//keyboardInputInit()
  let inputStream = newInputStream beesConfig inputParameters outputParameters withEcho withLogging
  // gc()
  // try
  //   let work = Trivial
  //   printfn $"\nDoing {work}\n"
  //   let f() = churnGc 1_000_000
  //   match work with
  //   | Trivial      -> ()
  //   | GcCreateOnly -> withStartStop inputStream.paStream false f
  //   | GcGcOnly     -> withStartStop inputStream.paStream true  gc
  //   | GcNormal     -> withStartStop inputStream.paStream true  f
  //   | Normal       -> withStartStop inputStream.paStream true  awaitForever
  //   printfn "Terminating..."
  //   PortAudio.Terminate()
  //   printfn "Terminated"
  // with
  // | :? PortAudioException as e ->
  //     printfn "While creating the stream: %A %A" e.ErrorCode e.Message
  //     Environment.Exit(2)
  //
  // gc()
  printfn "inputStream: %A" inputStream
  0