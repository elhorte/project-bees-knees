module BeesLib.CbMessagePool

open System

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesLib.BeesConfig
open BeesUtil.AsyncConcurrentQueue
open BeesUtil.ItemPool

open BeesUtil.DebugGlobals



let tbdDateTime = _DateTime.MinValue
let tbdTimeSpan = _TimeSpan.MinValue

    
let durationOf inSampleRate nFrames  = _TimeSpan.FromSeconds (float nFrames / float inSampleRate)
let nFramesOf  inSampleRate duration = int (round ((duration: _TimeSpan).TotalMicroseconds / 1_000_000.0 * float inSampleRate))

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
  TimeBase   : _DateTime
  FrameRate  : int        } with

  static member NewByBeginEnd indexBegin indexEnd  timeBegin timeEnd  timeOrigin frameRate =
    let nFrames  = indexEnd - indexBegin
    let duration = timeEnd  - timeBegin
    let fr = {
      IndexBegin = indexBegin
      IndexEnd   = indexBegin + nFrames
      NFrames    = nFrames
      TimeBegin  = timeBegin
      TimeEnd    = timeBegin + duration
      Duration   = duration
      TimeBase   = timeOrigin
      FrameRate  = frameRate   }
    fr.Check()
    fr

  static member NewByBeginDuration indexBegin nFrames  timeBegin duration  timeOrigin frameRate =
    let fr = {
      IndexBegin = indexBegin
      IndexEnd   = indexBegin + nFrames
      NFrames    = nFrames
      TimeBegin  = timeBegin
      TimeEnd    = timeBegin + duration
      Duration   = duration
      TimeBase   = timeOrigin
      FrameRate  = frameRate   }
    fr.Check()
    fr
    
  member fr.Check() =
    let frameDuration = _TimeSpan.FromSeconds(1.0 / float fr.FrameRate)
    assert (fr.NFrames    =              fr.IndexEnd  - fr.IndexBegin)
    assert (fr.Duration   =              fr.TimeEnd   - fr.TimeBegin )
    let nFrames = int (round ( fr.Duration                 / frameDuration))
    assert (fr.NFrames    = nFrames)
    assert (fr.IndexBegin = int (round ((fr.TimeBegin - fr.TimeBase) / frameDuration)))
    assert (fr.IndexEnd   = int (round ((fr.TimeEnd   - fr.TimeBase) / frameDuration)))
    

