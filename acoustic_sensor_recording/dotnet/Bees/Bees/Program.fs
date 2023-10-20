
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open Bees.AsyncConcurrentQueue
open FSharp.Control
open PortAudioSharp
open Bees.Logger
open Bees.PortAudioUtils
open Bees.BufferPool

/// Callback context
[<Struct>]
type CbContext = {
  stream      : Stream
  withEchoRef : bool ref
  streamQueue : StreamQueue
  bufferPool  : BufferPool
  startTime   : DateTime
  log         : Logger
  seqNo       : int ref  }

/// Callback args in a more usable form for managed code.
and [<Struct>]
    CbMessage = {
  // the callback args
  input       : IntPtr // for debugging
  output      : IntPtr
  frameCount  : uint32
  timeInfo    : StreamCallbackTimeInfo
  statusflags : StreamCallbackFlags
  userDataPtr : IntPtr
  // more from the callback
  cbContext   : CbContext
  withEcho    : bool
  seqNo       : int
  inputCopy   : Buf
  timestamp   : DateTime }

and StreamQueue = CbMessage AsyncConcurrentQueue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> StreamQueue handler

/// <summary>
///   Creates a Stream.Callback that:
///   <list type="bullet">
///     <item><description> Allocates no memory because this is a system-level callback </description></item>
///     <item><description> Makes a <c>CbMessage</c> struct from the callback arguments </description></item>
///     <item><description> Posts the <c>CbMessage</c> to the <c>streamQueue</c>        </description></item>
///   </list>
/// </summary>
/// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
/// <param name="streamQueue" > The <c>StreamQueue</c> to post to              </param>
/// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>
let makeStreamCallback (cbContextRef: CbContext ResizeArray) (streamQueue: StreamQueue)  : Stream.Callback =
  Stream.Callback(
    fun input output frameCount timeInfo statusflags userDataPtr ->
      let cbContext = cbContextRef[0]
      let withEcho  = Volatile.Read(cbContext.withEchoRef)
      let seqNo     = Volatile.Read cbContext.seqNo
      let inputCopy = cbContext.bufferPool.Take()
      let timeStamp = DateTime.Now
      if withEcho then
        let size = uint64 (frameCount * uint32 sizeof<float32>)
        Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
      Volatile.Write(cbContext.seqNo, seqNo + 1)
      do
        let (Buf buf) = inputCopy
        Marshal.Copy(input, buf, startIndex = 0, length = (int frameCount))
      cbContext.log.add seqNo timeStamp "cb bufs=" cbContext.bufferPool.Size
      { // the callback args
        input       = input
        output      = output
        frameCount  = frameCount
        timeInfo    = timeInfo
        statusflags = statusflags
        userDataPtr = userDataPtr
        // more from the callback
        cbContext   = cbContext
        withEcho    = withEcho 
        seqNo       = seqNo
        inputCopy   = inputCopy
        timestamp   = timeStamp }
      |> streamQueue.add
      match cbContext.bufferPool.Size with
      | 0 -> StreamCallbackResult.Complete
      | _ -> StreamCallbackResult.Continue )

//–––––––––––––––––––––––––––––––––––––

/// <summary>
///   Continuously receives messages from a StreamQueue,
///   processes each message with the provided function.
/// </summary>
/// <param name="workPerCallback"> A function to process each message.               </param>
/// <param name="streamQueue"    > A StreamQueue from which to receive the messages. </param>
let streamQueueHandler workPerCallback (streamQueue: StreamQueue) =
//let mutable callbackMessage = Unchecked.defaultof<CbMessage>
  let doOne (m: CbMessage) =
    let bufferPool = m.cbContext.bufferPool
    bufferPool.BufUseBegin m.inputCopy
    workPerCallback m
    bufferPool.BufUseEnd   m.inputCopy
  streamQueue.iter doOne

//–––––––––––––––––––––––––––––––––––––
// StreamQueue

