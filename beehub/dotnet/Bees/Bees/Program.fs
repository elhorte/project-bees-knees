
open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open FSharp.Control
open PortAudioSharp
open Bees.PortAudioUtils
open Bees.CbMessagePool
open Bees.Logger

// See Theory of Operation comment before main at the end of this file.

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> StreamQueue handler

/// <summary>
///   Creates a Stream.Callback that:
///   <list type="bullet">
///     <item><description> Allocates no memory because this is a system-level callback </description></item>
///     <item><description> Ges a <c>CbMessage</c> from the pool and fills it in        </description></item>
///     <item><description> Posts the <c>CbMessage</c> to the <c>streamQueue</c>        </description></item>
///   </list>
/// </summary>
/// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
/// <param name="streamQueue" > The <c>StreamQueue</c> to post to              </param>
/// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>
let makeStreamCallback (cbContextRef: CbContext ResizeArray) (streamQueue: StreamQueue)  : Stream.Callback =
  Stream.Callback(
    fun input output frameCount timeInfo statusFlags userDataPtr ->
      let cbContext = cbContextRef[0]
      let withEcho  = Volatile.Read(cbContext.withEchoRef)
      let seqNum    = Volatile.Read cbContext.seqNumRef
      let timeStamp = DateTime.Now
      if withEcho then
        let size = uint64 (frameCount * uint32 sizeof<float32>)
        Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
      Volatile.Write(cbContext.seqNumRef, seqNum + 1)
      match cbContext.cbMessagePool.Take() with
      | None -> // Yikes, pool is empty
        cbContext.logger.Add seqNum timeStamp "CbMessagePool is empty" null
        StreamCallbackResult.Continue
      | Some cbMessage ->
        do
          let (Buf buf) = cbMessage.InputSamplesCopy
          Marshal.Copy(input, buf, startIndex = 0, length = (int frameCount))
        if Volatile.Read(cbContext.withLoggingRef) then
          cbContext.logger.Add seqNum timeStamp "cb bufs=" cbMessage.PoolStats
        // the callback args
        cbMessage.InputSamples <- input
        cbMessage.Output       <- output
        cbMessage.FrameCount   <- frameCount
        cbMessage.TimeInfo     <- timeInfo
        cbMessage.StatusFlags  <- statusFlags
        cbMessage.UserDataPtr  <- userDataPtr
        // more from the callback
        cbMessage.CbContext    <- cbContext
        cbMessage.WithEcho     <- withEcho 
        cbMessage.SeqNum       <- seqNum
        cbMessage.Timestamp    <- timeStamp
        cbMessage |> streamQueue.add
        match cbContext.cbMessagePool.CountAvail with
        | 0 -> StreamCallbackResult.Complete
        | _ -> StreamCallbackResult.Continue )

//–––––––––––––––––––––––––––––––––––––

/// <summary>
///   Continuously receives messages from a StreamQueue;
///   processes each message with the provided function.
/// </summary>
/// <param name="workPerCallback"> A function to process each message.               </param>
/// <param name="streamQueue"    > A StreamQueue from which to receive the messages. </param>
let streamQueueHandler workPerCallback (streamQueue: StreamQueue) =
//let mutable callbackMessage = Unchecked.defaultof<CbMessage>
  let doOne (m: CbMessage) =
    let cbMessagePool = m.CbContext.cbMessagePool
    cbMessagePool.ItemUseBegin()
    workPerCallback m
    cbMessagePool.ItemUseEnd   m
  streamQueue.iter doOne

//–––––––––––––––––––––––––––––––––––––
// StreamQueue

/// <summary>
///   Creates and starts a StreamQueue that will process CbMessages inserted by callbacks.
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

