module BeesLib.CbMessagePool

open BeesUtil.Util

open System

open PortAudioSharp
open BeesLib.BeesConfig
open BeesUtil.Logger
open BeesUtil.AsyncConcurrentQueue
open BeesUtil.ItemPool


type SampleType  = float32
type BufArray    = SampleType array
type Buf         = Buf    of BufArray
type BufRef      = BufRef of BufArray ref


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessage pool

// The callback uses this for context.
[<Struct>]
type CbContext = {
  BeesConfig     : BeesConfig
  PaStream       : PortAudioSharp.Stream
  CbMessagePool  : CbMessagePool    // The callback grabs a CbMessage from here.
  CbMessageQueue : CbMessageQueue   // The callback fills in the CbMessage and enqueues it here.
  Logger         : Logger
  WithEchoRef    : bool ref
  WithLoggingRef : bool ref
  StartTime      : DateTime
  SeqNumRef      : int ref }

/// This is the message that the callback sends to the managed-code handler.
and CbMessage() =
  inherit IPoolItem()

  let ti = StreamCallbackTimeInfo() // Replace with actual time info.
  let sf = StreamCallbackFlags.PrimingOutput
  let cbMessagePoolDummy = dummyInstance<CbMessagePool>()
  let intPtr0 = IntPtr 0

  // Most initializer values here are placeholders that will be overwritten by the callback.


  // args to the callback called by PortAudioSharp
  member   val public InputSamples          : IntPtr                 = IntPtr.Zero        with get, set
  member   val public Output                : IntPtr                 = IntPtr.Zero        with get, set
  member   val public FrameCount            : uint32                 = 0u                 with get, set
  member   val public TimeInfo              : StreamCallbackTimeInfo = ti                 with get, set
  member   val public StatusFlags           : StreamCallbackFlags    = sf                 with get, set
  member   val public UserDataPtr           : IntPtr                 = IntPtr.Zero        with get, set
  // more from the callback
  member   val public CbMessagePool         : CbMessagePool          = cbMessagePoolDummy with get, set
  member   val public Timestamp             : DateTime               = DateTime.MinValue  with get, set
  member   val public WithEcho              : bool                   = false              with get, set
  member   val public InputSamplesRingCopy  : IntPtr                 = intPtr0            with get, set
  
  member   m.PoolStats with get() = sprintf "pool=%A:%A" m.CbMessagePool.CountAvail m.CbMessagePool.CountInUse
  
  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

and CbMessageQueue = AsyncConcurrentQueue<CbMessage>

and CbMessagePool( bufSize    : int ,
                   startCount : int ,
                   minCount   : int ) =
  inherit ItemPool<CbMessage>(startCount, minCount, fun () -> CbMessage())
    

  // static member test() =
  //   let startCount = 3
  //   let minCount   = 2
  //   let stream     = null 
  //   let startTime  = DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, CbMessageQueue(), logger)
  //   pool.Test()