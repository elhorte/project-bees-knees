
open System
open System.Runtime.InteropServices
open PortAudioSharp


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudio Utils

let exitWithTrouble exitValue (e: PortAudioException) message =
  printfn "Trouble: %s: %A %A" message e.ErrorCode e.Message
  Environment.Exit exitValue


/// Load the native library and initialize the PortAudio library.  
let initPortAudio() =
  try
    PortAudio.LoadNativeLibrary()
    PortAudio.Initialize()
  with
  | :? PortAudioException as e -> exitWithTrouble 2 e "Initializing PortAudio"


let floatToMicrosecondsFractionOnly (time: float) : int =
  int (1_000_000.0 * (time % 1.0))

/// Contains the callback arguments plus the Stream.
[<Struct>]
type StreamCallbackData = {
  input       : IntPtr
  output      : IntPtr
  frameCount  : uint32
  timeInfo    : StreamCallbackTimeInfo
  statusFlags : StreamCallbackFlags
  userDataPtr : IntPtr
  streamRef   : ResizeArray<Stream> }

// Make a Stream.Callback that:
// - puts the args into a StreamCallbackData
// - passes it to the given function
let makeStreamCallback streamRef f =
  Stream.Callback(
    fun input output frameCount timeInfo statusFlags userDataPtr ->
      let callbackData =
        { input       = input
          output      = output
          frameCount  = frameCount
          timeInfo    = timeInfo
          statusFlags = statusFlags
          userDataPtr = userDataPtr
          streamRef   = streamRef   }
      f callbackData )

/// DeviceInfo to a string, replacement for missing ToString()  
let deviceInfoToString (deviceInfo: DeviceInfo) : string =
  sprintf @"DeviceInfo [
  name=%s
  hostApi=%d
  maxInputChannels=%i
  maxOutputChannels=%i
  defaultSampleRate=%f
  defaultLowInputLatency=%f
  defaultLowOutputLatency=%f
  defaultHighInputLatency=%f
  defaultHighOutputLatency=%f
]"  
    deviceInfo.name 
    deviceInfo.hostApi
    deviceInfo.maxInputChannels 
    deviceInfo.maxOutputChannels 
    deviceInfo.defaultSampleRate 
    deviceInfo.defaultLowInputLatency 
    deviceInfo.defaultLowOutputLatency 
    deviceInfo.defaultHighInputLatency 
    deviceInfo.defaultHighOutputLatency 


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// StreamAgent

// A more client-friendly form for the data in a StreamCallbackArgs.
[<Struct>]
type StreamAgentMessage = {
  input       : float32 array
  output      : float32 array
  frameCount  : uint32
  timeInfo    : StreamCallbackTimeInfo
  statusFlags : StreamCallbackFlags
  userDataPtr : IntPtr
  stream      : Stream }

type StreamAgent = StreamCallbackData MailboxProcessor

/// Make a StreamAgentMessage from the callback arguments.
/// The main job here is to copy the input buffer out of driver memory.
let makeAgentMessage (callbackArgs: StreamCallbackData)  : StreamAgentMessage =
  let c = callbackArgs
  let inputCopy  = Array.zeroCreate<float32> (int c.frameCount)
  let outputCopy = Array.zeroCreate<float32> (int c.frameCount)
  Marshal.Copy(c.input, inputCopy, startIndex = 0, length = (int c.frameCount))
  let stream = c.streamRef[0]
  { input       = inputCopy
    output      = outputCopy
    frameCount  = c.frameCount
    timeInfo    = c.timeInfo
    statusFlags = c.statusFlags
    userDataPtr = c.userDataPtr
    stream      = stream        }

/// Receive messages to an agent and process them.
let agentHandler f (agent: StreamAgent) =
  let rec handleAMessage() = async {
    let! callbackArgs = agent.Receive()
    f (makeAgentMessage callbackArgs)
    return! handleAMessage() }
  handleAMessage()

/// Create an agent that will process callback messages from the audio stream,
/// then start it and return it.
/// Processing is done by theWork, a function that takes a StreamAgentMessage.
let makeAndStartAudioAgent theWork  : StreamAgent =
  let handler agent = agentHandler theWork agent
  MailboxProcessor.Start(handler)

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Stream

/// Create an audio stream, to be started by the caller.  
let makeStream inputParameters sampleRate (audioAgent: StreamAgent)  : Stream =
  let streamRef = ResizeArray<Stream>()
  let callbackWork callbackArgs =
    audioAgent.Post callbackArgs
    StreamCallbackResult.Continue
  let callback = makeStreamCallback streamRef callbackWork
  let stream = new Stream(inParams        = inputParameters                      ,
                          outParams       = Nullable()                           ,
                          sampleRate      = sampleRate                           ,
                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                          streamFlags     = StreamFlags.ClipOff                  ,
                          callback        = callback                             ,
                          userData        = Nullable()                           )
  streamRef.Add(stream)
  stream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters. 
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput in printfn $"%s{deviceInfoToString inputInfo}"
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels} (max)"
  let sampleRate   = inputInfo.defaultSampleRate          in printfn $"Sample rate = %f{sampleRate} (default)"
  let inputParameters = StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  sampleRate, inputParameters

/// This is the work we will do on each callback.
/// It is called by the agent, which
/// - got the data from a queue of PortAudio callback data
/// - transformed the data to a form more convenient for us
/// - and then called us.
/// There are no real-time restrictions on this work, 
/// since it is not called during the low-level PortAudio callback.
let workToDo (m: StreamAgentMessage) =
  let microseconds = floatToMicrosecondsFractionOnly m.timeInfo.currentTime
  let percentCPU   = m.stream.CpuLoad * 100.0
  printfn $"  callback: %d{microseconds} frameCount=%A{m.frameCount} cpuLoad=%5.1f{percentCPU}%%"
  
/// Run the stream for a while, then stop it and terminate PortAudio.
let run (stream: Stream) =
  printfn "Starting..."    ; stream.Start()
  printfn "Reading..."     ; Threading.Thread.Sleep(50)
  printfn "Stopping..."    ; stream.Stop() 
  printfn "Stopped"
  printfn "Terminating..." ; PortAudio.Terminate()
  printfn "Terminated"

//–––––––––––––––––––––––––––––––––––––
// Main

[<EntryPoint>]
let main _ =
  initPortAudio()
  let sampleRate, inputParameters = prepareArgumentsForStreamCreation()
  let audioAgent = makeAndStartAudioAgent workToDo
  let stream = makeStream inputParameters sampleRate audioAgent
  try
    run stream
  with
  | :? PortAudioException as e -> exitWithTrouble 2 e "Running PortAudio Stream"

  0