/// <summary>Make the pool of CbMessages used by the stream callback</summary>
let makeCbMessagePool stream streamQueue logger =
  let bufSize    = 1024
  let startCount = Environment.ProcessorCount * 4    // many more than number of cores
  let minCount   = 4
  CbMessagePool(bufSize, startCount, minCount, stream, streamQueue, logger)

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                         </param>
/// <param name="outputParameters"> Parameters for output audio stream                        </param>
/// <param name="sampleRate"      > Audio sample rate                                         </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging   </param>
/// <param name="streamQueue"     > StreamQueue object handling audio stream                  </param>
/// <returns>A CbContext struct to be passed to each callback</returns>
let makeStream inputParameters outputParameters sampleRate withEchoRef withLoggingRef (streamQueue: StreamQueue)  : CbContext =
  let cbContextRef = ResizeArray<CbContext>(1)  // indirection to solve the chicken or egg problem
  let callback = makeStreamCallback cbContextRef streamQueue
  let stream = new Stream(inParams        = Nullable<_>(inputParameters )        ,
                          outParams       = Nullable<_>(outputParameters)        ,
                          sampleRate      = sampleRate                           ,
                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                          streamFlags     = StreamFlags.ClipOff                  ,
                          callback        = callback                             ,
                          userData        = Nullable()                           )
  let startTime = DateTime.Now
  let logger = Logger(8000, startTime)
  let cbContext = {
    stream         = stream
    streamQueue    = streamQueue
    logger         = logger
    cbMessagePool  = makeCbMessagePool stream streamQueue logger
    withEchoRef    = withEchoRef
    withLoggingRef = withLoggingRef
    startTime      = startTime
    seqNumRef      = ref 1  }
  cbContextRef.Add(cbContext) // and here is where we provide the cbContext struct to be used by the callback
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

// for debug
let printCallback (m: CbMessage) =
  let microseconds = floatToMicrosecondsFractionOnly m.TimeInfo.currentTime
  let percentCPU   = m.CbContext.stream.CpuLoad * 100.0
  let sDebug = sprintf "%3d: %A %s" m.SeqNum m.Timestamp m.PoolStats
  let sWork  = sprintf $"work: %6d{microseconds} frameCount=%A{m.FrameCount} cpuLoad=%5.1f{percentCPU}%%"
  Console.WriteLine($"{sDebug}   ––   {sWork}")

/// This is the work to do immediately after each callback.
/// There are no real-time restrictions on this work,
/// since it is not called during the low-level PortAudio callback.
let workPerCallback (m: CbMessage) =
//printCallback m
  ()

/// Run the stream for a while, then stop it and terminate PortAudio.
let run (stream: Stream) = task {
  printfn "Starting..."    ; stream.Start()
  printfn "Reading..."     ; do! Task.Delay 500
  printfn "Stopping..."    ; stream.Stop()
  printfn "Stopped"
  printfn "Terminating..." ; PortAudio.Terminate()
  printfn "Terminated" }

//–––––––––––––––––––––––––––––––––––––
// Main

/// Main does the following:
/// - Initialize PortAudio.
/// - Create everything the callback will need.
///   - sampleRate, inputParameters, outputParameters
///   - a StreamQueue, which
///     - accepts a CbMessage from each callback
///     - calls the given handler asap for each CbMessage queued
///   - a CbContext struct, which is passed to each callback
/// - runs the streamQueue
/// The audio callback is designed to do as little as possible at interrupt time:
/// - grabs a CbMessage from a preallocated ItemPool
/// - copies the input data buf into the CbMessage
/// - inserts the CbMessage into in the StreamQueue for later processing

[<EntryPoint>]
let main _ =
//Bees.CbMessageItemPool.CbMessagePool.test()
  let mutable withEchoRef    = ref false
  let mutable withLoggingRef = ref true
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation()
  let streamQueue = makeAndStartStreamQueue workPerCallback
  let cbContext   = makeStream inputParameters outputParameters sampleRate withEchoRef withLoggingRef streamQueue
  task {
    try
      do! run cbContext.stream
    with
    | :? PortAudioException as e -> exitWithTrouble 2 e "Running PortAudio Stream" }
  |> Task.WaitAll
  printfn "%s" (cbContext.logger.ToString())
  0
