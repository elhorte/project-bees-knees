module BeesLib.AudioBuffer

open System
open System.Text
open System.Threading

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.Synchronizer
open BeesUtil.RangeClipper
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
  InChannelCount             : int
  InFrameRate                : double
  Simulating                 : Simulating  }
with

  member this.FrameSize = this.SampleSize * this.InChannelCount

let printBufConfig bc =
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
// the Read method responds with data having as much as possible of the specified range.
// The AudioBuffer class is callable from C# or F# and is written in F#.

//–––––––––––––––––––––––––––––––––
// AudioBuffer internals – the buffer
//
// The buffer is a ring buffer.  Another way to describe a ring buffer is as a queue of two
// segments sharing space in a fixed array: segs.Cur grows as data is appended to its head,
// and segs.Old shrinks as data is trimmed from its tail.  This implementation ensures a gap
// of a given TimeSpan in the space between segs.Cur.Head and segs.Old.Tail.  This gap gives
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
// Segs – current and old

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


type AudioBuffer(bufConfig: BufConfig) =

  let simulating       = bufConfig.Simulating 
  let inChannelCount   = bufConfig.InChannelCount
  let frameRate        = bufConfig.InFrameRate
  let maxDuration      = cbSimAudioDuration simulating (fun () -> bufConfig.AudioBufferDuration                    )
  let gapDuration      = cbSimGapDuration   simulating (fun () -> bufConfig.AudioBufferGapDuration * 2.0            )
  let nRingDataFrames  = cbSimNDataFrames   simulating (fun () -> durationToNFrames bufConfig.InFrameRate maxDuration )
  let nGapFrames       = cbSimNGapFrames    simulating (fun () -> durationToNFrames bufConfig.InFrameRate gapDuration   )
  let nRingFrames      = nRingDataFrames + (3 * nGapFrames) / 2
  //  assert (nRingDataFrames + nRingGapFrames <= nRingFrames)
  let nRingSamples     = nRingFrames * bufConfig.InChannelCount
  let frameSize        = bufConfig.FrameSize
  let nRingBytes       = int nRingFrames * frameSize

  let ring            = Array.init<float32> nRingSamples (fun _ -> dummyData)

  // modified by most recent data addition
  let mutable latestInput       = IntPtr.Zero
  let mutable latestFrameCount  = 0u
  let mutable latestStartTime   = dummyDateTime
  let mutable segs              = { Cur = Seg.NewEmpty nRingFrames bufConfig.InFrameRate 
                                    Old = Seg.NewEmpty nRingFrames bufConfig.InFrameRate  }
  let mutable state             = AtStart
  let mutable latestBlockIndex  = 0
  let mutable synchronizer      = Synchronizer.New()
  let mutable nFramesTotal      = 0UL
  // modified once upon first addition of data
  let mutable startTimeOfBuffer = dummyDateTime
  
  let printRing() =
    let empty    = '.'
    let dataChar = '◾'
    let getsNum i = i % 10 = 0
    let mutable ring =
      let num i = char ((i / 10 % 10).ToString())
      let sNumberedEmptyFrames i = if getsNum i then  num i else  empty
      // "0.........1.........2.........3.........4.........5.........6.........7.........8....."
      Array.init nRingFrames sNumberedEmptyFrames
    do // Overwrite empties with seg data.
      let showDataFor seg =
        let first = seg.Tail
        let last  = seg.Head - 1
        let getsNum i = first < i  &&  i < last  &&  getsNum i  // show only interior numbers
        let setDataFor i = if not (getsNum i) then  ring[i] <- dataChar     
        for i in first..last do  setDataFor i
      if segs.Old.Active then
        assert (state = Chasing)
        // "0.........1.........2.........3.........4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
        showDataFor segs.Old
      // "◾◾◾◾◾◾◾◾◾◾1◾◾◾◾◾◾◾◾◾2◾◾◾◾◾◾◾◾◾3◾◾◾◾.....4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
      showDataFor segs.Cur
    String ring
  
  let print newTail newHead msg =
    let sRing = printRing()
    let sText =
      let sSeqNum  = sprintf "%2d" synchronizer.N1
      let sX       = if String.length msg > 0 then  "*" else  " "
      let sTime    = sprintf "%3d.%3d %3d.%3d"
                       segs.Cur.TailTime.Millisecond
                       segs.Cur.HeadTime.Millisecond
                       segs.Old.TailTime.Millisecond
                       segs.Old.HeadTime.Millisecond
      let sDur     = let sum = segs.Cur.Duration.Milliseconds + segs.Old.Duration.Milliseconds
                     $"{segs.Cur.Duration.Milliseconds:d2}+{segs.Old.Duration.Milliseconds:d2}={sum:d2}"
      let sCur     = segs.Cur.ToString()
      let sNewTail = sprintf "%3d" newTail
      let sNew     = if newHead < 0 then  "      "  else  $"{sNewTail:S3}.{newHead:d2}"
      let sOld     = segs.Old.ToString()
      let sTotal   = let sum = segs.Cur.NFrames + segs.Old.NFrames
                     $"{segs.Cur.NFrames:d2}+{segs.Old.NFrames:d2}={sum:d2}"
      let sNFrames = latestFrameCount
      let sGap     = if segs.Old.Active then sprintf "%2d" (segs.Old.Tail - segs.Cur.Head) else  "  "
      let sState   = $"{state}"
      // "24    5    164.185 185.220 35+21=56  00.35 -16.40 64.85 35+21=56  29  Chasing "
      $"%s{sSeqNum}%s{sX}%4d{sNFrames}    %s{sTime} %s{sDur}  %s{sCur} %s{sNew} %s{sOld} %s{sTotal}  {sGap:s2}  %s{sState}  %s{msg}"
    Console.WriteLine $"%s{sRing}  %s{sText}"

  let printAfter msg =  print 0 -1 msg

  let printTitle() =
    let s0 = String.init nRingFrames (fun _ -> " ")
    let s1 = " seq nFrames timeCur timeOld duration      Cur    new       Old    size   gap   state"
    let s2 = " ––– ––––––– ––––––– ––––––– ––––––––  ––––––––– –––––– ––––––––– –––––––– –––  –––––––"
           //   24    5    185.220 164.185 35+21=56  000+00.35 -16.40 000+64.85 35+21=56  29  Chasing 
    Console.WriteLine $"%s{s0}%s{s1}"
    Console.WriteLine $"%s{s0}%s{s2}"

  //––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // The callback – Copy data from the audio driver into our ring.

  // only for debugging
  let markRingSpanAsDead srcFrameIndex nFrames =
    let srcFrameIndexNS = srcFrameIndex * inChannelCount
    let nSamples        = nFrames       * inChannelCount
    Array.Fill(ring, dummyData, srcFrameIndexNS, nSamples)

  let mutable threshold = 0 // for debugging, to get a printout from at reasonable intervals

  let addSystemData input frameCount (startTime: unit -> _DateTime) =
    let (input : IntPtr) = input
    let nFrames = int frameCount
    latestInput      <- input
    latestFrameCount <- frameCount

    synchronizer.EnterUnstable()

    latestStartTime <- startTime()
    if startTimeOfBuffer = dummyDateTime then
  //  Console.WriteLine "first callback"
      startTimeOfBuffer      <- latestStartTime
      segs.Old.StartTime <- latestStartTime
      segs.Cur.StartTime <- latestStartTime
    
    do
      // Modify the segs so that segs.Cur.Head points to where the data will go in the ring.
      // Later, after the copy is done, segs.Cur.Head will point after the new data.
      let nextValues() =
        let newHead = segs.Cur.Head + nFrames
        let newTail = newHead - nRingDataFrames
        (newHead, newTail)
      let mutable newHead, newTail = nextValues()
      let printRing msg = if simulating <> NotSimulating then  print newTail newHead msg
      let trimCurTail() =
        if newTail > 0 then
          segs.Cur.AdvanceTail (newTail - segs.Cur.Tail)
          true
        else
          assert (segs.Cur.Tail = 0)
          false
      printRing ""
      if newHead > nRingFrames then
        assert (state = Moving)
        assert (not segs.Old.Active)
        state <- AtEnd // Briefly; quickly changes to Chasing.
        segs.Exchange() ; assert (segs.Cur.Head = 0  &&  segs.Cur.Tail = 0)
        segs.Cur.Offset <- segs.Old.Offset + segs.Old.Head
        let h, t = nextValues() in newHead <- h ; newTail <- t
        if simulating <> NotSimulating then  markRingSpanAsDead segs.Old.Head (nRingFrames - segs.Old.Head) 
        state <- Chasing
        printRing "exchanged"
      match state with
      | AtStart ->
        assert (not segs.Cur.Active)
        assert (not segs.Old.Active)
        assert (newHead = nFrames)  // The block will fit at Ring[0]
        state <- AtBegin
      | AtBegin ->
        assert (not segs.Old.Active)
        assert (segs.Cur.Tail = 0)
        assert (segs.Cur.Head + nGapFrames <= nRingFrames)  // The block will def fit after segs.Cur.Head
        state <- if trimCurTail() then  Moving else  AtBegin
      | Moving ->
        assert (not segs.Old.Active)
        trimCurTail() |> ignore
        state <- Moving
      | Chasing  ->
        assert segs.Old.Active
        assert (newHead <= nRingFrames)  // The block will fit after segs.Cur.Head
        assert (segs.Cur.Tail = 0)
        // segs.Old.Active.  segs.Cur.Head is growing toward the segs.Old.Tail, which retreats as segs.Cur.Head grows.
        assert (segs.Cur.Head < segs.Old.Tail)
        trimCurTail() |> ignore
        if segs.Old.NFrames <= nFrames then
          // segs.Old is so small that it can’t survive.
          segs.Old.Reset()
          state <- Moving
        else
          segs.Old.AdvanceTail nFrames
          let halfGap = nGapFrames / 2  // in case nFrames has just been adjusted upwards
          assert (newHead + halfGap <= segs.Old.Tail)
          state <- Chasing
      | AtEnd ->
        failwith "Can’t happen."

    let curHeadNS = segs.Cur.Head * inChannelCount
    let nSamples  = nFrames       * inChannelCount
    UnsafeHelpers.CopyPtrToArrayAtIndex(input, ring, curHeadNS, nSamples)
    latestBlockIndex <- segs.Cur.Head
    segs.Cur.AdvanceHead nFrames
    nFramesTotal <- nFramesTotal + uint64 frameCount
  //Console.Write(".")
  //if Synchronizer.N1 % 20us = 0us then  Console.WriteLine $"%6d{segs.Cur.Head} %3d{segs.Cur.Head / nFrames} %10f{timeInfo.inputBufferAdcTime - TimeInfoBase}"
    synchronizer.LeaveUnstable()

  do
    printfn $"{bufConfig.InFrameRate}"
  
  member private this.SetSegs segsArg = segs <- segsArg

  member val  Config      = bufConfig
  member val  MaxDuration = maxDuration
  member val  GapDuration = gapDuration
  member val  NRingBytes  = nRingBytes

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  
  member this.AddSystemData(input, frameCount: uint32, startTimeFunc: unit -> _DateTime) =
              addSystemData input  frameCount          startTimeFunc
    
  member this.durationOf nFrames = durationOf frameRate nFrames
  member this.nFramesOf duration = nFramesOf  frameRate duration

  member this.TailTime = segs.TailTime
  member this.HeadTime = segs.HeadTime

