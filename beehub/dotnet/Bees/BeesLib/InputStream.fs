module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.PortAudioUtils
open BeesUtil.CallbackHandoff
open BeesUtil.SeqNums
open BeesUtil.Ranges
open BeesLib.BeesConfig
open CSharpHelpers


let dummyDateTime = _DateTime.MaxValue
let dummyTimeSpan = _TimeSpan.MaxValue


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

  static member NewEmpty nRingFrames frameRate =  Seg.New 0 0 dummyDateTime nRingFrames frameRate 

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

type Worker = Buf -> int -> int

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// An InputStream object makes recent input data available to clients via a buffer.
// The storage capacity of the buffer is specified as a TimeSpan.
// A client Task can call the Read method with a desired DateTime and a TimeSpan, and
// the Read method responds with data from as much of the specified range as it has on hand.
// A client Task can also subscribe to events fired immediately following each callback.
// The InputStream class is callable from C# or F# and is written in F#.
//
// The interface to the operating system’s audio I/O is provided by the PortAudio library,
// which is written in C and made available on .NET via the PortAudioSharp library, written
// in C#.  An InputStream object is a wrapper for a PortAudioSharp Stream object.  The
// InputStream constructor sets up a callback function that is called from a system interrupt
// but runs in managed code.  The callback function is written to be quick and not to do any
// allocations.
//
// Synchronization between the interrupt-time addition of input data to the buffer and client
// managed code that reads the buffered data is handled in a lock-free manner transparent to
// the client.

//–––––––––––––––––––––––––––––––––
// InputStream internals – the buffer
//
// The buffer is a ring buffer.  Another way to describe a ring buffer is as a queue of two
// segments sharing space in a fixed array: Segs.Cur grows as data is appended to its head,
// and Segs.Old shrinks as data is trimmed from its tail.  This implementation ensures a gap
// of a given TimeSpan in the space between Segs.Cur.Head and Segs.Old.Tail.  This gap gives
// a client reading data from the buffer a grace period in which to access the data to which
// it has been given access, without worry that the data could be overwritten with new data.
// The gap thus avoids a read–write race condition without locking.
//
// The callback (at interrupt time) hands off to a background Task for further processing in managed code.

// Internal management of the ring is governed by a State variable.

type State = // |––––––––––– ring ––––––––––––|
  | AtStart  // |             gap             |
  | AtBegin  // |  Cur  |         gap         | This initial gap is of no consequence.
  | Moving   // | gapB |  Cur  |     gapA     | Cur has grown so much that Cur.Tail is being trimmed.
  | AtEnd    // |      gapB    |  Cur  | gapA | like Moving but gapA has become too small for more Cur.Head growth.
  | Chasing  // |  Cur  | gapB |  Old  | gapA | As Cur.Head grows, Old.Tail is being trimmed.

// Repeating lifecycle:  Empty –> AtBegin –> Moving –> AtEnd –> Chasing –> Moving ...
//
//      || time –>                  R               (R = repeat)         R                                    R
//      ||                          |                                    |                                    |
//      || Empty     | AtBegin      | Moving     | AtEnd | Chasing       | Moving     | AtEnd | Chasing       |
// seg0 || inactive  | Cur growing  | Cur moving         | Old shrinking | inactive           | Cur growing   |
// seg1 || inactive  | inactive     | inactive           | Cur growing   | Cur moving         | Old shrinking |
//      ||                                               X     (X = exchange Cur and Old)     X


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

type PaTime = float
let  PaTimeBad = 0.0
let  dummySample = 9999999f  // 

