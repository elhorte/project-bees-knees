module BeesLib.CbMessagePool

open System

open PortAudioSharp
open BeesLib.BeesConfig
open BeesUtil.AsyncConcurrentQueue
open BeesUtil.ItemPool
open BeesUtil.Util



let tbdDateTime = DateTime.MinValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Seg class, used by InputStream.  The ring buffer can comprise 0, 1, or 2 segs.

type Seg(head: int, tail: int, nRingFrames: int, inSampleRate: int) =
  let durationOf nFrames = TimeSpan.FromSeconds (float nFrames / float inSampleRate)
  let nFramesOf duration = int ((duration: TimeSpan).TotalMicroseconds / 1_000_000.0 * float inSampleRate)

  new (nRingFrames: int, inSampleRate: int) = Seg(0, 0, nRingFrames, inSampleRate)
  
  member val  Head     = head         with get, set
  member val  Tail     = tail         with get, set
  member val  TimeHead = tbdDateTime  with get, set
  member this.NFrames  = assert (this.Head >= this.Tail) ; this.Head - this.Tail
  member this.Duration = durationOf this.NFrames
  member this.TimeTail = this.TimeHead - this.Duration
  member this.Active   = this.NFrames <> 0
  member this.Copy()   = Seg(this.Head, this.Tail, nRingFrames, inSampleRate)
  member this.Reset()  = this.Head <- 0 ; this.Tail <- 0 ; assert (not this.Active)

  member this.NFramesOf duration = nFramesOf duration
  
  member this.AdvanceHead nFrames timeHead =
    let headNew = this.Head + nFrames
    assert (headNew <= nRingFrames)
    this.Head     <- headNew
    this.TimeHead <- timeHead

  /// Trim nFrames from the tail.  May result in an inactive Seg.
  member this.TrimTail nFrames  : unit =
    if this.NFrames > nFrames then  this.Tail <- this.Tail + nFrames
                              else  this.Reset()

type SampleType  = float32
type BufArray    = SampleType array
type Buf         = Buf    of BufArray
type BufRef      = BufRef of BufArray ref


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessage, CbMessagePool, CbMessageQueue

/// This is the message that the callback sends to the managed-code handler.
and CbMessage(beesConfig: BeesConfig) =
  inherit IPoolItem()

  let timeInfo          = StreamCallbackTimeInfo() // Replace with actual time info.
  let primingOutputFlag = StreamCallbackFlags.PrimingOutput

  // Most initializer values here are placeholders that will be overwritten by the callback.
  // as this is an object recycled in a pool so there is no allocation.

  // args to the callback called by PortAudioSharp
  member   val public InputSamples         = IntPtr.Zero           with get, set
  member   val public Output               = IntPtr.Zero           with get, set
  member   val public FrameCount           = 0u                    with get, set
  member   val public TimeInfo             = timeInfo              with get, set
  member   val public StatusFlags          = primingOutputFlag     with get, set
  member   val public UserDataPtr          = IntPtr.Zero           with get, set
  // more from the callback
  member   val public TimeStamp            = DateTime.MinValue     with get, set
  member   val public WithEcho             = false                 with get, set
  member   val public InputSamplesRingCopy = IntPtr 0              with get, set
  member   val public SegCur               = dummyInstance<Seg>()  with get, set
  member   val public SegOld               = dummyInstance<Seg>()  with get, set

  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

and CbMessagePool( bufSize    : int        ,
                   startCount : int        ,
                   minCount   : int        ,
                   beesConfig : BeesConfig ) =
  inherit ItemPool<CbMessage>(startCount, minCount, fun () -> CbMessage(beesConfig))

and CbMessageQueue = AsyncConcurrentQueue<CbMessage>
    

  // static member test() =
  //   let startCount = 3
  //   let minCount   = 2
  //   let stream     = null 
  //   let startTime  = DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, CbMessageQueue(), logger)
  //   pool.Test()