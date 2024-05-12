module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading

open PortAudioSharp

open DateTimeDebugging
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.Logger
open BeesUtil.SubscriberList
open BeesUtil.PortAudioUtils
open BeesUtil.CallbackHandoff
open BeesUtil.SeqNums
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open CSharpHelpers

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
// The gap thus avoids a read–write race condition without locking.  The gap is a parameter
// for InputStream creation.
// 
// To synchronize reading by a client with writing by a callback, there are two atomic
// 32-bit integers, SeqNum1 and SeqNum2.  The callback increments SeqNum1, does its work,
// then increments SeqNum2.  The Read method takes a snapshot of Segs.Cur and Segs.Old
// before delivering the data to the client.  The snapshot saves SeqNum1 in a temp, then
// if SeqNum2 ≠ temp, it starts over; otherwise it takes a copy of the segment info, then
// if SeqNum1 ≠ temp, it starts over; otherwise it returns the snapshot.
 
// writing to the ring and a client reading from the ring, which works as follows:
// There are two sequence numbers SeqNum1 and SeqNum2.  THe callback increments SeqNum1, then updates its persistent state,
// then increments SeqNum2.  Client code that wants to read the ring buffer data, first notes the value of
// SeqNum1, then makes a copy of the segments, then checks that SeqNum2 = SeqNum1, repeating if they are not equal.
//
// The callback (at interrupt time) hands off to a background Task for further processing (not at interrupt time).

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

[<Struct>]
type Segs = {
  mutable Cur : Seg
  mutable Old : Seg }  with

  member this.Copy()   = { Cur = this.Cur.Copy()
                           Old = this.Old.Copy() }
  member this.Oldest   = if this.Old.Active then this.Old else this.Cur
  member this.TailTime = this.Oldest.TailTime
  member this.HeadTime = this.Cur   .HeadTime
  member this.Duration = this.HeadTime - this.TailTime

  member this.Exchange() =
    let tmp = this.Cur  in  this.Cur <- this.Old  ;  this.Old <- tmp
    assert (not this.Cur.Active)

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

// Callback state, shared across callbacks, updated by each callback.
type CbState = {
  // callback args
  mutable Input              : IntPtr
  mutable Output             : IntPtr
  mutable FrameCount         : uint32
  mutable TimeInfo           : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags        : PortAudioSharp.StreamCallbackFlags
  // callback result
  Ring                       : float32 array // samples not frames
  mutable State              : State
  mutable Segs               : Segs
  mutable BlockAdcStartTime  : _DateTime  // datetime of first sample collection in this block
  mutable LatestBlockHead    : int        // ring index where latest input block was copied
  mutable SeqNums            : SeqNums
  mutable NRingFrames        : int
  mutable NRingDataFrames    : int
  mutable NGapFrames         : int
  // more stuff
  mutable NFramesTotal       : uint64
  mutable WithEcho           : bool
  mutable WithLogging        : bool
  mutable CallbackHandoff    : CallbackHandoff
  mutable StreamAdcStartTime : _DateTime       // datetime of first sample collection since Start()
  mutable PaStreamTime       : unit -> PaTime  // now, in PaTime units
  InChannelCount             : int
  FrameRate                  : float
  FrameSize                  : int  // bytes
  Logger                     : Logger
  Simulating                 : SimulatingCallbacks } with

  member cbs.Copy() = { cbs with Segs = cbs.Segs.Copy() }

  member cbs.markRingSpanAsDead srcFrameIndex nFrames =
    let srcFrameIndexNS = srcFrameIndex * cbs.InChannelCount
    let nSamples        = nFrames       * cbs.InChannelCount
    Array.Fill(cbs.Ring, 9999999f, srcFrameIndexNS, nSamples)
  
  member cbs.PrintRing dataChar msg =
      let empty = '.'
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
    let sRing = cbs.PrintRing '◾' msg
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

let mutable thresh = 0

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle  = GCHandle.FromIntPtr(userDataPtr)
  let cbs     = handle.Target :?> CbState
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
  if cbs.StreamAdcStartTime = tbdDateTime then
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