[<Struct>]
type Segs = {
  mutable Cur : Seg
  mutable Old : Seg }  with

  member this.Copy()    = { Cur = this.Cur.Copy()
                            Old = this.Old.Copy() }
  member this.Oldest    = if this.Old.Active then this.Old else this.Cur
  member this.TailInAll = this.Oldest.TailInAll
  member this.HeadInAll = this.Cur   .HeadInAll
  member this.NFrames   = this.HeadInAll - this.TailInAll
  member this.TailTime  = this.Oldest.TailTime
  member this.HeadTime  = this.Cur   .HeadTime
  member this.Duration  = this.HeadTime - this.TailTime

  member this.Exchange() =
    let tmp = this.Cur  in  this.Cur <- this.Old  ;  this.Old <- tmp
    assert (not this.Cur.Active)

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Callback state, persists across callbacks, updated by each callback.

type CbState = {
  // callback args
  mutable Input              : IntPtr
  mutable Output             : IntPtr
  mutable FrameCount         : uint32
  mutable TimeInfo           : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags        : PortAudioSharp.StreamCallbackFlags
  // callback result
  Ring                       : float32 array   // of samples not frames
  mutable State              : State
  mutable Segs               : Segs
  mutable BlockAdcStartTime  : _DateTime       // DateTime of first sample collection in this block
  mutable LatestBlockHead    : int             // ring index where latest input block was written by a callback
  mutable SeqNums            : SeqNums
  mutable NRingFrames        : int
  mutable NRingDataFrames    : int
  mutable NGapFrames         : int
  mutable NFramesTotal       : uint64          // total number of frames produced by callbacks so far
  // more stuff
  mutable WithEcho           : bool            // echo    is in effect
  mutable WithLogging        : bool            // logging is in effect
  // these mutables are modified once, as early as possible
  mutable CallbackHandoff    : CallbackHandoff // for handing off events for further processing in managed code
  mutable StreamAdcStartTime : _DateTime       // DateTime of first ever sample collection
  mutable PaStreamTime       : unit -> PaTime  // Function to get the current date and time, in PaTime units
  InChannelCount             : int
  FrameRate                  : float           // also known as sample rate, but frame rate is clearer
  FrameSize                  : int             // in bytes
  Logger                     : Logger          // the Logger
  Simulating                 : Simulating }    // simulating callbacks for testing and debugging 
