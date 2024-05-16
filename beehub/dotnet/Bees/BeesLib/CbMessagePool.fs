module BeesLib.CbMessagePool

open System

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesLib.BeesConfig
open BeesUtil.AsyncConcurrentQueue
open BeesUtil.ItemPool

open BeesUtil.DebugGlobals



let tbdDateTime = _DateTime.BadValue
let tbdTimeSpan = _TimeSpan.BadValue

    
let durationOf frameRate nFrames  = _TimeSpan.FromSeconds (float nFrames / frameRate)
let nFramesOf  frameRate duration = int (round ((duration: _TimeSpan).TotalMicroseconds / 1_000_000.0 * frameRate))

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Seg class, used by InputStream.  The ring buffer can comprise 0, 1, or 2 segs.

type Seg = {
  mutable Tail   : int  // frames not samples
  mutable Head   : int  // frames not samples
  mutable Offset : int  // totalFrames at beginning of seg
  mutable Start  : _DateTime
  NRingFrames    : int
  FrameRate      : double  }
  
  with

  static member New (head: int) (tail: int) (start: _DateTime) (nRingFrames: int) (frameRate: double) =
    assert (head >= tail)
    let seg = {
      Tail        = tail
      Head        = head
      Offset      = 0
      Start       = start        // set only once, at first callback
      NRingFrames = nRingFrames
      FrameRate   = frameRate  }
    seg

  static member NewEmpty nRingFrames frameRate =  Seg.New 0 0 tbdDateTime nRingFrames frameRate 

  member seg.Copy() = { seg with Tail = seg.Tail }

  member seg.durationOf nFrames = durationOf seg.FrameRate nFrames
  member seg.nFramesOf duration = nFramesOf  seg.FrameRate duration
  
  member seg.NFrames   = seg.Head - seg.Tail
  member seg.Duration  = seg.durationOf seg.NFrames
  member seg.TailInAll = seg.Offset + seg.Tail
  member seg.HeadInAll = seg.Offset + seg.Head
  member seg.TailTime  = seg.Start  + seg.durationOf seg.TailInAll
  member seg.HeadTime  = seg.Start  + seg.durationOf seg.HeadInAll

  member seg.Active    = seg.NFrames <> 0
  member seg.Reset()   = seg.Head <- 0 ; seg.Tail <- 0 ; assert (not seg.Active)

  member seg.SetTail index =  seg.Tail <- index
                              assert (seg.Tail <= seg.Head)
                              assert (seg.Tail <= seg.NRingFrames)
  member seg.SetHead index =  seg.Head <- index
                              assert (seg.Tail <= seg.Head)
                              assert (seg.Head <= seg.NRingFrames)

  member seg.AdvanceTail nFrames =  seg.SetTail (seg.Tail + nFrames)
  member seg.AdvanceHead nFrames =  seg.SetHead (seg.Head + nFrames)
  
  override seg.ToString() = $"{seg.Offset:D3}+{seg.Tail:D2}.{seg.Head:D2}"



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
  mutable TimeStamp            : _DateTime              
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
    let newSeg()          = Seg.NewEmpty nRingFrames beesConfig.InFrameRate
    
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
      TimeStamp            = _DateTime.MinValue 
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
  //   let startTime  = _DateTime.Now
  //   let logger     = Logger(8000, startTime)
  //   let pool = CbMessagePool(1, startCount, minCount, stream, CbMessageQueue(), logger)
  //   pool.Test()