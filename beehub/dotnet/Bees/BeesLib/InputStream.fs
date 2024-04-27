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
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open CSharpHelpers

type Worker = Buf -> int -> int

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream – the callback

// An InputStream object makes recent input data available to clients via a buffer.
// The duration of the audio capacity of the buffer is a parameter.
// A client Task can call the Read method to get buffered data recorded within a given
// TimeSpan starting at a given DateTime.
// A client Task can also subscribe to events issued immediately following each callback
// if low-latency delivery of input audio data is desired.
//
// The interface to the operating system’s audio I/O is provided by the PortAudio library,
// which is written in C and made available on .NET via the PortAudioSharp library, written in C#.
// PortAudio appends data to the InputStream buffer via a callback called at interrupt time.
//
// Synchronization between the interrupt-time acquisition of data and a managed-code Task
// is handled in a lock-free manner transparent to the client.
//
// #######
// The buffer is a ring buffer, which is 
// The data buffered in the ring is managed as one or two segments, Segs.Old and Segs.Cur, with a gap between
// Segs.Cur.Head and Segs.old.Tail.
// Segs.Cur is always Active;
// Segs.Old is Active most of the time but not all.  Segs.Cur.Head, where new callback data is added, never overwrites
// Segs.Old.Tail because when both segs are active, they are separated by a gap.  The duration of the gap is a parameter.
//
// The gap allows a client
// to ask for buffered data and expect it to be there for at least as long as the gap duration without
// being overwritten by callbacks.  The gap is part of a lock-free strategy that avoids a race between a callback 
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
    // Cur is now empty.
    this.Cur.TailTime <- tbdDateTime

