module BeesLib.PaStream


open System
open System.Runtime.InteropServices
open System.Threading
open System.Threading.Tasks

open PortAudioSharp
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.InputBuffer
open BeesLib.Logger

// See Theory of Operation comment before main at the end of this file.


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> CbMessageQueue handler

/// <summary>
///   Creates a Stream.Callback that:
///   <list type="bullet">
///     <item><description> Allocates no memory because this is a system-level callback </description></item>
///     <item><description> Ges a <c>CbMessage</c> from the pool and fills it in        </description></item>
///     <item><description> Posts the <c>CbMessage</c> to the <c>cbMessageQueue</c>     </description></item>
///   </list>
/// </summary>
/// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
/// <param name="cbMessageQueue" > The <c>CbMessageQueue</c> to post to           </param>
/// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>
let makeStreamCallback (beesConfig: BeesConfig) (cbContextRef: ResizeArray<CbContext>) (cbMessageQueue: CbMessageQueue)  : PortAudioSharp.Stream.Callback =
  let inputBuffer = InputBuffer(beesConfig, cbMessageQueue)
  PortAudioSharp.Stream.Callback(
    fun input output frameCount timeInfo statusFlags userDataPtr ->
      let cbContext = cbContextRef[0]
      let withEcho  = Volatile.Read &cbContext.WithEchoRef.contents
      let seqNum    = Volatile.Read &cbContext.SeqNumRef.contents
      let timeStamp = DateTime.Now
      if withEcho then
        let size = uint64 (frameCount * uint32 sizeof<float32>)
        Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
      Volatile.Write(cbContext.SeqNumRef, seqNum + 1)
      match cbContext.CbMessagePool.Take() with
      | None -> // Yikes, pool is empty
        cbContext.Logger.Add seqNum timeStamp "CbMessagePool is empty" null
        StreamCallbackResult.Continue
      | Some cbMessage ->
        if Volatile.Read &cbContext.WithLoggingRef.contents then
          cbContext.Logger.Add seqNum timeStamp "cb bufs=" cbMessage.PoolStats
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
        match cbContext.CbMessagePool.CountAvail with
        | 0 -> StreamCallbackResult.Complete // todo should continue?
        | _ -> inputBuffer.Callback(beesConfig, cbMessage)
               StreamCallbackResult.Continue )

//–––––––––––––––––––––––––––––––––––––

/// <summary>
///   Continuously receives messages from a CbMessageQueue;
///   processes each message with the provided function.
/// </summary>
/// <param name="workPerCallback"> A function to process each message.                     </param>
/// <param name="cbMessageQueue"    > A CbMessageQueue from which to receive the messages. </param>
let cbMessageQueueHandler workPerCallback (cbMessageQueue: CbMessageQueue) =
//let mutable callbackMessage = Unchecked.defaultof<CbMessage>
  let doOne (m: CbMessage) =
    let cbMessagePool = m.CbContext.CbMessagePool
    cbMessagePool.ItemUseBegin()
    workPerCallback m
    cbMessagePool.ItemUseEnd   m
  cbMessageQueue.iter doOne

//–––––––––––––––––––––––––––––––––––––
// CbMessageQueue

/// <summary>
///   Creates and starts a CbMessageQueue that will process CbMessages inserted by callbacks.
/// </summary>
/// <param name="workPerCallback">A function that processes a CbMessageQueueMessage</param>
/// <returns>Returns a started CbMessageQueue</returns>
let makeAndStartCbMessageQueue workPerCallback  : CbMessageQueue =
  let cbMessageQueue = CbMessageQueue()
  let handler() = cbMessageQueueHandler workPerCallback cbMessageQueue
  Task.Run handler |> ignore
  cbMessageQueue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudioSharp.Stream

/// <summary>Make the pool of CbMessages used by the stream callback</summary>
let makeCbMessagePool beesConfig stream cbMessageQueue logger =
  let bufSize    = 1024
  let startCount = Environment.ProcessorCount * 4    // many more than number of cores
  let minCount   = 4
  let bufRefMaker() = BufRef (ref (Array.zeroCreate<SampleType> bufSize))
  CbMessagePool(bufSize, startCount, minCount, beesConfig, stream, cbMessageQueue, logger, bufRefMaker)

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                               </param>
/// <param name="outputParameters"> Parameters for output audio stream                              </param>
/// <param name="sampleRate"      > Audio sample rate                                               </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output       </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging         </param>
/// <param name="cbMessageQueue"     > CbMessageQueue object handling audio stream                  </param>
/// <returns>A CbContext struct to be passed to each callback</returns>
let makePaStream beesConfig inputParameters outputParameters sampleRate withEchoRef withLoggingRef cbMessageQueue  : CbContext =
  let cbContextRef = ResizeArray<CbContext>(1)  // indirection to solve the chicken or egg problem
  let callback = makeStreamCallback beesConfig cbContextRef cbMessageQueue
  let paStream = new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                           outParams       = Nullable<_>(outputParameters)        ,
                                           sampleRate      = sampleRate                           ,
                                           framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                           streamFlags     = StreamFlags.ClipOff                  ,
                                           callback        = callback                             ,
                                           userData        = Nullable()                           )
  let startTime = DateTime.Now
  let logger = Logger(8000, startTime)
  let cbContext = {
    BeesConfig     = beesConfig
    PaStream       = paStream
    CbMessagePool  = makeCbMessagePool beesConfig paStream cbMessageQueue logger
    CbMessageQueue = cbMessageQueue
    Logger         = logger
    WithEchoRef    = withEchoRef
    WithLoggingRef = withLoggingRef
    StartTime      = startTime
    SeqNumRef      = ref 1  }
  cbContextRef.Add(cbContext) // and here is where we provide the cbContext struct to be used by the callback
  cbContext

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
