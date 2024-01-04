module BeesLib.CbMessagePool


open System

open System.Threading
open Util
open PortAudioSharp
open BeesLib.BeesConfig
open BeesLib.Logger
open BeesLib.AsyncConcurrentQueue
open BeesLib.ItemPool


type SampleType  = float32
type BufArray    = SampleType array
type Buf         = Buf    of BufArray
type BufRef      = BufRef of BufArray ref
type BufRefMaker = unit -> BufRef


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessage pool

// The callback uses this for context.
[<Struct>]
type CbContext = {
  BeesConfig     : BeesConfig
  PaStream       : PortAudioSharp.Stream
  CbMessagePool  : CbMessagePool // The callback grabs a CbMessage from here.
  CbMessageQueue : CbMessageQueue   // The callback fills in the CbMessage and enqueues it here.
  Logger         : Logger
  WithEchoRef    : bool ref
  WithLoggingRef : bool ref
  StartTime      : DateTime
  SeqNumRef      : int ref }

/// This is the message that the callback sends to the managed-code handler.
and CbMessage(beesConfig: BeesConfig, paStream: PortAudioSharp.Stream, cbMessageQueue: CbMessageQueue, logger: Logger, bufSize: int, bufRefMaker: BufRefMaker) =
  inherit IPoolItem()

  let cbMessagePoolPlaceHolder = CbMessagePool(bufSize, 0, 0, beesConfig, paStream, cbMessageQueue, logger, bufRefMaker)
  let ti = StreamCallbackTimeInfo() // Replace with actual time info.
  let sf = StreamCallbackFlags.PrimingOutput
  let bufRef = bufRefMaker()

  // Most initializer values here are placeholders that will be overwritten by the callback.

  let cbCtxDummy: CbContext = {
    BeesConfig     = beesConfig
    PaStream       = paStream
    CbMessagePool  = cbMessagePoolPlaceHolder
    CbMessageQueue = cbMessageQueue
    Logger         = logger
    WithEchoRef    = ref false
    WithLoggingRef = ref false
    StartTime      = DateTime.Now
    SeqNumRef      = ref 0  }

  // the callback args
  member   val public InputSamples        : IntPtr                 = IntPtr.Zero        with get, set
  member   val public Output              : IntPtr                 = IntPtr.Zero        with get, set
  member   val public FrameCount          : uint32                 = 0u                 with get, set
  member   val public TimeInfo            : StreamCallbackTimeInfo = ti                 with get, set
  member   val public StatusFlags         : StreamCallbackFlags    = sf                 with get, set
  member   val public UserDataPtr         : IntPtr                 = IntPtr.Zero        with get, set
  // more from the callback
  member   val public CbContext           : CbContext              = cbCtxDummy         with get, set
  member   val public WithEcho            : bool                   = false              with get, set
  member   val public InputSamplesCopyRef : BufRef                 = bufRef             with get, set
  member   val public Timestamp           : DateTime               = DateTime.MinValue  with get, set
  
  member   m.PoolStats with get() = sprintf "pool=%A:%A" m.CbContext.CbMessagePool.CountAvail m.CbContext.CbMessagePool.CountInUse
  
  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

and CbMessageQueue = AsyncConcurrentQueue<CbMessage>

and CbMessagePool( bufSize        : int                   ,
                   startCount     : int                   ,
                   minCount       : int                   ,
                   beesConfig     : BeesConfig            ,
                   stream         : PortAudioSharp.Stream ,
                   cbMessageQueue : CbMessageQueue        ,
                   logger         : Logger                ,
                   bufRefMaker    : BufRefMaker           ) =
  inherit ItemPool<CbMessage>(startCount, minCount, fun () -> CbMessage(beesConfig, stream, cbMessageQueue, logger, bufSize, bufRefMaker))
    

  // static member test() =
  //   let startCount = 3
  //   let minCount   = 2
  //   let stream     = null 
  //   let startTime  = DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, CbMessageQueue(), logger)
  //   pool.Test()