type ReadDelivery = float32[]   // source array
                  * int         // sizeNF
                  * int         // indexNF
                  * int         // nFrames 
                  * int         // nChannels
                  * _DateTime   // time
                  * _TimeSpan   // duration
                   -> unit

type InputStreamGetResult =
  | ErrorTimeout        = 0
  | ErrorBeforeData     = 1
  | ErrorAfterData      = 2
  | WarnClippedBothEnds = 3
  | WarnClippedTail     = 4
  | WarnClippedHead     = 5
  | AsRequested         = 6

// initPortAudio() must be called before this constructor.
type InputStream(beesConfig       : BeesConfig          ,
                 inputParameters  : StreamParameters    ,
                 outputParameters : StreamParameters    ,
                 withEcho         : bool                ,
                 withLogging      : bool                ,
                 sim              : SimulatingCallbacks ) =

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
  // the CLR ensures that the garbage collector will not move referenced managed objects
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
    Ring               = Array.init<float32> nRingSamples (fun _ -> 0.0f)
    State              = AtStart
    Segs               = segs
    BlockAdcStartTime  = tbdDateTime
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
    StreamAdcStartTime = tbdDateTime
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

  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow (fun() -> this.PaStream.Start() )
    printfn $"InputStream size: {this.NRingBytes / 1_000_000} MB for {this.RingDuration}"
    printfn $"InputStream nFrames: {this.CbState.NRingFrames}"

  member this.Stop() =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Stop () )

  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  member this.AfterCallback() =
    let cbs = this.CbStateSnapshot()
    if cbs.Segs.Cur.Head > thresh then
      thresh <- thresh + int (round (cbs.FrameRate))
      let sinceStart = cbs.TimeInfo.inputBufferAdcTime - this.PaStream.Time
      Console.WriteLine $"%6d{cbs.Segs.Cur.Head} %3d{cbs.Segs.Cur.Head / int cbs.FrameCount} %10f{sinceStart}"
    cbs.Segs.Cur.Check()
     // if cbState.Simulating = NotSimulating then Console.Write ","

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    
  member this.durationOf nFrames = durationOf beesConfig.InFrameRate nFrames
  member this.nFramesOf duration = nFramesOf  beesConfig.InFrameRate duration

  member this.tailTime = this.CbStateLatest.Segs.TailTime
  member this.headTime = this.CbStateLatest.Segs.HeadTime
  
  member this.CbStateSnapshot() : CbState =
    let copyCbState() = this.CbState.Copy()
    let timeout = TimeSpan.FromMicroseconds 1
    match this.CbState.SeqNums.WhenStable copyCbState timeout with
    | OK cbState -> cbState
    | TimedOut s -> failwith "Timed out taking a snapshot of CbState" 

  member this.range() = this.CbState.Segs.TailTime, this.CbState.Segs.HeadTime
    
  // Read a range of data from the input recent history.
  // The caller requests a range expressed as a DateTime time and TimeSpan duration.
  // The delivered range may be clipped to the available subrange, depending on availability.
  // The data is delivered via 0 1 or 2 calls to the provided callback, to which
  // the data is passed with a reference to the internal buffer array and an index;
  // the data is guaranteed to be valid only for the duration of the callback.
  // The result is a tuple of an InputStreamGetResult enum and the 
  // time and duration of the range of the delivered data.
  // Synchronizatrion with the callback is handled by the CbStateSnapshot property without locking.
  member this.read (time: _DateTime) (duration: _TimeSpan) (deliver: ReadDelivery)
                   : (InputStreamGetResult * _DateTime * _TimeSpan) =
    let cbs = this.CbStateSnapshot()
    let (|BeforeData|AfterData|ClippedTail|ClippedHead|ClippedBothEnds|OK|) (wantTime, wantDuration, haveTime, haveDuration) =
      // Return the situation along with time and duration clipped to fit within Segs.
      //      Segs.Old         Segs.Cur
      // [.........◾◾◾◾◾◾◾] [◾◾◾◾◾◾◾.....]
      //           a      b  a      b
      //           tail             head
      let wantEnd: _DateTime = wantTime + wantDuration
      let haveEnd: _DateTime = haveTime + haveDuration
      let timeAndDuration tail head =
        let duration = head - tail
        assert (cbs.Segs.Oldest.TailTime <= tail) ; assert (head <= cbs.Segs.Cur.HeadTime)
        tail, duration
      match () with
      | _ when wantEnd  <= haveTime                          ->  BeforeData      (timeAndDuration haveTime haveTime)
      | _ when                           haveEnd <= wantTime ->  AfterData       (timeAndDuration haveEnd  haveEnd )
      | _ when wantTime <  haveTime  &&  haveEnd <  wantEnd  ->  ClippedBothEnds (timeAndDuration haveTime haveEnd )
      | _ when wantTime <  haveTime                          ->  ClippedTail     (timeAndDuration haveTime wantEnd )
      | _ when                           haveEnd <  wantEnd  ->  ClippedHead     (timeAndDuration wantTime haveEnd )
      | _                                                    ->  assert (haveTime <= wantTime)
                                                                 assert (wantEnd  <= haveEnd )
                                                                 OK              (timeAndDuration wantTime wantEnd )
    let deliver (time: _DateTime) duration =
      let nFrames  = nFramesOf beesConfig.InFrameRate duration
      let headTime = time + duration
      assert (cbs.Segs.TailTime <= time) ; assert (headTime <= cbs.Segs.HeadTime)
      let deliverSegPortion (seg: Seg) =
        let p = seg.clipToFit time duration
        deliver (cbs.Ring, nFrames, p.IndexBegin, p.NFrames, cbs.InChannelCount, p.TimeBegin, p.Duration)
      if cbs.Segs.Old.Active  &&  time < cbs.Segs.Old.HeadTime     then  deliverSegPortion cbs.Segs.Old
      if                          cbs.Segs.Cur.TailTime < headTime then  deliverSegPortion cbs.Segs.Cur
    if cbs.Simulating = NotSimulating then Console.Write "R"
    match (time, duration, cbs.Segs.TailTime, cbs.Segs.Duration) with
    | BeforeData      (t, d) ->               (InputStreamGetResult.ErrorBeforeData    , t, d)
    | AfterData       (t, d) ->               (InputStreamGetResult.ErrorAfterData     , t, d)
    | ClippedTail     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedTail    , t, d)
    | ClippedHead     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedHead    , t, d)
    | ClippedBothEnds (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedBothEnds, t, d)
    | OK              (t, d) -> deliver t d ; (InputStreamGetResult.AsRequested        , t, d)  

  member this.Read (from: _DateTime, duration: _TimeSpan, f: ReadDelivery) =
    this.read from duration f
    
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––



  // let getSome timeStart count  : (int * int) seq = seq {
  //   if cbMessage.Segs.Old.Active then
  //     if timeStart >= segHead then
  //       // return empty sequence
  //     let timeOffset = timeStart - cbMessage.Segs.Old.TailTime
  //     assert (timeOffset >= 0)
  //     let nFrames = cbMessage.Segs.Old.NFramesOf timeOffset
  //     let indexStart = cbMessage.Segs.Old.Tail + nFrames
  //     if indexStart < cbMessage.Segs.Old.Head then
  //       yield (indexStart, nFrames)
  //   if cbMessage.Segs.Cur.Active then yield (cbMessage.Segs.Cur.Tail, cbMessage.Segs.Cur.NFrames)
  // }

  //
  // let x = tailTime
  // let get (dateTime: _DateTime) (duration: _TimeSpan) (worker: Worker) =
  //   let now = _DateTime.Now
  //   let timeStart = max dateTime tailTime
  //   if timeStart + duration > now then  Error "insufficient buffered data"
  //   else
  //   let rec deliver timeStart nFrames =
  //     let nSamples = nFrames / frameSize
  //     let r = worker fromPtr nSamples
  //   let nextIndex = ringIndex timeStart
  //   let count =
  //   deliver next timeStart
  //   Success timeStart


  // let keep (duration: _TimeSpan) =
    // assert (duration > _TimeSpan.Zero)
    // let now = _DateTime.Now
    // let dateTime = now - duration
    // tailTime <-
    //   if dateTime < tailTime then  tailTime
    //                          else  dateTime
    // tailTime

  member private is.offsetOfDateTime (dateTime: _DateTime)  : Option<Seg * int> =
    if not (is.tailTime <= dateTime && dateTime <= is.headTime) then Some (is.CbStateLatest.Segs.Cur, 1)
    else None


  // member private is.take inputTake =
  //   let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
  //   let size = frameCountToByteCount inputTake.FrameCount
  //   System.Buffer.BlockCopy(from, 0, buffer, index, size)
  //   advanceIndex inputTake.FrameCount
  //   inputTake.CompletionSource.SetResult()


  /// Create a stream of samples starting at a past _DateTime.
  /// The stream is exhausted when it gets to the end of buffered data.
  /// The recipient is responsible for separating out channels from the sequence.
  // member this.Get(dateTime: _DateTime, worker: Worker)  : SampleType seq option = seq {
  //    let segIndex = segOfDateTime dateTime
  //    match seg with
  //    | None: return! None
  //    | Some seg :
  //    if isInSegs.Old dateTime then
  //    WIP
  //
  // }

  interface IDisposable with
    member this.Dispose() =
      Console.WriteLine("Disposing inputStream")
      this.PaStream.Dispose()