with
  
  member cbs.Copy() = { cbs with Segs = cbs.Segs.Copy() }

  member cbs.markRingSpanAsDead srcFrameIndex nFrames =
    let srcFrameIndexNS = srcFrameIndex * cbs.InChannelCount
    let nSamples        = nFrames       * cbs.InChannelCount
    Array.Fill(cbs.Ring, dummySample, srcFrameIndexNS, nSamples)
  
  member cbs.PrintRing msg =
      let empty    = '.'
      let dataChar = '◾'
      let getsNum i = i % 10 = 0
      let mutable ring =
        let num i = char ((i / 10 % 10).ToString())
        let sNumberedEmptyFrames i = if getsNum i then  num i else  empty
        // "0.........1.........2.........3.........4.........5.........6.........7.........8....."
        Array.init cbs.NRingFrames sNumberedEmptyFrames
      do // Overwrite empties with seg data.
        let showDataFor seg =
          let first = seg.Tail
          let last  = seg.Head - 1
          let getsNum i = first < i  &&  i < last  &&  getsNum i  // show only interior numbers
          let setDataFor i = if not (getsNum i) then  ring[i] <- dataChar     
          for i in first..last do  setDataFor i
        if cbs.Segs.Old.Active then
          assert (cbs.State = Chasing)
          // "0.........1.........2.........3.........4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
          showDataFor cbs.Segs.Old
        // "◾◾◾◾◾◾◾◾◾◾1◾◾◾◾◾◾◾◾◾2◾◾◾◾◾◾◾◾◾3◾◾◾◾.....4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
        showDataFor cbs.Segs.Cur
      String ring
  
  member cbs.Print newTail newHead msg =
    let sRing = cbs.PrintRing msg
    let sText =
      let sSeqNum  = sprintf "%2d" cbs.SeqNums.N1
      let sX       = if String.length msg > 0 then  "*" else  " "
      let sTime    = sprintf "%3d.%3d %3d.%3d"
                       cbs.Segs.Cur.TailTime.Millisecond
                       cbs.Segs.Cur.HeadTime.Millisecond
                       cbs.Segs.Old.TailTime.Millisecond
                       cbs.Segs.Old.HeadTime.Millisecond
      let sDur     = let sum = cbs.Segs.Cur.Duration.Milliseconds + cbs.Segs.Old.Duration.Milliseconds
                     $"{cbs.Segs.Cur.Duration.Milliseconds:d2}+{cbs.Segs.Old.Duration.Milliseconds:d2}={sum:d2}"
      let sCur     = cbs.Segs.Cur.ToString()
      let sNewTail = sprintf "%3d" newTail
      let sNew     = if newHead < 0 then  "      "  else  $"{sNewTail:S3}.{newHead:d2}"
      let sOld     = cbs.Segs.Old.ToString()
      let sTotal   = let sum = cbs.Segs.Cur.NFrames + cbs.Segs.Old.NFrames
                     $"{cbs.Segs.Cur.NFrames:d2}+{cbs.Segs.Old.NFrames:d2}={sum:d2}"
      let sNFrames = cbs.FrameCount
      let sGap     = if cbs.Segs.Old.Active then sprintf "%2d" (cbs.Segs.Old.Tail - cbs.Segs.Cur.Head) else  "  "
      let sState   = $"{cbs.State}"
      // "24    5    164.185 185.220 35+21=56  00.35 -16.40 64.85 35+21=56  29  Chasing "
      $"%s{sSeqNum}%s{sX}%4d{sNFrames}    %s{sTime} %s{sDur}  %s{sCur} %s{sNew} %s{sOld} %s{sTotal}  {sGap:s2}  %s{sState}  %s{msg}"
    Console.WriteLine $"%s{sRing}  %s{sText}"

  member cbs.PrintAfter msg =  cbs.Print 0 -1 msg

  member cbs.PrintTitle() =
    let s0 = String.init cbs.NRingFrames (fun _ -> " ")
    let s1 = " seq nFrames timeCur timeOld duration      Cur    new       Old    size   gap   state"
    let s2 = " ––– ––––––– ––––––– ––––––– ––––––––  ––––––––– –––––– ––––––––– –––––––– –––  –––––––"
           //   24    5    185.220 164.185 35+21=56  000+00.35 -16.40 000+64.85 35+21=56  29  Chasing 
    Console.WriteLine $"%s{s0}%s{s1}"
    Console.WriteLine $"%s{s0}%s{s2}"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The callback – Copy data from the audio driver into our ring.

let mutable threshold = 0 // for debugging, to get a printout from at reasonable intervals

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle   = GCHandle.FromIntPtr(userDataPtr)
  let cbs      = handle.Target :?> CbState
  let nFrames = int frameCount
  cbs.SeqNums.EnterUnstable()

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  let inputBuferAdcDateTime =
    let f = cbs.PaStreamTime()
    let secondsSinceAdcTime = f - timeInfo.inputBufferAdcTime
    let timeTilNow = _TimeSpan.FromSeconds secondsSinceAdcTime
    _DateTime.Now - timeTilNow
  cbs.BlockAdcStartTime <- inputBuferAdcDateTime
  if cbs.StreamAdcStartTime = dummyDateTime then
