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
// CbMessage

/// This is the message that the callback sends to the managed-code handler.
type CbMessage = {
  mutable InputSamples         : IntPtr                
  mutable Output               : IntPtr                
  mutable FrameCount           : uint32                
  mutable TimeInfo             : StreamCallbackTimeInfo
  mutable StatusFlags          : StreamCallbackFlags   
  mutable UserDataPtr          : IntPtr                
  // more from the callback
  mutable SeqNum               : int
  mutable TimeStamp            : DateTime              
  mutable WithEcho             : bool                  
  mutable InputSamplesRingCopy : IntPtr                
  mutable SegCur               : Seg                   
  mutable SegOld               : Seg }
  
  with
  
  member m.SegOldest    = if m.SegOld.Active then m.SegOld else m.SegCur

  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

let makeCbMessage (ip: ItemPool<CbMessage>) (beesConfig: BeesConfig) (nRingFrames: int) =

  let timeInfo          = StreamCallbackTimeInfo() // Replace with actual time info.
  let primingOutputFlag = StreamCallbackFlags.PrimingOutput
  let newSeg()          = Seg(nRingFrames, beesConfig.InSampleRate)
  
  // Most initializer values here are placeholders that will be overwritten by the callback.
  // as this is an object recycled in a pool so there is no allocation.

  let cbMessage = {
    // args to the callback called by PortAudioSharp
    InputSamples         = IntPtr.Zero       
    Output               = IntPtr.Zero       
    FrameCount           = 0u                
    TimeInfo             = timeInfo          
    StatusFlags          = primingOutputFlag 
    UserDataPtr          = IntPtr.Zero       
    // more from the callback
    SeqNum               = 0
    TimeStamp            = DateTime.MinValue 
    WithEcho             = false             
    InputSamplesRingCopy = IntPtr 0          
    SegCur               = newSeg()          
    SegOld               = newSeg()           }
  cbMessage

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessagePool

type CbMessagePool = ItemPool<CbMessage>

let makeCbMessagePool (startCount  : int        )
                      (minCount    : int        )
                      (beesConfig  : BeesConfig )
                      (nRingFrames : int        ) : CbMessagePool =
  makeItemPool<CbMessage> startCount minCount (fun (ip: ItemPool<CbMessage>) -> makeCbMessage ip  beesConfig  nRingFrames)

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessageQueue

type CbMessageQueue = AsyncConcurrentQueue<PoolItem<CbMessage>>

   

  // static member test() =
  //   let startCount = 3
  //   let minCount   = 2
  //   let stream     = null 
  //   let startTime  = DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, CbMessageQueue(), logger)
  //   pool.Test()