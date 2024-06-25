module BeesLib.AudioBuffer

open System
open System.Runtime.InteropServices
open System.Text
open System.Threading

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.Synchronizer
open BeesUtil.RangeClipper
open BeesUtil.SubscriberList
open CSharpHelpers


let dummyData     = 9999999f  // 
let dummyDateTime = _DateTime.MaxValue
let dummyTimeSpan = _TimeSpan.MaxValue


let durationOf frameRate nFrames  = _TimeSpan.FromSeconds (float nFrames / frameRate)
let nFramesOf  frameRate duration = int (round ((duration: _TimeSpan).TotalMicroseconds / 1_000_000.0 * frameRate))

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Config

type BufConfig = {
  AudioBufferDuration        : _TimeSpan
  AudioBufferGapDuration     : _TimeSpan // long enough for the largest automatically adjusted frameCount arg to callback
  SampleSize                 : int
  Simulating                 : Simulating
  InChannelCount             : int
  InFrameRate                : double  }
with

  member this.FrameSize = this.SampleSize * this.InChannelCount

let printConfig bc =
  let sb = StringBuilder()
  sb.AppendLine "BufConfig:"                                            |> ignore
  sb.AppendLine $"  AudioBufferDuration    {bc.AudioBufferDuration   }" |> ignore
  sb.AppendLine $"  AudioBufferGapDuration {bc.AudioBufferGapDuration}" |> ignore
  sb.AppendLine $"  SampleSize             {bc.SampleSize            }" |> ignore
  sb.AppendLine $"  InChannelCount         {bc.InChannelCount        }" |> ignore
  sb.AppendLine $"  InFrameRate            {bc.InFrameRate           }" |> ignore
  Console.WriteLine (sb.ToString())

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The Ring buffer comprises 0, 1, or 2 segs.