//  Console.WriteLine "first callback"
    cbs.StreamAdcStartTime <- inputBuferAdcDateTime
    cbs.Segs.Old.Start     <- inputBuferAdcDateTime
    cbs.Segs.Cur.Start     <- inputBuferAdcDateTime
  
  do
    // Modify the segs so that Segs.Cur.Head points to where the data will go in the ring.
    // Later, after the copy is done, Segs.Cur.Head will point after the new data.
    let nextValues() =
      let newHead = cbs.Segs.Cur.Head + nFrames
      let newTail = newHead - cbs.NRingDataFrames
      (newHead, newTail)
    let mutable newHead, newTail = nextValues()
    let printRing msg = if cbs.Simulating <> NotSimulating then  cbs.Print newTail newHead msg
    let trimCurTail() =
      if newTail > 0 then
        cbs.Segs.Cur.AdvanceTail (newTail - cbs.Segs.Cur.Tail)
        true
      else
        assert (cbs.Segs.Cur.Tail = 0)
        false
    printRing ""
    if newHead > cbs.NRingFrames then
      assert (cbs.State = Moving)
      assert (not cbs.Segs.Old.Active)
      cbs.State <- AtEnd // Briefly; quickly changes to Chasing.
      cbs.Segs.Exchange() ; assert (cbs.Segs.Cur.Head = 0  &&  cbs.Segs.Cur.Tail = 0)
      cbs.Segs.Cur.Offset <- cbs.Segs.Old.Offset + cbs.Segs.Old.Head
      let h, t = nextValues() in newHead <- h ; newTail <- t
      if cbs.Simulating <> NotSimulating then  cbs.markRingSpanAsDead cbs.Segs.Old.Head (cbs.NRingFrames - cbs.Segs.Old.Head) 
      cbs.State <- Chasing
      printRing "exchanged"
    match cbs.State with
    | AtStart ->
      assert (not cbs.Segs.Cur.Active)
      assert (not cbs.Segs.Old.Active)
      assert (newHead = nFrames)  // The block will fit at Ring[0]
      cbs.State <- AtBegin
    | AtBegin ->
      assert (not cbs.Segs.Old.Active)
      assert (cbs.Segs.Cur.Tail = 0)
      assert (cbs.Segs.Cur.Head + cbs.NGapFrames <= cbs.NRingFrames)  // The block will def fit after Segs.Cur.Head
      cbs.State <- if trimCurTail() then  Moving else  AtBegin
    | Moving ->
      assert (not cbs.Segs.Old.Active)
      trimCurTail() |> ignore
      cbs.State <- Moving
    | Chasing  ->
      assert cbs.Segs.Old.Active
      assert (newHead <= cbs.NRingFrames)  // The block will fit after Segs.Cur.Head
      assert (cbs.Segs.Cur.Tail = 0)
      // Segs.Old.Active.  Segs.Cur.Head is growing toward the Segs.Old.Tail, which retreats as Segs.Cur.Head grows.
      assert (cbs.Segs.Cur.Head < cbs.Segs.Old.Tail)
      trimCurTail() |> ignore
      if cbs.Segs.Old.NFrames <= nFrames then
        // Segs.Old is so small that it can’t survive.
        cbs.Segs.Old.Reset()
        cbs.State <- Moving
      else
        cbs.Segs.Old.AdvanceTail nFrames
        let halfGap = cbs.NGapFrames / 2  // in case nFrames has just been adjusted upwards
        assert (newHead + halfGap <= cbs.Segs.Old.Tail)
        cbs.State <- Chasing
    | AtEnd ->
      failwith "Can’t happen."

  let curHeadNS = cbs.Segs.Cur.Head * cbs.InChannelCount
  let nSamples  = nFrames           * cbs.InChannelCount
  UnsafeHelpers.CopyPtrToArrayAtIndex(input, cbs.Ring, curHeadNS, nSamples)
  cbs.LatestBlockHead   <- cbs.Segs.Cur.Head
  cbs.Segs.Cur.AdvanceHead nFrames
  cbs.NFramesTotal <- cbs.NFramesTotal + uint64 frameCount
//Console.Write(".")
//if cbs.SeqNums.N1 % 20us = 0us then  Console.WriteLine $"%6d{cbs.Segs.Cur.Head} %3d{cbs.Segs.Cur.Head / nFrames} %10f{timeInfo.inputBufferAdcTime - cbs.TimeInfoBase}"
  cbs.SeqNums.LeaveUnstable()