type Seg = {
  mutable Tail     : int  // frames not samples
  mutable Head     : int  // frames not samples
  mutable TailTime : _DateTime
  mutable HeadTime : _DateTime
  mutable TimeBase : _DateTime
  NRingFrames      : int
  FrameRate        : int  }
  
  with

  static member New (head: int) (tail: int) (nRingFrames: int) (inSampleRate: int) =
    assert (head >= tail)
    let seg = {
      Tail        = tail
      Head        = head
      TailTime    = tbdDateTime
      HeadTime    = tbdDateTime
      TimeBase    = tbdDateTime
      NRingFrames = nRingFrames
      FrameRate   = inSampleRate  }
    seg

  static member NewEmpty (nRingFrames: int) (inSampleRate: int) =  Seg.New 0 0 nRingFrames inSampleRate

  member seg.ToFrameRange() =
    let fr = {
      IndexBegin = seg.Tail
      IndexEnd   = seg.Head
      NFrames    = seg.NFrames
      TimeBegin  = seg.TailTime
      TimeEnd    = seg.HeadTime 
      Duration   = seg.HeadTime - seg.TailTime
      TimeBase   = seg.TimeBase
      FrameRate  = seg.FrameRate   }
    fr.Check()
    fr

  member seg.Check() =
    let frameDuration = _TimeSpan.FromSeconds(1.0 / float seg.FrameRate)
    assert (seg.NFrames = seg.Head - seg.Tail     )
    let duration = seg.HeadTime - seg.TailTime
    if duration <> seg.Duration then printfn $"Head %x{seg.Head} Duration exp {duration} act {seg.Duration}" 
    let nFrames = int (round (seg.Duration / frameDuration))
    if nFrames <> seg.NFrames then printfn $"Head %x{seg.Head} NFrames exp {nFrames} act {seg.NFrames}"
    assert (seg.Tail = int (round ((seg.TailTime - seg.TimeBase) / frameDuration)))
    let head = int (round ((seg.HeadTime - seg.TimeBase) / frameDuration))
    if head <> seg.Head then  printfn $"Head %x{seg.Head} Head exp {head} act {seg.Head}"


  member seg.Copy() = { seg with Tail = seg.Tail }

  member seg.durationOf nFrames = durationOf seg.FrameRate nFrames
  member seg.nFramesOf duration = nFramesOf  seg.FrameRate duration
  
  member seg.NFrames  = seg.Head - seg.Tail
  member seg.Duration = seg.durationOf seg.NFrames
  member seg.Active   = seg.NFrames <> 0
  member seg.Reset()  = seg.Head <- 0 ; seg.Tail <- 0 ; assert (not seg.Active)
  
  /// identify the portion of seg that overlaps with the given time and duration
  member seg.clipToFit (time: _DateTime) (duration: _TimeSpan)  : FrameRange =
    let segTailTime      = seg.TailTime
    let segHeadTime      = seg.HeadTime
    let segDuration      = segHeadTime - segTailTime
    let segTail          = seg.Tail
    let segHead          = seg.Head
    let segLength        = seg.NFrames
    let tailTime         = time
    let headTime         = time + duration
    let tailTimeClipped  = max tailTime segTailTime
    let headTimeClipped  = min headTime segHeadTime
    let portionTime      = tailTimeClipped
    let portionDuration  = _TimeSpan.FromSeconds (headTimeClipped - tailTimeClipped).Seconds
    let portionIndex     = seg.nFramesOf (_TimeSpan.FromSeconds (tailTimeClipped - seg.TimeBase).Seconds)
    let portionNFrames   = seg.nFramesOf portionDuration
    let portionDuration2 = seg.durationOf portionNFrames
    let portionTailIndex = segTail + portionIndex
    let portionHeadIndex = portionTailIndex + portionNFrames
    let sStatus = $"""
      time             %A{time            }
      duration         %A{duration        }
      segTailTime      %A{segTailTime     }
      segHeadTime      %A{segHeadTime     }
      segDuration      %A{segDuration     }
      segTail          %A{segTail         }
      segHead          %A{segHead         }
      segLength        %A{segLength       }
      tailTime         %A{tailTime        }
      headTime         %A{headTime        }
      tailTimeClipped  %A{tailTimeClipped }
      headTimeClipped  %A{headTimeClipped }
      portionTime      %A{portionTime     }
      portionDuration  %A{portionDuration }
      portionIndex     %A{portionIndex    }
      portionNFrames   %A{portionNFrames  }
      portionDuration2 %A{portionDuration2}
      portionTailIndex %A{portionTailIndex}
      portionHeadIndex %A{portionHeadIndex}
      """
    assert (seg.Tail <= portionTailIndex) ; assert (portionHeadIndex <= seg.Head)
    FrameRange.NewByBeginDuration portionIndex portionNFrames portionTime portionDuration seg.TimeBase seg.FrameRate
    
  // member seg.clipToFit (time: _DateTime) (duration: _TimeSpan)  : FrameRange =
  //   let tr    = TimeRange.NewByBeginDuration time duration
  //   let segFr = seg.ToFrameRange()
  //   let timeBegin        = time
  //   let timeEnd          = time + duration
  //   let timeBeginClipped = max tr.TimeBegin segFr.TimeBegin
  //   let timeEndClipped   = min tr.TimeEnd   segFr.TimeEnd
  //   let trClipped = TimeRange.NewByBeginEnd timeBeginClipped timeEndClipped
  //   
  //   // let frTimeOffset     = timeBeginClipped - segFr.TimeBegin
  //   // let portionDuration  = timeEndClipped - timeBeginClipped
  //   //
  //   // let segTail          = seg.Tail
  //   // let segHead          = seg.Head
  //   // let segLength        = seg.NFrames
  //   // let portionIndex     = seg.nFramesOf frTimeOffset
  //   // let portionNFrames   = seg.nFramesOf portionDuration
  //   // let portionDuration2 = seg.durationOf portionNFrames
  //   //
  //   // let portionTailIndex = segTail + portionIndex
  //   // let portionHeadIndex = portionTailIndex + portionNFrames
  //   // let sStatus = $"""
  //   //   time             %A{time            }
  //   //   duration         %A{duration        }
  //   //   segTailTime      %A{segFr.TimeBegin     }
  //   //   segHeadTime      %A{segFr.TimeEnd     }
  //   //   segDuration      %A{segFr.Duration     }
  //   //   segTail          %A{segTail         }
  //   //   segHead          %A{segHead         }
  //   //   segLength        %A{segLength       }
  //   //   tailTime         %A{timeBegin        }
  //   //   headTime         %A{timeEnd        }
  //   //   tailTimeClipped  %A{timeBeginClipped }
  //   //   headTimeClipped  %A{timeEndClipped }
  //   //   portionTime      %A{frTimeOffset     }
  //   //   portionDuration  %A{portionDuration }
  //   //   portionIndex     %A{portionIndex    }
  //   //   portionNFrames   %A{portionNFrames  }
  //   //   portionDuration2 %A{portionDuration2}
  //   //   portionTailIndex %A{portionTailIndex}
  //   //   portionHeadIndex %A{portionHeadIndex}
  //   //   """
  //   // assert (seg.Tail <= portionTailIndex) ; assert (portionHeadIndex <= seg.Head)
  //   // { indexBegin    = portionTailIndex
  //   //   nFrames       = portionNFrames
  //   //   timeBegin     = tailTimeClipped
  //   //   duration      = portionDuration }

  member seg.SetTail index dateTime =  seg.Tail <- index ; seg.TailTime <- dateTime
                                       assert (seg.Tail     <= seg.Head)
                                       assert (seg.TailTime <= seg.HeadTime)
  member seg.SetHead index dateTime =  seg.Head <- index ; seg.HeadTime <- dateTime
                                       assert (seg.Tail     <= seg.Head)
                                       assert (seg.TailTime <= seg.HeadTime)
                                       assert (seg.Head <= seg.NRingFrames)

  member seg.AdvanceTail nFrames =  seg.SetTail (seg.Tail + nFrames) (seg.TailTime + seg.durationOf nFrames)
  member seg.AdvanceHead nFrames =  seg.SetHead (seg.Head + nFrames) (seg.HeadTime + seg.durationOf nFrames)
  
  override seg.ToString() = $"{seg.Tail:D2}.{seg.Head:D2}"



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