type Seg = {
  mutable Tail      : int       // ring index in frames, not samples
  mutable Head      : int       // ring index in frames, not samples
  mutable Offset    : int       // totalFrames prior to beginning of seg
  mutable StartTime : _DateTime // start time of first callback, set only once 
  NRingFrames       : int
  FrameRate         : double  }
  
  with

  static member New (head: int) (tail: int) (start: _DateTime) (nRingFrames: int) (frameRate: double) =
    assert (head >= tail)
    let seg = {
      Tail        = tail
      Head        = head
      Offset      = 0
      StartTime   = start
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
  member seg.TailTime  = seg.StartTime + seg.durationOf seg.TailInAll
  member seg.HeadTime  = seg.StartTime + seg.durationOf seg.HeadInAll

  member seg.Active    = seg.NFrames <> 0
  member seg.Reset()   = seg.Head <- 0 ; seg.Tail <- 0  // and not Active

  member seg.SetTail index =  seg.Tail <- index
                              assert (seg.Tail <= seg.Head)
                              assert (seg.Tail <= seg.NRingFrames)
  member seg.SetHead index =  seg.Head <- index
                              assert (seg.Tail <= seg.Head)
                              assert (seg.Head <= seg.NRingFrames)

  member seg.AdvanceTail nFrames =  seg.SetTail (seg.Tail + nFrames)
  member seg.AdvanceHead nFrames =  seg.SetHead (seg.Head + nFrames)
  
  override seg.ToString() = $"{seg.Offset:D3}+{seg.Tail:D2}.{seg.Head:D2}"


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// AudioBuffer

// An AudioBuffer object makes recent input data available to clients via a buffer.
// The storage capacity of the buffer is specified as a TimeSpan.
// A client Task can call the Read method with a desired DateTime and a TimeSpan, and
// the Read method responds with data from as much of the specified range as it has on hand.
// A client Task can also subscribe to events fired immediately following each callback.
// The AudioBuffer class is callable from C# or F# and is written in F#.

//–––––––––––––––––––––––––––––––––
// AudioBuffer internals – the buffer
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
// AudioBuffer

[<Struct>]
type Segs = {
  mutable Cur : Seg
  mutable Old : Seg }
with

  member this.Copy()    = { Cur = this.Cur.Copy()
                            Old = this.Old.Copy()  }
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

type InputInfo = {
  mutable Input              : IntPtr  // block of incoming data 
  mutable FrameCount         : uint32
  Ring                       : float32 array     // of samples not frames
  mutable State              : State
  mutable Segs               : Segs
  mutable BlockAdcStartTime  : _DateTime         // DateTime of first sample collection in this block
  mutable LatestBlockHead    : int               // ring index where latest input block was written by a callback
  mutable Synchronizer       : Synchronizer
  mutable NFramesTotal       : uint64            // total number of frames produced by callbacks so far
  // constants
  NRingDataFrames            : int
  NGapFrames                 : int
  NRingFrames                : int
  InChannelCount             : int
  FrameRate                  : float             // also known as sample rate, but frame rate is clearer
  FrameSize                  : int               // in bytes
  Simulating                 : Simulating        // simulating callbacks for testing and debugging 
  // these are modified once, as early as possible
  mutable StartTime          : _DateTime  }      // DateTime of first ever sample collection
with
  
  member this.Copy() = { this with Segs = this.Segs.Copy() }

  // only for debugging
  member this.markRingSpanAsDead srcFrameIndex nFrames =
    let srcFrameIndexNS = srcFrameIndex * this.InChannelCount
    let nSamples        = nFrames       * this.InChannelCount
    Array.Fill(this.Ring, dummyData, srcFrameIndexNS, nSamples)
  
  member this.PrintRing() =
      let empty    = '.'
      let dataChar = '◾'
      let getsNum i = i % 10 = 0
      let mutable ring =
        let num i = char ((i / 10 % 10).ToString())
        let sNumberedEmptyFrames i = if getsNum i then  num i else  empty
        // "0.........1.........2.........3.........4.........5.........6.........7.........8....."
        Array.init this.NRingFrames sNumberedEmptyFrames
      do // Overwrite empties with seg data.
        let showDataFor seg =
          let first = seg.Tail
          let last  = seg.Head - 1
          let getsNum i = first < i  &&  i < last  &&  getsNum i  // show only interior numbers
          let setDataFor i = if not (getsNum i) then  ring[i] <- dataChar     
          for i in first..last do  setDataFor i
        if this.Segs.Old.Active then
          assert (this.State = Chasing)
          // "0.........1.........2.........3.........4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
          showDataFor this.Segs.Old
        // "◾◾◾◾◾◾◾◾◾◾1◾◾◾◾◾◾◾◾◾2◾◾◾◾◾◾◾◾◾3◾◾◾◾.....4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
        showDataFor this.Segs.Cur
      String ring
  
  member this.Print newTail newHead msg =
    let sRing = this.PrintRing()
    let sText =
      let sSeqNum  = sprintf "%2d" this.Synchronizer.N1
      let sX       = if String.length msg > 0 then  "*" else  " "
      let sTime    = sprintf "%3d.%3d %3d.%3d"
                       this.Segs.Cur.TailTime.Millisecond
                       this.Segs.Cur.HeadTime.Millisecond
                       this.Segs.Old.TailTime.Millisecond
                       this.Segs.Old.HeadTime.Millisecond
      let sDur     = let sum = this.Segs.Cur.Duration.Milliseconds + this.Segs.Old.Duration.Milliseconds
                     $"{this.Segs.Cur.Duration.Milliseconds:d2}+{this.Segs.Old.Duration.Milliseconds:d2}={sum:d2}"
      let sCur     = this.Segs.Cur.ToString()
      let sNewTail = sprintf "%3d" newTail
      let sNew     = if newHead < 0 then  "      "  else  $"{sNewTail:S3}.{newHead:d2}"
      let sOld     = this.Segs.Old.ToString()
      let sTotal   = let sum = this.Segs.Cur.NFrames + this.Segs.Old.NFrames
                     $"{this.Segs.Cur.NFrames:d2}+{this.Segs.Old.NFrames:d2}={sum:d2}"
      let sNFrames = this.FrameCount
      let sGap     = if this.Segs.Old.Active then sprintf "%2d" (this.Segs.Old.Tail - this.Segs.Cur.Head) else  "  "
      let sState   = $"{this.State}"
      // "24    5    164.185 185.220 35+21=56  00.35 -16.40 64.85 35+21=56  29  Chasing "
      $"%s{sSeqNum}%s{sX}%4d{sNFrames}    %s{sTime} %s{sDur}  %s{sCur} %s{sNew} %s{sOld} %s{sTotal}  {sGap:s2}  %s{sState}  %s{msg}"
    Console.WriteLine $"%s{sRing}  %s{sText}"

  member this.PrintAfter msg =  this.Print 0 -1 msg

  member this.PrintTitle() =
    let s0 = String.init this.NRingFrames (fun _ -> " ")
    let s1 = " seq nFrames timeCur timeOld duration      Cur    new       Old    size   gap   state"
    let s2 = " ––– ––––––– ––––––– ––––––– ––––––––  ––––––––– –––––– ––––––––– –––––––– –––  –––––––"
           //   24    5    185.220 164.185 35+21=56  000+00.35 -16.40 000+64.85 35+21=56  29  Chasing 
    Console.WriteLine $"%s{s0}%s{s1}"
    Console.WriteLine $"%s{s0}%s{s2}"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The callback – Copy data from the audio driver into our ring.

let mutable threshold = 0 // for debugging, to get a printout from at reasonable intervals

let addSystemData input frameCount userDataPtr startTime =
  let (input : IntPtr) = input
  let handle  = GCHandle.FromIntPtr(userDataPtr)
  let info    = handle.Target :?> InputInfo
  let nFrames = int frameCount

  info.Synchronizer.EnterUnstable()

  info.BlockAdcStartTime <- startTime
  if info.StartTime = dummyDateTime then
//  Console.WriteLine "first callback"
    info.StartTime <- startTime
    info.Segs.Old.StartTime <- startTime
    info.Segs.Cur.StartTime <- startTime
  
  do
    // Modify the segs so that Segs.Cur.Head points to where the data will go in the ring.
    // Later, after the copy is done, Segs.Cur.Head will point after the new data.
    let nextValues() =
      let newHead = info.Segs.Cur.Head + nFrames
      let newTail = newHead - info.NRingDataFrames
      (newHead, newTail)
    let mutable newHead, newTail = nextValues()
    let printRing msg = if info.Simulating <> NotSimulating then  info.Print newTail newHead msg
    let trimCurTail() =
      if newTail > 0 then
        info.Segs.Cur.AdvanceTail (newTail - info.Segs.Cur.Tail)
        true
      else
        assert (info.Segs.Cur.Tail = 0)
        false
    printRing ""
    if newHead > info.NRingFrames then
      assert (info.State = Moving)
      assert (not info.Segs.Old.Active)
      info.State <- AtEnd // Briefly; quickly changes to Chasing.
      info.Segs.Exchange() ; assert (info.Segs.Cur.Head = 0  &&  info.Segs.Cur.Tail = 0)
      info.Segs.Cur.Offset <- info.Segs.Old.Offset + info.Segs.Old.Head
      let h, t = nextValues() in newHead <- h ; newTail <- t
      if info.Simulating <> NotSimulating then  info.markRingSpanAsDead info.Segs.Old.Head (info.NRingFrames - info.Segs.Old.Head) 
      info.State <- Chasing
      printRing "exchanged"
    match info.State with
    | AtStart ->
      assert (not info.Segs.Cur.Active)
      assert (not info.Segs.Old.Active)
      assert (newHead = nFrames)  // The block will fit at Ring[0]
      info.State <- AtBegin
    | AtBegin ->
      assert (not info.Segs.Old.Active)
      assert (info.Segs.Cur.Tail = 0)
      assert (info.Segs.Cur.Head + info.NGapFrames <= info.NRingFrames)  // The block will def fit after Segs.Cur.Head
      info.State <- if trimCurTail() then  Moving else  AtBegin
    | Moving ->
      assert (not info.Segs.Old.Active)
      trimCurTail() |> ignore
      info.State <- Moving
    | Chasing  ->
      assert info.Segs.Old.Active
      assert (newHead <= info.NRingFrames)  // The block will fit after Segs.Cur.Head
      assert (info.Segs.Cur.Tail = 0)
      // Segs.Old.Active.  Segs.Cur.Head is growing toward the Segs.Old.Tail, which retreats as Segs.Cur.Head grows.
      assert (info.Segs.Cur.Head < info.Segs.Old.Tail)
      trimCurTail() |> ignore
      if info.Segs.Old.NFrames <= nFrames then
        // Segs.Old is so small that it can’t survive.
        info.Segs.Old.Reset()
        info.State <- Moving
      else
        info.Segs.Old.AdvanceTail nFrames
        let halfGap = info.NGapFrames / 2  // in case nFrames has just been adjusted upwards
        assert (newHead + halfGap <= info.Segs.Old.Tail)
        info.State <- Chasing
    | AtEnd ->
      failwith "Can’t happen."

  let curHeadNS = info.Segs.Cur.Head * info.InChannelCount
  let nSamples  = nFrames           * info.InChannelCount
  UnsafeHelpers.CopyPtrToArrayAtIndex(input, info.Ring, curHeadNS, nSamples)
  info.LatestBlockHead   <- info.Segs.Cur.Head
  info.Segs.Cur.AdvanceHead nFrames
  info.NFramesTotal <- info.NFramesTotal + uint64 frameCount
//Console.Write(".")
//if info.Synchronizer.N1 % 20us = 0us then  Console.WriteLine $"%6d{info.Segs.Cur.Head} %3d{info.Segs.Cur.Head / nFrames} %10f{timeInfo.inputBufferAdcTime - info.TimeInfoBase}"
  info.Synchronizer.LeaveUnstable()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The AudioBuffer class

type RingSpan = {
  Index   : int  // in frames
  NFrames : int  }
with
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


let durationToNFrames frameRate (duration: _TimeSpan) =
  let nFramesApprox = duration.TotalSeconds * frameRate
  int (round nFramesApprox)


type RingBuffer(bufConfig: BufConfig) =

  let sim              = bufConfig.Simulating 
  let audioDuration    = cbSimAudioDuration sim (fun () -> bufConfig.AudioBufferDuration                    )
  let gapDuration      = cbSimGapDuration   sim (fun () -> bufConfig.AudioBufferGapDuration * 2.0            )
  let nRingDataFrames  = cbSimNDataFrames   sim (fun () -> durationToNFrames bufConfig.InFrameRate audioDuration )
  let nGapFrames       = cbSimNGapFrames    sim (fun () -> durationToNFrames bufConfig.InFrameRate gapDuration   )
  let nRingFrames      = nRingDataFrames + (3 * nGapFrames) / 2
  //  assert (nRingDataFrames + nRingGapFrames <= nRingFrames)
  let nRingSamples     = nRingFrames * bufConfig.InChannelCount
  let frameSize        = bufConfig.FrameSize
  let nRingBytes       = int nRingFrames * frameSize
  let startTime        = _DateTime.Now
  let segs             = { Cur = Seg.NewEmpty nRingFrames bufConfig.InFrameRate 
                           Old = Seg.NewEmpty nRingFrames bufConfig.InFrameRate  }
  
  // When unmanaged code calls managed code (e.g., a callback from unmanaged to managed),
  // the .NET CLR ensures that the garbage collector will not move referenced managed objects
  // in memory during the execution of that managed code.
  // This happens automatically and does not require manual pinning.

  let inputInfo = {
    Input              = IntPtr.Zero
    FrameCount         = 0u
    // affected by callbacks
    Ring               = Array.init<float32> nRingSamples (fun _ -> dummyData)
    State              = AtStart
    Segs               = segs
    BlockAdcStartTime  = dummyDateTime
    LatestBlockHead    = 0
    Synchronizer       = Synchronizer.New()
    NFramesTotal       = 0UL
    // constants
    NRingDataFrames    = nRingDataFrames
    NGapFrames         = nGapFrames
    NRingFrames        = nRingFrames
    InChannelCount     = bufConfig.InChannelCount
    FrameRate          = bufConfig.InFrameRate
    FrameSize          = frameSize
    Simulating         = sim
    // these are modified once, as early as possible
    StartTime = dummyDateTime  }

  let subscriberList = SubscriberList<RingBuffer>()

  do
    printfn $"{bufConfig.InFrameRate}"

  member val  InputInfo    = inputInfo
  member val  StartTime    = inputInfo.StartTime
  member val  Config       = bufConfig
  member val  RingDuration = audioDuration
  member val  GapDuration  = gapDuration
  member val  NRingBytes   = nRingBytes

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  
  /// Subscribe a post-callback handler, which will be called in managed code after each callback.
  member this.Subscribe  (subscriber: SubscriberHandler<RingBuffer>)  : Subscription<RingBuffer> =
    subscriberList.Subscribe subscriber

  /// Unsubscribe a post-callback handler.
  member this.Unsubscribe(subscription: Subscription<RingBuffer>)  : bool =
    subscriberList.Unsubscribe subscription

  
  /// Called only when Simulating, to simulate a callback.
  member this.AddSystemData(input, frameCount, startTime, userDataPtr) =
              addSystemData input  frameCount  startTime  userDataPtr

  /// <summary>
  /// Called from a <c>Task</c> (managed code) as soon as possible after the callback.
  /// </summary>
  member this.AfterCallback() =
    let info = this.CbStateSnapshot
    subscriberList.Broadcast this
    if info.Simulating <> NotSimulating then ()
    else
    if info.Segs.Cur.Head > threshold then
      threshold <- threshold + int (roundAway info.FrameRate)
  //  let sinceStart = info.TimeInfo.inputBufferAdcTime - this.PaStream.Time
  //  Console.WriteLine $"%6d{info.Segs.Cur.Head} %3d{info.Segs.Cur.Head / int info.FrameCount} %10f{sinceStart}"
  //  if inputInfo.Simulating = NotSimulating then Console.Write ","
      ()
    
  member this.durationOf nFrames = durationOf this.InputInfo.FrameRate nFrames
  member this.nFramesOf duration = nFramesOf  this.InputInfo.FrameRate duration

  member this.TailTime = this.CbStateSnapshot.Segs.TailTime
  member this.HeadTime = this.CbStateSnapshot.Segs.HeadTime

#if USE_FAKE_DATE_TIME
#else

  /// Wait until the buffer contains the given DateTime.
  member this.WaitUntil dateTime =
    while this.HeadTime < dateTime do waitUntil dateTime
  
  /// Wait until the buffer contains the given DateTime.
  member this.WaitUntil(dateTime, ctsToken: CancellationToken) =
    while this.HeadTime < dateTime do waitUntilWithToken dateTime ctsToken

#endif    

  // The `WhenStableAndEntered` function synchronizes reading by this client and writing by the callback.
  member this.CbStateSnapshot : InputInfo =
    let copyCbState() = this.InputInfo.Copy()
    let timeout = TimeSpan.FromMicroseconds 1
    match this.InputInfo.Synchronizer.WhenStableAndEntered timeout copyCbState with
    | Stable inputInfo -> inputInfo
    | TimedOut msg -> failwith $"Timed out taking a snapshot of InputInfo: {msg}" 

  member this.range() = this.InputInfo.Segs.TailTime, this.InputInfo.Segs.HeadTime
    
  // The delivered range is clipped to what is available.
  // The data is delivered in 0 1 or 2 Parts, each part comprising a Ring index and a length.
  // The data is guaranteed to be valid only for the duration of the Ring's gap duration.
  // The result is a tuple of an AudioBufferGetResult enum and the 
  // time and duration of the range of the delivered data.
  // Synchronizatrion with the callback is handled by the CbStateSnapshot property without locking.

  /// Reads buffered data.
  ///
  /// <param name="time">The starting time of the data to be read.</param>
  /// <param name="duration">The duration of the data to be read.</param>
  /// <returns>A ReadResult via which the data can be accessed.</returns>
  member this.read (time: _DateTime) (duration: _TimeSpan)  : ReadResult =
    let info = this.CbStateSnapshot
    let indexBeginArg = nFramesOf info.FrameRate (time - info.StartTime)
    let nFramesArg    = nFramesOf info.FrameRate duration
    let rangeClip, indexBeginInAll, nFramesInAll = clipRange indexBeginArg nFramesArg info.Segs.TailInAll info.Segs.NFrames
    let time     = info.StartTime + (durationOf info.FrameRate indexBeginInAll)
    let duration = durationOf info.FrameRate nFramesInAll
    let getPart (seg: Seg) =
      let _, indexBegin, nFrames = clipRange indexBeginInAll nFramesInAll seg.TailInAll seg.NFrames
      { Index = indexBegin - seg.Offset; NFrames = nFrames } // Index, indexBegin, and seg.Offset are all in frames not samples
    let parts = [|
      match rangeClip with
      | RangeClip.BeforeData | RangeClip.AfterData -> ()
      | _ ->
      if info.Segs.Old.Active then
        getPart info.Segs.Old
      getPart info.Segs.Cur  |]
    let result = {
      Ring           = info.Ring
      InChannelCount = info.InChannelCount 
      FrameRate      = info.FrameRate 
      RangeClip      = rangeClip
      NSamples       = nFramesInAll * info.InChannelCount
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
    RingBuffer.DeliverReadResult result copyPart
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
