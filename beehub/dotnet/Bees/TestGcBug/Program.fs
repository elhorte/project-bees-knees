
open System.Runtime.InteropServices
open System.Threading.Tasks
open PortAudioSharp
open System
open BeesUtil.ItemPool
open TestGcBug.GcUtils

try
  PortAudio.LoadNativeLibrary()
  PortAudio.Initialize()
with
| :? PortAudioException as e ->
  printfn $"PortAudio error: %s{e.Message}"
  Environment.Exit(2)

// let defaultInputDevice = PortAudio.DefaultInputDevice
// printfn $"Default input device = %d{defaultInputDevice}"
//
// let inputInfo = PortAudio.GetDeviceInfo defaultInputDevice
// printfn $"%s{inputInfo.ToString()}"
//
// let nChannels = inputInfo.maxInputChannels
// printfn $"Number of channels = %d{nChannels} (max)"
// let sampleRate = inputInfo.defaultSampleRate
// printfn $"Sample rate = %f{sampleRate} (default)"
//
// let sampleFormat = SampleFormat.Float32
//
// let mutable inputParameters = StreamParameters()
// inputParameters.device                    <- defaultInputDevice
// inputParameters.channelCount              <- nChannels
// inputParameters.sampleFormat              <- sampleFormat 
// inputParameters.suggestedLatency          <- inputInfo.defaultHighInputLatency
// inputParameters.hostApiSpecificStreamInfo <- IntPtr.Zero


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
let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()


let stream = new Stream(inParams        = inputParameters    ,
                        outParams       = outputParameters   ,
                        sampleRate      = sampleRate         ,
                        framesPerBuffer = uint32 0           ,
                        streamFlags     = StreamFlags.ClipOff,
                        callback        = callback           ,
                        userData        = IntPtr.Zero        )
[<EntryPoint>]
let main _ =
  try
    let work = GcNormal
    printfn $"\nDoing {work}\n"
    let f() = churnGc 1_000_000
    match work with
    | GcCreateOnly ->
      withStartStop stream false f
    | GcNormal ->
      withStartStop stream true f
    | Normal ->
      withStartStop stream true awaitForever
    printfn "Terminating..."
    PortAudio.Terminate()
    printfn "Terminated"
  with
  | :? PortAudioException as e ->
      printfn "While creating the stream: %A %A" e.ErrorCode e.Message
      Environment.Exit(2)
  0