// See Theory of Operation comment before main at the end of this file.



//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> CbMessageQueue handler

/// NEEDS WORK
/// Main does the following:
/// - Initialize PortAudio.
/// - Create everything the callback will need.
///   - sampleRate, inputParameters, outputParameters
///   - a CbMessageQueue, which
///     - accepts a CbMessage from each callback
///     - calls the given handler asap for each CbMessage queued
///   - a CbContext struct, which is passed to each callback
/// - runs the cbMessageQueue
/// The audio callback is designed to do as little as possible at interrupt time:
/// - grabs a CbMessage from a preallocated ItemPool
/// - copies the input data buf into the CbMessage
/// - inserts the CbMessage into in the CbMessageQueue for later processing

// <summary>
//   Creates a Stream.Callback that:
//   <list type="bullet">
//     <item><description> Allocates no memory because this is a system-level callback </description></item>
//     <item><description> Gets a <c>CbMessage</c> from the pool and fills it in        </description></item>
//     <item><description> Posts the <c>CbMessage</c> to the <c>cbMessageQueue</c>     </description></item>
//   </list>
// </summary>
// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
// <param name="cbMessageQueue" > The <c>CbMessageQueue</c> to post to           </param>
// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>

//–––––––––––––––––––––––––––––––––––––
// PortAudioSharp.Stream

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                               </param>
/// <param name="outputParameters"> Parameters for output audio stream                              </param>
/// <param name="frameRate"       > Audio frame rate (a.k.a, sample rate)                           </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output       </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging         </param>
/// <param name="cbMessageQueue"  > CbMessageQueue object handling audio stream                     </param>
/// <returns>An <c>InputStream</c></returns>
// let makeInputStream beesConfig inputParameters outputParameters frameRate withEcho withLogging  : InputStream =
//   initPortAudio()
//   let inputStream = new InputStream(beesConfig, withEcho, withLogging)
//   let callback = PortAudioSharp.Stream.Callback( // The fun has to be here because of a limitation of the compiler, apparently.
//     fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
//       // inputStream.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) )
//       Console.Write(".\007")
//       PortAudioSharp.StreamCallbackResult.Continue )
//   let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
//                                                                         outParams       = Nullable<_>(outputParameters)        ,
//                                                                         sampleRate      = frameRate                           ,
//                                                                         framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
//                                                                         streamFlags     = StreamFlags.ClipOff                  ,
//                                                                         callback        = callback                             ,
//                                                                         userData        = Nullable()                           ) )
//   inputStream.PaStream <- paStream
//   paTryCatchRethrow(fun() -> inputStream.Start())
//   inputStream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

