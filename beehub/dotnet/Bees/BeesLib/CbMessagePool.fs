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

    
let durationOf frameRate nFrames  = _TimeSpan.FromSeconds (float nFrames / float frameRate)
let nFramesOf  frameRate duration = int (round ((duration: _TimeSpan).TotalMicroseconds / 1_000_000.0 * float frameRate))

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Seg class, used by InputStream.  The ring buffer can comprise 0, 1, or 2 segs.

type TimeRange = {
  TimeBegin  : _DateTime
  TimeEnd    : _DateTime
  Duration   : _TimeSpan } with

  static member NewByBeginEnd timeBegin timeEnd  timeOrigin frameRate =
    let duration = timeEnd  - timeBegin
    let tr = {
      TimeBegin  = timeBegin
      TimeEnd    = timeBegin + duration
      Duration   = duration   }
    tr

  static member NewByBeginDuration  timeBegin duration  timeOrigin frameRate =
    let tr = {
      TimeBegin  = timeBegin
      TimeEnd    = timeBegin + duration
      Duration   = duration   }
    tr

type FrameRange = {
  IndexBegin : int
  IndexEnd   : int
  NFrames    : int
  TimeBegin  : _DateTime
  TimeEnd    : _DateTime
  Duration   : _TimeSpan
  StartTime  : _DateTime
  FrameRate  : int        } with

  static member NewByBeginDuration timeBegin duration startTime frameRate =
    let timeOffset = timeBegin - (startTime: _DateTime)
    let indexBegin = nFramesOf frameRate timeOffset
    let nFrames    = nFramesOf frameRate duration
    let fr = {
      IndexBegin = indexBegin
      IndexEnd   = indexBegin + nFrames
      NFrames    = nFrames
      TimeBegin  = timeBegin
      TimeEnd    = timeBegin + duration
      Duration   = duration
      StartTime  = startTime
      FrameRate  = frameRate   }
    fr.Check()
    fr

  static member NewByBeginEnd timeBegin timeEnd startTime frameRate =
    let duration = timeEnd - timeBegin
    FrameRange.NewByBeginDuration timeBegin duration startTime frameRate
    
  member fr.Check() =
    let frameDuration = _TimeSpan.FromSeconds(1.0 / float fr.FrameRate)
    assert (fr.NFrames    =              fr.IndexEnd  - fr.IndexBegin)
    assert (fr.Duration   =              fr.TimeEnd   - fr.TimeBegin )
    let nFrames           = int (round ( fr.Duration                  / frameDuration))
    assert (fr.NFrames    = nFrames)
    assert (fr.IndexBegin = int (round ((fr.TimeBegin - fr.StartTime) / frameDuration)))
    assert (fr.IndexEnd   = int (round ((fr.TimeEnd   - fr.StartTime) / frameDuration)))
    

type Seg = {
  mutable Tail     : int  // frames not samples
  mutable Head     : int  // frames not samples
  mutable Offset   : int  // totalFrames at beginning of seg
  mutable Start    : _DateTime
  NRingFrames      : int
  FrameRate        : int  }
  
  with

  static member New (head: int) (tail: int) (start: _DateTime) (nRingFrames: int) (frameRate: int) =
    assert (head >= tail)
    let seg = {
      Tail        = tail
      Head        = head
      Offset      = 0
      Start       = start
      NRingFrames = nRingFrames
      FrameRate   = frameRate  }
    seg

  static member NewEmpty (nRingFrames: int) (frameRate: int) =  Seg.New 0 0 tbdDateTime nRingFrames frameRate

  member seg.Check() =
    // let frameDuration = _TimeSpan.FromSeconds(1.0 / float seg.FrameRate)
    // assert (seg.NFrames = seg.Head - seg.Tail     )
    // let duration = seg.HeadTime - seg.TailTime
    // if duration <> seg.Duration then printfn $"Head %x{seg.Head} Duration exp {duration} act {seg.Duration}" 
    // let nFrames = int (round (seg.Duration / frameDuration))
    // if nFrames <> seg.NFrames then printfn $"Head %x{seg.Head} NFrames exp {nFrames} act {seg.NFrames}"
    // assert (seg.Tail = int (round ((seg.TailTime - seg.TimeBase) / frameDuration)))
    // let head = int (round ((seg.HeadTime - seg.TimeBase) / frameDuration))
    // if head <> seg.Head then  printfn $"Head %x{seg.Head} Head exp {head} act {seg.Head}"
    ()

  member seg.Copy() = { seg with Tail = seg.Tail }

  member seg.durationOf nFrames = durationOf seg.FrameRate nFrames
  member seg.nFramesOf duration = nFramesOf  seg.FrameRate duration
  
  member seg.NFrames  = seg.Head - seg.Tail
  member seg.Duration = seg.durationOf seg.NFrames
  member seg.TailTime = seg.Start + seg.durationOf (seg.Offset + seg.Tail)
  member seg.HeadTime = seg.Start + seg.durationOf (seg.Offset + seg.Head)

  member seg.Active   = seg.NFrames <> 0
  member seg.Reset()  = seg.Head <- 0 ; seg.Tail <- 0 ; assert (not seg.Active)
  
  /// identify the portion of seg that overlaps with the given time and duration
  member seg.clipToFit (time: _DateTime) (duration: _TimeSpan)  : FrameRange =
    let segTailTime      = seg.TailTime
    let segHeadTime      = seg.HeadTime
  //let segDuration      = segHeadTime - segTailTime
    let segTail          = seg.Tail
  //let segHead          = seg.Head
  //let segLength        = seg.NFrames
    let tailTime         = time
    let headTime         = time + duration
    let tailTimeClipped  = max tailTime segTailTime
    let headTimeClipped  = min headTime segHeadTime
    let portionTime      = tailTimeClipped
    let portionDuration  = _TimeSpan.FromMilliseconds (headTimeClipped - tailTimeClipped).Milliseconds
    let portionIndex     = seg.nFramesOf (_TimeSpan.FromSeconds (tailTimeClipped - seg.TailTime).Seconds)
    let portionNFrames   = seg.nFramesOf portionDuration
  //let portionDuration2 = seg.durationOf portionNFrames
    let portionTailIndex = segTail + portionIndex
  //let portionHeadIndex = portionTailIndex + portionNFrames
    // let sStatus = $"""
    //   time             %A{time            }
    //   duration         %A{duration        }
    //   segTailTime      %A{segTailTime     }
    //   segHeadTime      %A{segHeadTime     }
    //   segDuration      %A{segDuration     }
    //   segTail          %A{segTail         }
    //   segHead          %A{segHead         }
    //   segLength        %A{segLength       }
    //   tailTime         %A{tailTime        }
    //   headTime         %A{headTime        }
    //   tailTimeClipped  %A{tailTimeClipped }
    //   headTimeClipped  %A{headTimeClipped }
    //   portionTime      %A{portionTime     }
    //   portionDuration  %A{portionDuration }
    //   portionIndex     %A{portionIndex    }
    //   portionNFrames   %A{portionNFrames  }
    //   portionDuration2 %A{portionDuration2}
    //   portionTailIndex %A{portionTailIndex}
    //   portionHeadIndex %A{portionHeadIndex}
    //   """
    // assert (seg.Tail <= portionTailIndex) ; assert (portionHeadIndex <= seg.Head)
    let fr = FrameRange.NewByBeginDuration portionTime portionDuration seg.TailTime seg.FrameRate
    fr

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