/// <summary>
///   Creates and starts a StreamQueue that is ready to process CbMessage structs posted by callbacks.
/// </summary>
/// <param name="workPerCallback">A function that processes a StreamQueueMessage</param>
/// <returns>Returns a started StreamQueue</returns>
let makeAndStartStreamQueue workPerCallback  : StreamQueue =
  let streamQueue = StreamQueue()
  let handler() = streamQueueHandler workPerCallback streamQueue
  Task.Run handler |> ignore
  streamQueue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudioSharp.Stream

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                         </param>
/// <param name="outputParameters"> Parameters for output audio stream                        </param>
/// <param name="sampleRate"      > Audio sample rate                                         </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output </param>
/// <param name="streamQueue"     > StreamQueue object handling audio stream                  </param>
/// <returns>A Stream object representing created audio stream</returns>
let makeStream inputParameters outputParameters sampleRate withEchoRef (streamQueue: StreamQueue)  : CbContext =
  let cbContextRef = ResizeArray<CbContext>(1)
  let callback = makeStreamCallback cbContextRef streamQueue
  let stream = new Stream(inParams        = Nullable<_>(inputParameters )        ,
                          outParams       = Nullable<_>(outputParameters)        ,
                          sampleRate      = sampleRate                           ,
                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                          streamFlags     = StreamFlags.ClipOff                  ,
                          callback        = callback                             ,
                          userData        = Nullable()                           )
  let startTime = DateTime.Now
  let cbContext = {
    stream      = stream
    withEchoRef = withEchoRef
    streamQueue = streamQueue
    bufferPool  = BufferPool(32, 4) //? todo magic number to cover latency btw callback and agent
    startTime   = startTime
    log         = Logger(8000, startTime)
    seqNo       = ref 1  } 
  cbContextRef.Add(cbContext)
  cbContext

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// App

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation() =
  let defaultInput = PortAudio.DefaultInputDevice         in printfn $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in printfn $"Number of channels = %d{nChannels}"
  let sampleRate   = inputInfo.defaultSampleRate          in printfn $"Sample rate = %f{sampleRate} (default)"
  let inputParameters = StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = SampleFormat.Float32              ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  printfn $"%s{deviceInfoToString inputInfo}"
  printfn $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in printfn $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = SampleFormat.Float32                ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  printfn $"%s{deviceInfoToString outputInfo}"
  printfn $"outputParameters=%A{outputParameters}"
  sampleRate, inputParameters, outputParameters

/// This is the work we will do on each callback.
/// It is called by the agent, which
/// - got the data from a queue of PortAudio callback data
/// - transformed the data to a form more convenient for us
/// - and then called us.
/// There are no real-time restrictions on this work,
/// since it is not called during the low-level PortAudio callback.
let workPerCallback (m: CbMessage) =
  Volatile.Write(m.cbContext.withEchoRef, false)
  let microseconds = floatToMicrosecondsFractionOnly m.timeInfo.currentTime
  let percentCPU   = m.cbContext.stream.CpuLoad * 100.0
  let sDebug = sprintf "%3d: %A  %A %A" m.seqNo m.timestamp "a  bufs=" m.cbContext.bufferPool.Size
  let s = sprintf($"work: %6d{microseconds} frameCount=%A{m.frameCount} cpuLoad=%5.1f{percentCPU}%%")
  Console.WriteLine($"{sDebug}   ––   {s}")


/// Run the stream for a while, then stop it and terminate PortAudio.
let run (stream: Stream) = task {
  printfn "Starting..."    ; stream.Start()
  printfn "Reading..."     ; do! Task.Delay 2
  printfn "Stopping..."    ; stream.Stop()
  printfn "Stopped"
  printfn "Terminating..." ; PortAudio.Terminate()
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// Main

[<EntryPoint>]
let main _ =
  let mutable withEchoRef = ref true
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  let streamQueue = makeAndStartStreamQueue workPerCallback
  let cbContext   = makeStream inputParameters outputParameters sampleRate withEchoRef streamQueue
  task {
    try
      do! run cbContext.stream
    with
    | :? PortAudioException as e -> exitWithTrouble 2 e "Running PortAudio Stream" }
  |> Task.WaitAll
  printfn "\nLog:\n%s" (cbContext.log.ToString())
  0