#if USE_FAKE_DATE_TIME
#else

  /// Wait until the buffer contains the given DateTime.
  member this.WaitUntil dateTime =
    while this.HeadTime < dateTime do waitUntil dateTime
  
  /// Wait until the buffer contains the given DateTime.
  member this.WaitUntil(dateTime, ctsToken: CancellationToken) =
    while this.HeadTime < dateTime do waitUntilWithToken dateTime ctsToken

#endif    

  member this.DateTimeRange() = segs.TailTime, segs.Duration
    
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
    let stableSegs =
      let copySegs() = segs.Copy()
      let timeout = TimeSpan.FromMicroseconds 1
      match synchronizer.WhenStableAndEntered timeout copySegs with
      | TimedOut msg -> failwith $"Timed out taking a snapshot of audio buffer state: {msg}"
      | Stable segs -> segs
    let rangeClip, indexBeginInResult, nFramesInResult =
      let indexBeginArg = nFramesOf frameRate (time - startTimeOfBuffer)
      let nFramesArg    = nFramesOf frameRate duration
      clipRange indexBeginArg nFramesArg stableSegs.TailInAll stableSegs.NFrames
    let resultTime     = startTimeOfBuffer + (durationOf frameRate indexBeginInResult)
    let resultDuration = durationOf frameRate nFramesInResult
    let getPart (seg: Seg) =
      let _, indexBegin, nFrames = clipRange indexBeginInResult nFramesInResult seg.TailInAll seg.NFrames
      { Index = indexBegin - seg.Offset; NFrames = nFrames } // Index, indexBegin, and seg.Offset are all in frames not samples
    let parts = [|
      match rangeClip with
      | RangeClip.BeforeData | RangeClip.AfterData -> ()
      | _ ->
      if stableSegs.Old.Active then
        getPart stableSegs.Old
      getPart stableSegs.Cur  |]
    let result = {
      Ring           = ring
      InChannelCount = inChannelCount 
      FrameRate      = frameRate 
      RangeClip      = rangeClip
      NSamples       = nFramesInResult * inChannelCount
      Time           = resultTime
      Duration       = resultDuration
      Parts          = parts  }
    result

  member this.Read (from: _DateTime, duration: _TimeSpan) =
    this.read from duration

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

  static member CopyFromReadResult result =
    let deadData = 12345678.0f
    let resultArray = Array.create<float32> result.NSamples deadData
    let copyPart (indexNS: int) (destIndexNS: int) (nSamples: int) =
      if indexNS + nSamples > Array.length result.Ring then  printfn "asking for more than is there"
      Array.Copy(result.Ring, indexNS, resultArray, destIndexNS, nSamples)
    AudioBuffer.DeliverReadResult result copyPart
    resultArray

  // Mostly for testing.
  member this.InChannelCount   = inChannelCount
  member this.Segs             = segs
  member this.PrintAfter msg   = printAfter msg
  member this.PrintTitle()     = printTitle()
  member this.NFramesTotal     = nFramesTotal
  member this.Ring             = ring
  member this.FrameRate        = frameRate
  member this.NRingFrames      = nRingFrames
  member this.FrameSize        = frameSize
  member this.FrameCount       = latestFrameCount
  member this.LatestBlockIndex = latestBlockIndex
  member this.Simulating       = simulating
  member this.StartTime        = startTimeOfBuffer