//cbs.Logger.Add cbs.SeqNum2 cbs.TimeStamp "cb bufs=" ""
  cbs.CallbackHandoff.HandOff()
  PortAudioSharp.StreamCallbackResult.Continue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The InputStream class

type RingSpan = {
  Index   : int  // in frames
  NFrames : int  } with
  override t.ToString() = $"[ I %d{t.Index} N %d{t.NFrames} ]"

type Parts = RingSpan array

let partsToString (parts: Parts) =
    match parts.Length with
    | 0 -> "(no parts)"
    | 1 -> $"%A{parts[0].ToString()}" 
    | 2 -> $"%A{parts[0].ToString()} %A{parts[1].ToString()}" 
    | _ -> "(bad parts)"


type ReadResult = {
  Ring           : float32[]  // source array
  InChannelCount : int
  FrameRate      : float
  RangeClip      : RangeClip  // whether or how the requested range had to be clipped
  NSamples       : int        // result array length
  Time           : _DateTime  // time     of overall result
  Duration       : _TimeSpan  // duration of overall result
  Parts          : Parts     } // 0 1 or 2 portions of the Ring
with

  override t.ToString() = $"%d{t.Parts.Length} %A{t.RangeClip} %d{t.NSamples} L %s{partsToString t.Parts}"