// Callback state, shared across callbacks, updated by each callback.
type CbState = {
  // callback args
  mutable Input           : IntPtr
  mutable Output          : IntPtr
  mutable FrameCount      : uint32
  mutable TimeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags     : PortAudioSharp.StreamCallbackFlags
  // callback result
  Ring                    : float32 array
  mutable State           : State
  mutable Segs            : Segs
  mutable AdcStartTime    : _DateTime
  mutable LatestBlock     : int // ring index where latest input block was copied
  mutable SeqNum1         : int
  mutable SeqNum2         : int
  mutable NRingFrames     : int
  mutable NDataFrames     : int
  mutable NGapFrames      : int
  // more stuff
  mutable WithEcho        : bool
  mutable WithLogging     : bool
  mutable CallbackHandoff : CallbackHandoff // modified only once
  TimeInfoBase            : _DateTime // for getting UTC from timeInfo.inputBufferAdcTime
  FrameSize               : int
  Logger                  : Logger
  Simulating              : SimulatingCallbacks } with

  member this.Copy() = { this with Segs = this.Segs.Copy() }
  
  member cbs.Print newTail newHead msg =
    let sRing =
      let empty = '.'
      let data  = '◾'
      let getsNum i = i % 10 = 0
      let mutable ring =
        let num i = char ((i / 10 % 10).ToString())
        let numberedEmpties i = if getsNum i then  num i else  empty
        // "0.........1.........2.........3.........4.........5.........6.........7.........8....."
        Array.init cbs.NRingFrames numberedEmpties
      do // Overwrite empties with seg data.
        let showDataFor seg =
          let first = seg.Tail
          let last  = seg.Head - 1
          let getsNum i = first < i  &&  i < last  &&  getsNum i  // show only interior numbers
          let setDataFor i = if not (getsNum i) then  ring[i] <- data     
          for i in first..last do  setDataFor i
        if cbs.Segs.Old.Active then
          assert (cbs.State = Chasing)
          // "0.........1.........2.........3.........4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
          showDataFor cbs.Segs.Old
        // "◾◾◾◾◾◾◾◾◾◾1◾◾◾◾◾◾◾◾◾2◾◾◾◾◾◾◾◾◾3◾◾◾◾.....4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
        showDataFor cbs.Segs.Cur
      String ring
    let sText =
      let sSeqNum  = sprintf "%2d" cbs.SeqNum1
      let sX       = if String.length msg > 0 then  "*" else  " "
      let sTime    = sprintf "%3d.%3d %3d.%3d"
                       cbs.Segs.Old.TailTime.Millisecond
                       cbs.Segs.Old.HeadTime.Millisecond
                       cbs.Segs.Cur.TailTime.Millisecond
                       cbs.Segs.Cur.HeadTime.Millisecond
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

  member cbs.PrintRing msg =  cbs.Print 0 -1 msg

  member cbs.PrintTitle() =
    let s0 = String.init cbs.Ring.Length (fun _ -> " ")
    let s1 = " seq nFrames timeOld timeCur duration   Cur    new   Old    size   gap   state"
    let s2 = " ––– ––––––– ––––––– ––––––– ––––––––  ––––– –––––– ––––– –––––––– –––  –––––––"
           //   24    5    164.185 185.220 35+21=56  00.35 -16.40 64.85 35+21=56  29  Chasing 
    Console.WriteLine $"%s{s0}%s{s1}"
    Console.WriteLine $"%s{s0}%s{s2}"

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The callback – Copy data from the audio driver into our ring.

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle  = GCHandle.FromIntPtr(userDataPtr)
  let cbs     = handle.Target :?> CbState
  let nFrames = int frameCount
  Volatile.Write(&cbs.SeqNum1, cbs.SeqNum1 + 1)
  if cbs.Simulating = NotSimulating then  Console.Write "."

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  cbs.AdcStartTime <- cbs.TimeInfoBase + _TimeSpan.FromSeconds timeInfo.inputBufferAdcTime

  do
    // Modify the segs so that Segs.Cur.Head points to where the data will go in the ring.
    // Later, after the copy is done, Segs.Cur.Head will point after the new data.
    let nextValues() =
      let newHead = cbs.Segs.Cur.Head + nFrames
      let newTail = newHead - cbs.NDataFrames
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
      cbs.Segs.Cur.TailTime <- cbs.AdcStartTime
      cbs.Segs.Cur.HeadTime <- cbs.AdcStartTime
      let h, t = nextValues() in newHead <- h ; newTail <- t
      if cbs.Simulating <> NotSimulating then  Array.Fill(cbs.Ring, 0f, cbs.Segs.Old.Head, cbs.Ring.Length - cbs.Segs.Old.Head)
      cbs.State <- Chasing
      printRing "exchanged"
    match cbs.State with
    | AtStart ->
      assert (not cbs.Segs.Cur.Active)
      assert (not cbs.Segs.Old.Active)
      assert (newHead = nFrames)  // The block will fit at Ring[0]
      cbs.State <- AtBegin
      cbs.Segs.Cur.TailTime <- cbs.AdcStartTime
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
        // Segs.Old is so small that it vanishes.
        cbs.Segs.Old.Reset()
        cbs.State <- Moving
      else
        cbs.Segs.Old.AdvanceTail nFrames
        let halfGap = cbs.NGapFrames / 2  // in case nFrames has just been adjusted upwards
        assert (newHead + halfGap <= cbs.Segs.Old.Tail)
        cbs.State <- Chasing
    | AtEnd ->
      failwith "Can’t happen."

  UnsafeHelpers.CopyPtrToArrayAtIndex(input, cbs.Ring, cbs.Segs.Cur.Head, nFrames)
  cbs.LatestBlock <- cbs.Segs.Cur.Head
  cbs.Segs.Cur.HeadTime <- cbs.AdcStartTime
  cbs.Segs.Cur.AdvanceHead nFrames
  Volatile.Write(&cbs.SeqNum2, cbs.SeqNum2 + 1)

//cbs.Logger.Add cbs.SeqNum2 cbs.TimeStamp "cb bufs=" ""
  cbs.CallbackHandoff.HandOff()
  PortAudioSharp.StreamCallbackResult.Continue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The InputStream class

type ReadDelivery = float32[] * int * int * int * _DateTime * _TimeSpan -> unit

type InputStreamGetResult =
  | ErrorBeforeData     = 0
  | ErrorAfterData      = 1
  | WarnClippedBothEnds = 2
  | WarnClippedTail     = 3
  | WarnClippedHead     = 4
  | AsRequested         = 5

