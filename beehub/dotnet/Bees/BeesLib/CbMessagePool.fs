module BeesLib.CbMessagePool


open System

open Util
open PortAudioSharp
open BeesLib.Logger
open BeesLib.AsyncConcurrentQueue
open BeesLib.ItemPool


type BufType     = float32
type BufArray    = BufType array
type Buf         = Buf    of BufArray
type BufRef      = BufRef of BufArray ref
type BufRefMaker = unit -> BufRef

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Config

type Config = {
  LocationId     : int
  HiveId         : int
  PrimaryDir     : string
  MonitorDir     : string
  PlotDir        : string
  bufferDuration : TimeSpan
  nChannels      : int
  inSampleRate   : int  }

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessage pool

/// The callback is given this.
[<Struct>]
type CbContext = {
  config         : Config
  stream         : Stream
  streamQueue    : StreamQueue
  logger         : Logger
  cbMessagePool  : CbMessagePool
  withEchoRef    : bool ref
  withLoggingRef : bool ref
  startTime      : DateTime
  seqNumRef      : int ref }

/// The callback sends this message to the managed-code handler.
and CbMessage(config: Config, stream: Stream, streamQueue: StreamQueue, logger: Logger, bufSize: int, bufRefMaker: BufRefMaker) =
  inherit IPoolItem()

  let cbMessagePoolPlaceHolder = CbMessagePool(bufSize, 0, 0, config, stream, streamQueue, logger, bufRefMaker)
  let ti = StreamCallbackTimeInfo() // Replace with actual time info.
  let sf = StreamCallbackFlags.PrimingOutput
  let bufRef = bufRefMaker()

  // Most initializer values here are placeholders that will be overwritten by the callback.

  let cbCtxTemp: CbContext = {
    config         = config
    stream         = stream
    streamQueue    = streamQueue
    logger         = logger
    cbMessagePool  = cbMessagePoolPlaceHolder
    withEchoRef    = ref false
    withLoggingRef = ref false
    startTime      = DateTime.Now
    seqNumRef      = ref 0  }

  // the callback args
  member   val public InputSamples        : IntPtr                 = IntPtr.Zero        with get, set
  member   val public Output              : IntPtr                 = IntPtr.Zero        with get, set
  member   val public FrameCount          : uint32                 = uint32 0           with get, set
  member   val public TimeInfo            : StreamCallbackTimeInfo = ti                 with get, set
  member   val public StatusFlags         : StreamCallbackFlags    = sf                 with get, set
  member   val public UserDataPtr         : IntPtr                 = IntPtr.Zero        with get, set
  // more from the callback
  member   val public CbContext           : CbContext              = cbCtxTemp          with get, set
  member   val public WithEcho            : bool                   = false              with get, set
  member   val public InputSamplesCopyRef : BufRef                 = bufRef             with get, set
  member   val public Timestamp           : DateTime               = DateTime.MinValue  with get, set
  
  member   m.PoolStats with get() =
    sprintf "pool=%A:%A" m.CbContext.cbMessagePool.CountAvail m.CbContext.cbMessagePool.CountInUse
  
  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

and StreamQueue = CbMessage AsyncConcurrentQueue

and CbMessagePool(bufSize     : int         ,
                  startCount  : int         ,
                  minCount    : int         ,
                  config      : Config      ,
                  stream      : Stream      ,
                  streamQueue : StreamQueue ,
                  logger      : Logger      ,
                  bufRefMaker : BufRefMaker ) =
  inherit ItemPool<CbMessage>(startCount, minCount, fun () -> CbMessage(config, stream, streamQueue, logger, bufSize, bufRefMaker))
    

  // static member test() =
  //   let startCount = 3
  //   let minCount   = 2
  //   let stream     = null 
  //   let startTime  = DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, StreamQueue(), logger)
  //   pool.Test()