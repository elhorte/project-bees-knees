module BeesLib.PaStream


open System
open System.Threading.Tasks

open BeesUtil.WorkList
open PortAudioSharp
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open BeesLib.InputBuffer
open BeesUtil.Logger

// See Theory of Operation comment before main at the end of this file.


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> CbMessageQueue handler

/// <summary>
///   Creates a Stream.Callback that:
///   <list type="bullet">
///     <item><description> Allocates no memory because this is a system-level callback </description></item>
///     <item><description> Gets a <c>CbMessage</c> from the pool and fills it in        </description></item>
///     <item><description> Posts the <c>CbMessage</c> to the <c>cbMessageQueue</c>     </description></item>
///   </list>
/// </summary>
/// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
/// <param name="cbMessageQueue" > The <c>CbMessageQueue</c> to post to           </param>
/// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>
let makePaStreamCallback ( beesConfig     : BeesConfig             )
                         ( cbContextRef   : ResizeArray<CbContext> )
                         ( inputBuffer    : InputBuffer            )
                         : PortAudioSharp.Stream.Callback =
  PortAudioSharp.Stream.Callback(
    // This fun has to be here because of a limitation of the compiler, apparently.
    fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
      let cbContext = cbContextRef[0]
      inputBuffer.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr, cbContext) )

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
let makePaStream beesConfig inputParameters outputParameters sampleRate withEchoRef withLoggingRef  : CbContext * InputBuffer =
  let cbMessageWorkList = WorkList<CbMessage>()
  let cbContextRef = ResizeArray<CbContext>(1)  // indirection to solve the chicken or egg problem
  let inputBuffer = InputBuffer(beesConfig)
  let callback = makePaStreamCallback beesConfig cbContextRef inputBuffer
  let paStream = new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                           outParams       = Nullable<_>(outputParameters)        ,
                                           sampleRate      = sampleRate                           ,
                                           framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                           streamFlags     = StreamFlags.ClipOff                  ,
                                           callback        = callback                             ,
                                           userData        = Nullable()                           )
  let cbMessageQueue = makeAndStartCbMessageQueue cbMessageWorkList.HandleEvent
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
  cbContext, inputBuffer

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
