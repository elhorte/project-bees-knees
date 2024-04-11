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

type Seg = {
  mutable Tail     : int
  mutable Head     : int
  mutable TimeHead : DateTime
  NRingFrames      : int
  InSampleRate     : int  }
  
  with

  static member New (head: int) (tail: int) (nRingFrames: int) (inSampleRate: int) =
    assert (head >= tail)
    let seg = {
      Tail         = tail
      Head         = head
      TimeHead     = tbdDateTime
      NRingFrames  = nRingFrames
      InSampleRate = inSampleRate  }
    seg

  static member NewEmpty (nRingFrames: int) (inSampleRate: int) =  Seg.New 0 0 nRingFrames inSampleRate

  member seg.Copy() = Seg.New seg.Head seg.Tail seg.NRingFrames seg.InSampleRate

    
  member seg.durationOf nFrames = TimeSpan.FromSeconds (float nFrames / float seg.InSampleRate)
  member seg.nFramesOf duration = int ((duration: TimeSpan).TotalMicroseconds / 1_000_000.0 * float seg.InSampleRate)
  
  member seg.NFrames  = seg.Head - seg.Tail
  member seg.Duration = seg.durationOf seg.NFrames
  member seg.TimeTail = seg.TimeHead - seg.Duration
  member seg.Active   = seg.NFrames <> 0
  member seg.Reset()  = seg.Head <- 0 ; seg.Tail <- 0 ; assert (not seg.Active)

  member seg.NFramesOf duration = seg.nFramesOf duration
  
  member seg.AdvanceHead nFrames timeHead =
    let headNew = seg.Head + nFrames
    assert (headNew <= seg.NRingFrames)
    seg.Head     <- headNew
    seg.TimeHead <- timeHead
  
  member seg.Print name = $"{name} {seg.Tail}.{seg.Head}"



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
  mutable SeqNum               : uint64
  mutable TimeStamp            : DateTime              
  mutable WithEcho             : bool                  
  mutable InputSamplesRingCopy : IntPtr                
  mutable SegCur               : Seg                   
  mutable SegOld               : Seg }
  
  with
  
  member m.SegOldest    = if m.SegOld.Active then m.SegOld else m.SegCur

  override m.ToString() = sprintf "%A %A" m.SeqNum m.TimeInfo

  static member New (ip: ItemPool<CbMessage>) (beesConfig: BeesConfig) (nRingFrames: int) =
    let timeInfo          = StreamCallbackTimeInfo() // Replace with actual time info.
    let primingOutputFlag = StreamCallbackFlags.PrimingOutput
    let newSeg()          = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
    
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
      SeqNum               = 0UL
      TimeStamp            = DateTime.MinValue 
      WithEcho             = false             
      InputSamplesRingCopy = IntPtr 0          
      SegCur               = newSeg()          
      SegOld               = newSeg()  }
    cbMessage

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// CbMessagePool

type CbMessagePool = ItemPool<CbMessage>

let makeCbMessagePool( startCount  : int        )
                     ( minCount    : int        )
                     ( beesConfig  : BeesConfig )
                     ( nRingFrames : int        ) : CbMessagePool =
  ItemPool.New<CbMessage> startCount minCount (fun (ip: ItemPool<CbMessage>) -> CbMessage.New ip  beesConfig  nRingFrames)

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