// initPortAudio() must be called before this constructor.
type InputStream(beesConfig       : BeesConfig          ,
                 inputParameters  : StreamParameters    ,
                 outputParameters : StreamParameters    ,
                 withEcho         : bool                ,
                 withLogging      : bool                ,
                 sim              : Simulating ) =

  let audioDuration   = cbSimAudioDuration sim (fun () -> beesConfig.InputStreamAudioDuration                     )
  let gapDuration     = cbSimGapDuration   sim (fun () -> beesConfig.InputStreamRingGapDuration * 2.0             )
  let nRingDataFrames = cbSimNDataFrames   sim (fun () -> durationToNFrames beesConfig.InFrameRate audioDuration )
  let nGapFrames      = cbSimNGapFrames    sim (fun () -> durationToNFrames beesConfig.InFrameRate gapDuration   )
  let nRingFrames     = nRingDataFrames + (3 * nGapFrames) / 2
  let nRingSamples    = nRingFrames * beesConfig.InChannelCount
  let frameSize       = beesConfig.FrameSize
  let nRingBytes      = int nRingFrames * frameSize
  let startTime       = _DateTime.Now
  let segs            = { Cur = Seg.NewEmpty nRingFrames beesConfig.InFrameRate 
                          Old = Seg.NewEmpty nRingFrames beesConfig.InFrameRate  }
  
  // When unmanaged code calls managed code (e.g., a callback from unmanaged to managed),
  // the .NET CLR ensures that the garbage collector will not move referenced managed objects
  // in memory during the execution of that managed code.
  // This happens automatically and does not require manual pinning.

  let cbState = {
    // callback args
    Input              = IntPtr.Zero
    Output             = IntPtr.Zero
    FrameCount         = 0u
    TimeInfo           = PortAudioSharp.StreamCallbackTimeInfo()
    StatusFlags        = PortAudioSharp.StreamCallbackFlags()
    // callback result
    Ring               = Array.init<float32> nRingSamples (fun _ -> dummySample)
    State              = AtStart
    Segs               = segs
    BlockAdcStartTime  = dummyDateTime
    LatestBlockHead    = 0
    SeqNums            = SeqNums.New()
    NRingFrames        = nRingFrames
    NRingDataFrames    = nRingDataFrames
    NGapFrames         = nGapFrames
    // more stuff
    NFramesTotal       = 0UL
    WithEcho           = withEcho
    WithLogging        = withLogging
    CallbackHandoff    = dummyInstance<CallbackHandoff>()  // tbd
    StreamAdcStartTime = dummyDateTime
    PaStreamTime       = fun () -> PaTimeBad
    InChannelCount     = beesConfig.InChannelCount
    FrameRate          = beesConfig.InFrameRate
    FrameSize          = frameSize
    Logger             = Logger(8000, startTime)
    Simulating         = sim  }

  let paStream =
    if cbState.Simulating <> NotSimulating then
      cbState.PaStreamTime <- fun () -> cbState.TimeInfo.inputBufferAdcTime // seconds
      dummyInstance<PortAudioSharp.Stream>()
    else
      let streamCallback = PortAudioSharp.Stream.Callback(
        // The intermediate lambda here is required to avoid a compiler error.
        fun        input output frameCount  timeInfo statusFlags userDataPtr ->
          callback input output frameCount &timeInfo statusFlags userDataPtr )
      let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                            outParams       = Nullable<_>(outputParameters)        ,
                                                                            sampleRate      = beesConfig.InFrameRate               ,
                                                                            framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                            streamFlags     = StreamFlags.ClipOff                  ,
                                                                            callback        = streamCallback                       ,
                                                                            userData        = cbState                              ) )
      cbState.PaStreamTime <- fun () -> paStream.Time
      paStream
  do
    printfn $"{beesConfig.InFrameRate}"

  member  this.echoEnabled   () = Volatile.Read &cbState.WithEcho
  member  this.loggingEnabled() = Volatile.Read &cbState.WithEcho

  member val  PaStream          = paStream
  member val  CbState           = cbState
  member val  CbStateLatest     = cbState                      with get, set
  member val  StartTime         = cbState.StreamAdcStartTime
  member val  BeesConfig        = beesConfig
  member val  RingDuration      = audioDuration
  member val  GapDuration       = gapDuration
  member val  NRingBytes        = nRingBytes

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  /// <summary>
  /// Starts the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow (fun() -> this.PaStream.Start() )
    printfn $"InputStream size:    {this.NRingBytes / 1_000_000} MB for {this.RingDuration}"
    printfn $"InputStream nFrames: {this.CbState.NRingFrames}"

  /// <summary>
  /// Stops the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Stop() =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Stop () )

  /// Called only when Simulating, to simulate a callback.
  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  /// <summary>
  /// Called from a <c>Task</c> (managed code) as soon as possible after the callback.
  /// </summary>
  member this.AfterCallback() =
    let cbs = this.CbStateSnapshot
    if cbs.Simulating <> NotSimulating then ()
    else
    if cbs.Segs.Cur.Head > threshold then
      threshold <- threshold + int (round (cbs.FrameRate))
  //  let sinceStart = cbs.TimeInfo.inputBufferAdcTime - this.PaStream.Time
  //  Console.WriteLine $"%6d{cbs.Segs.Cur.Head} %3d{cbs.Segs.Cur.Head / int cbs.FrameCount} %10f{sinceStart}"
  //  if cbState.Simulating = NotSimulating then Console.Write ","
      ()

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    
  member this.durationOf nFrames = durationOf this.CbState.FrameRate nFrames
  member this.nFramesOf duration = nFramesOf  this.CbState.FrameRate duration

  member this.TailTime = this.CbStateSnapshot.Segs.TailTime
  member this.HeadTime = this.CbStateSnapshot.Segs.HeadTime
  
  /// Wait until the buffer contains the given DateTime.
  member this.WaitUntil dateTime =
    let rec loop() =
      if this.HeadTime < dateTime then
        waitUntil dateTime
        loop()
    loop()
    
  // The `WhenStableAndEntered` function synchronizes reading by this client and writing by the callback.
  member this.CbStateSnapshot : CbState =
    let copyCbState() = this.CbState.Copy()
    let timeout = TimeSpan.FromMicroseconds 1
    match this.CbState.SeqNums.WhenStableAndEntered timeout copyCbState with
    | Stable cbState -> cbState
    | TimedOut s -> failwith "Timed out taking a snapshot of CbState" 

  member this.range() = this.CbState.Segs.TailTime, this.CbState.Segs.HeadTime
    
  // The delivered range is clipped to what is available.
  // The data is delivered in 0 1 or 2 Parts, each part comprising a Ring index and a length.
  // The data is guaranteed to be valid only for the duration of the Ring's gap duration.
  // The result is a tuple of an InputStreamGetResult enum and the 
  // time and duration of the range of the delivered data.
  // Synchronizatrion with the callback is handled by the CbStateSnapshot property without locking.

  /// Reads buffered data.
  ///
  /// <param name="time">The starting time of the data to be read.</param>
  /// <param name="duration">The duration of the data to be read.</param>
  /// <returns>A ReadResult via which the data can be accessed.</returns>
  member this.read (time: _DateTime) (duration: _TimeSpan)  : ReadResult =
    let cbs = this.CbStateSnapshot
    let indexBeginArg = nFramesOf cbs.FrameRate (time - cbs.StreamAdcStartTime)
    let nFramesArg    = nFramesOf cbs.FrameRate duration
    let rangeClip, indexBeginInAll, nFramesInAll = clipRange indexBeginArg nFramesArg cbs.Segs.TailInAll cbs.Segs.NFrames
    let time     = cbs.StreamAdcStartTime + (durationOf cbs.FrameRate indexBeginInAll)
    let duration = durationOf cbs.FrameRate nFramesInAll
    let getPart (seg: Seg) =
      let _, indexBegin, nFrames = clipRange indexBeginInAll nFramesInAll seg.TailInAll seg.NFrames
      { Index = indexBegin - seg.Offset; NFrames = nFrames } // Index, indexBegin, and seg.Offset are all in frames not samples
    let parts = [|
      match rangeClip with
      | RangeClip.BeforeData | RangeClip.AfterData -> ()
      | _ ->
      if cbs.Segs.Old.Active then
        getPart cbs.Segs.Old
      getPart cbs.Segs.Cur  |]
    let result = {
      Ring           = cbs.Ring
      InChannelCount = cbs.InChannelCount 
      FrameRate      = cbs.FrameRate 
      RangeClip      = rangeClip
      NSamples       = nFramesInAll * cbs.InChannelCount
      Time           = time
      Duration       = duration
      Parts          = parts  }
    result

  member this.Read (from: _DateTime, duration: _TimeSpan) =
    this.read from duration

  static member CopyFromReadResult result =
    let deadData = 12345678.0f
    let resultArray = Array.create<float32> result.NSamples deadData
    let copyPart (indexNS: int) (destIndexNS: int) (nSamples: int) =
      if indexNS + nSamples > Array.length result.Ring then  printfn "asking for more than is there"
      Array.Copy(result.Ring, indexNS, resultArray, destIndexNS, nSamples)
    InputStream.DeliverReadResult result copyPart
    resultArray

  static member DeliverReadResult (result: ReadResult) deliver =
    let copyResultPart (destIndexNS, nParts) { Index = indexNF; NFrames = nFrames } =
      let indexNS  = indexNF * result.InChannelCount
      let nSamples = nFrames * result.InChannelCount
      deliver indexNS destIndexNS nSamples
      destIndexNS + nSamples, nParts + 1
    let foldInitialState = 0, 0 // destIndexNS, nParts
    result.Parts
    |> Array.fold copyResultPart foldInitialState
    |> if true then ignore
       else
       // The following is only to reinforce what happened, for those new to functional programming.
       (fun (destIndexNS, nParts) ->
         assert (destIndexNS = result.NSamples)    // We copied the total number of samples
         assert (nParts = result.Parts.Length) ) // in the given number of parts
    
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  interface IDisposable with
    member this.Dispose() =
      Console.WriteLine("Disposing inputStream")
  //  this.PaStream.Dispose()  // I think this crashes because PaStream doesn’t like being closed twice.