// initPortAudio() must be called before this constructor.
type InputStream(beesConfig       : BeesConfig          ,
                 inputParameters  : StreamParameters    ,
                 outputParameters : StreamParameters    ,
                 withEcho         : bool                ,
                 withLogging      : bool                ,
                 sim              : SimulatingCallbacks ) =

  let audioDuration = cbSimAudioDuration sim (fun () -> beesConfig.InputStreamAudioDuration                     )
  let gapDuration   = cbSimGapDuration   sim (fun () -> beesConfig.InputStreamRingGapDuration * 2               )
  let nDataFrames   = cbSimNDataFrames   sim (fun () -> durationToNFrames beesConfig.InSampleRate audioDuration )
  let nGapFrames    = cbSimNGapFrames    sim (fun () -> durationToNFrames beesConfig.InSampleRate gapDuration   )
  let nRingFrames   = nDataFrames + (3 * nGapFrames) / 2
  let frameSize     = beesConfig.FrameSize
  let nRingBytes    = int nRingFrames * frameSize
  let startTime     = _DateTime.UtcNow
  let segs          = { Cur = Seg.NewEmpty nRingFrames beesConfig.InSampleRate
                        Old = Seg.NewEmpty nRingFrames beesConfig.InSampleRate }
  
  // When unmanaged code calls managed code (e.g., a callback from unmanaged to managed),
  // the CLR ensures that the garbage collector will not move referenced managed objects
  // in memory during the execution of that managed code.
  // This happens automatically and does not require manual pinning.

  let cbState = {
    // callback args
    Input           = IntPtr.Zero
    Output          = IntPtr.Zero
    FrameCount      = 0u
    TimeInfo        = PortAudioSharp.StreamCallbackTimeInfo()
    StatusFlags     = PortAudioSharp.StreamCallbackFlags()
    // callback result
    Ring            = Array.init<float32> nRingFrames (fun _ -> 0.0f)
    State           = AtStart
    Segs            = segs
    AdcStartTime    = _DateTime.MaxValue // placeholder
    LatestBlock     = 0
    SeqNum1         = -1
    SeqNum2         = -1
    NRingFrames     = nRingFrames
    NDataFrames     = nDataFrames
    NGapFrames      = nGapFrames
    // more stuff
    WithEcho        = withEcho
    WithLogging     = withLogging
    CallbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
    TimeInfoBase    = startTime  // timeInfoBase + adcInputTime -> cbState.TimeStamp
    FrameSize       = frameSize
    Logger          = Logger(8000, startTime)
    Simulating      = sim  }

  let debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    if cbState.Simulating = NotSimulating then Console.Write ","

  let paStream =
    if cbState.Simulating <> NotSimulating then
      dummyInstance<PortAudioSharp.Stream>()
    else
      let streamCallback = PortAudioSharp.Stream.Callback(
        // The intermediate lambda here is required to avoid a compiler error.
        fun        input output frameCount  timeInfo statusFlags userDataPtr ->
          callback input output frameCount &timeInfo statusFlags userDataPtr )
      paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                             outParams       = Nullable<_>(outputParameters)        ,
                                                             sampleRate      = beesConfig.InSampleRate              ,
                                                             framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                             streamFlags     = StreamFlags.ClipOff                  ,
                                                             callback        = streamCallback                       ,
                                                             userData        = cbState                              ) )

  let debugSubscription = dummyInstance<Subscription<CbMessage>>()

  member  this.echoEnabled   () = Volatile.Read &cbState.WithEcho
  member  this.loggingEnabled() = Volatile.Read &cbState.WithEcho

  member val  PaStream          = paStream
  member val  CbState           = cbState
  member val  CbStateLatest     = cbState       with get, set
  member val  StartTime         = startTime
  member val  BeesConfig        = beesConfig
  member val  RingDuration      = audioDuration
  member val  NRingBytes        = nRingBytes
  member val  GapDuration       = gapDuration
  member this.DebugSubscription = debugSubscription

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
    if cbState.Simulating = NotSimulating then Console.Write ","

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    
  member this.durationOf nFrames = durationOf beesConfig.InSampleRate nFrames
  member this.nFramesOf duration = nFramesOf  beesConfig.InSampleRate duration

  member this.tailTime = this.CbStateLatest.Segs.Oldest.TailTime
  member this.headTime = this.CbStateLatest.Segs.Cur   .HeadTime
  
  member this.IsInCallback  : bool * int =
    let n1 = Volatile.Read(&this.CbState.SeqNum1)
    if n1 <> Volatile.Read(&this.CbState.SeqNum2) then true , n1
                                                  else false, n1
  member this.CbStateSnapshot =
    let rec get()  : CbState =
      match this.IsInCallback with
      | true , _       ->  get()
      | false, seqNum1 ->
      let cbState = this.CbState.Copy()
      match Volatile.Read(&this.CbState.SeqNum1) with
      | seqNum1Again when seqNum1 <> seqNum1Again ->  get()
      | _ ->
      cbState
    get()

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
    let cbs = this.CbStateSnapshot
    let (|BeforeData|AfterData|ClippedTail|ClippedHead|ClippedBothEnds|OK|) (wantTime, wantDuration, haveTime, haveDuration) =
      //      Segs.Old         Segs.Cur
      // [.........◾◾◾◾◾◾◾] [◾◾◾◾◾◾◾.....]
      //           a      b  a      b
      //           tail             head
      let wantEnd: _DateTime = wantTime + wantDuration
      let haveEnd: _DateTime = haveTime + haveDuration
      let timeAndDuration tail head = tail, head - tail
      match () with
      | _ when wantEnd  <= haveTime                          ->  BeforeData
      | _ when                           haveEnd <= wantTime ->  AfterData
      | _ when wantTime <  haveTime  &&  haveEnd <  wantEnd  ->  ClippedBothEnds (timeAndDuration haveTime haveEnd)
      | _ when wantTime <  haveTime                          ->  ClippedTail     (timeAndDuration haveTime wantEnd)
      | _ when                           haveEnd <  wantEnd  ->  ClippedHead     (timeAndDuration wantTime haveEnd)
      | _                                                    ->  assert (haveTime <= wantTime)
                                                                 assert (wantEnd  <= haveEnd )
                                                                 OK              (timeAndDuration wantTime wantEnd)
    let deliver (tailTime: _DateTime) duration =
      let size = nFramesOf beesConfig.InSampleRate duration
      let headTime = tailTime + duration
      assert (cbs.Segs.TailTime <= tailTime) ; assert (headTime <= cbs.Segs.HeadTime)
      let deliverSegPortion (seg: Seg) =
        let p = seg.getPortion tailTime duration
        deliver (cbs.Ring, size, p.index, p.nFrames, p.time, p.duration)
      if cbs.Segs.Old.Active  &&  tailTime < cbs.Segs.Old.HeadTime then  deliverSegPortion cbs.Segs.Old
      if                          cbs.Segs.Cur.TailTime < headTime then  deliverSegPortion cbs.Segs.Cur
    let haveTime     = cbs.Segs.TailTime
    let haveDuration = cbs.Segs.Duration
    let tNg = _DateTime.MinValue in let dNg = _TimeSpan.Zero
    match (time, duration, haveTime, haveDuration) with
    | BeforeData             ->               (InputStreamGetResult.ErrorBeforeData    , tNg, dNg)
    | AfterData              ->               (InputStreamGetResult.ErrorAfterData     , tNg, dNg)
    | ClippedTail     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedTail    , t  , d  )
    | ClippedHead     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedHead    , t  , d  )
    | ClippedBothEnds (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedBothEnds, t  , d  )
    | OK              (t, d) -> deliver t d ; (InputStreamGetResult.AsRequested        , t  , d  )  

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
/// <param name="sampleRate"      > Audio sample rate                                               </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output       </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging         </param>
/// <param name="cbMessageQueue"  > CbMessageQueue object handling audio stream                     </param>
/// <returns>An <c>InputStream</c></returns>
// let makeInputStream beesConfig inputParameters outputParameters sampleRate withEcho withLogging  : InputStream =
//   initPortAudio()
//   let inputStream = new InputStream(beesConfig, withEcho, withLogging)
//   let callback = PortAudioSharp.Stream.Callback( // The fun has to be here because of a limitation of the compiler, apparently.
//     fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
//       // inputStream.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) )
//       Console.Write(".\007")
//       PortAudioSharp.StreamCallbackResult.Continue )
//   let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
//                                                                         outParams       = Nullable<_>(outputParameters)        ,
//                                                                         sampleRate      = sampleRate                           ,
//                                                                         framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
//                                                                         streamFlags     = StreamFlags.ClipOff                  ,
//                                                                         callback        = callback                             ,
//                                                                         userData        = Nullable()                           ) )
//   inputStream.PaStream <- paStream
//   paTryCatchRethrow(fun() -> inputStream.Start())
//   inputStream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

