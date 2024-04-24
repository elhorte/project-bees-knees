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
// InputStream – callback state

// The callback adds data to the ring buffer.  The duration of the audio capacity of the ring is a parameter.
// The data in the ring buffer is the concatenation of two segments, Segs.Old and Segs.Cur.  From time to
// time Segs.Old is empty.  Segs.Cur.Head, where new callback data is added, never overwrites Segs.Old.Tail
// because they are separated by a gap. The duration of the gap is a parameter.  The gap allows a client
// to ask for past buffered data and expect it to be there for at least as long as the gap duration without
// being overwritten by callbacks.  The gap is part of a lock-free way to avoid a race between callbacks 
// writing to the ring and a client reading from the ring.
// The callback (at interrupt time) hands off to a background Task for further processing (not at interrupt time).

// Internal management of the ring is governed by a state variable.

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
  mutable Cur   : Seg
  mutable Old   : Seg }  with

  member this.Copy()     = { Cur = this.Cur.Copy()
                             Old = this.Old.Copy() }
  member this.Oldest     = if this.Old.Active then this.Old else this.Cur
  member this.TimeTail   = this.Oldest.TailTime
  member this.TimeHead   = this.Cur   .HeadTime
  member this.Duration   = this.TimeHead - this.TimeTail

  member this.Exchange() =
    let tmp = this.Cur  in  this.Cur <- this.Old  ;  this.Old <- tmp
    this.Cur.TailTime <- tbdDateTime // Cur is now empty.

// Callback state, updated by each callback.
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
  mutable IsInCallback    : bool
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
        // "..........1.........2.........3.........4.........5.........6.........7.........8....."
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
          // "..........1.........2.........3.........4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
          showDataFor cbs.Segs.Old
        // "◾◾◾◾◾◾◾◾◾◾1◾◾◾◾◾◾◾◾◾2◾◾◾◾◾◾◾◾◾3◾◾◾◾.....4.........5.........6...◾◾◾◾◾◾7◾◾◾◾◾◾◾◾◾8◾◾◾◾."
        showDataFor cbs.Segs.Cur
      String ring
    let sText =
      let sSeqNum  = sprintf "%2d" cbs.SeqNum1
      let sX       = if String.length msg > 0 then  "*" else  " "
      let sTime    = sprintf "%3d.%3d %3d.%3d"
                       cbs.Segs.Old.TailTime.Milliseconds
                       cbs.Segs.Old.HeadTime.Milliseconds
                       cbs.Segs.Cur.TailTime.Milliseconds
                       cbs.Segs.Cur.HeadTime.Milliseconds
      let sDur     = let sum = cbs.Segs.Cur.Duration.Milliseconds + cbs.Segs.Old.Duration.Milliseconds
                     $"{cbs.Segs.Cur.Duration.Milliseconds:d2}+{cbs.Segs.Old.Duration.Milliseconds:d2}={sum:d2}"
      let sCur     = cbs.Segs.Cur.ToString "cur"
      let sNewTail = sprintf "%3d" newTail
      let sNew     = if newHead < 0 then  "      "  else  $"{sNewTail:S3}.{newHead:d2}"
      let sOld     = cbs.Segs.Old.ToString "old"
      let sTotal   = let sum = cbs.Segs.Cur.NFrames + cbs.Segs.Old.NFrames
                     $"{cbs.Segs.Cur.NFrames:d2}+{cbs.Segs.Old.NFrames:d2}={sum:d2}"
      let sGap     = if cbs.Segs.Old.Active then sprintf "%2d" (cbs.Segs.Old.Tail - cbs.Segs.Cur.Head) else  "  "
      let sState   = $"{cbs.State}"
      // "cur 00.35  new -11.45 old 64.85 35+21=56  gap 29 Chasing "
      $"%s{sSeqNum}%s{sX} %s{sTime} %s{sDur}  %s{sCur}  new %s{sNew} %s{sOld} %s{sTotal}  gap {sGap:s2} %s{sState} %s{msg}"
    Console.WriteLine $"%s{sRing}  %s{sText}"

  member cbs.PrintRing msg =  cbs.Print 0 -1 msg

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The callback – Copy data from the audio driver into our ring.

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle  = GCHandle.FromIntPtr(userDataPtr)
  let cbs     = handle.Target :?> CbState
  let nFrames = int frameCount
  Volatile.Write(&cbs.IsInCallback, true)
  if cbs.Simulating = NotSimulating then  Console.Write "."

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  Volatile.Write(&cbs.SeqNum1, cbs.SeqNum1 + 1)
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
    let printRing msg = cbs.Print newTail newHead msg
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
        assert (newHead + cbs.NGapFrames <= cbs.Segs.Old.Tail)
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
  Volatile.Write(&cbs.IsInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Support for the get() member.


  //      Segs.Old         Segs.Cur
  // [.........◾◾◾◾◾◾◾] [◾◾◾◾◾◾◾.....]
  //           a      b  a      b
  //           t                h
let (|BeforeData|AfterData|ClippedTail|ClippedHead|ClippedBothEnds|OK|) (wantTime, wantDuration, haveTime, haveDuration) =
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
  

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The InputStream class

type GetCallback = float32[] * int * int * int * _DateTime * _TimeSpan -> unit

type InputStreamGetResult =
  | ErrorBeforeData     = 0
  | ErrorAfterData      = 1
  | WarnClippedBothEnds = 2
  | WarnClippedTail     = 3
  | WarnClippedHead     = 4
  | ResultOK            = 5

// initPortAudio() must be called before this constructor.
type InputStream(beesConfig       : BeesConfig          ,
                 inputParameters  : StreamParameters    ,
                 outputParameters : StreamParameters    ,
                 withEcho         : bool                ,
                 withLogging      : bool                ,
                 sim              : SimulatingCallbacks ) =

  let audioDuration = cbSimAudioDuration sim (fun () -> beesConfig.InputStreamAudioDuration                     )
  let gapDuration   = cbSimGapDuration   sim (fun () -> beesConfig.InputStreamRingGapDuration                   )
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
    IsInCallback    = false
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
  
  member this.CbStateSnapshot =
    let rec get()  : CbState =
      let seqNum1 = Volatile.Read(&this.CbState.SeqNum1)
      let cbState = this.CbState.Copy()
      let seqNum2 = Volatile.Read(&this.CbState.SeqNum2)
      if seqNum1 <> seqNum2 then  get()
                            else  cbState
    get()

  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  member this.AfterCallback() =
    if cbState.Simulating = NotSimulating then Console.Write ","

  member private is.debuggingSubscriber cbMessage subscriptionId unsubscriber  : unit =
    Console.Write ","
    
  member this.durationOf nFrames = durationOf beesConfig.InSampleRate nFrames
  member this.nFramesOf duration = nFramesOf  beesConfig.InSampleRate duration

  member this.timeTail = this.CbStateLatest.Segs.Oldest.TailTime
  member this.timeHead = this.CbStateLatest.Segs.Cur   .HeadTime

  //      Segs.Old         Segs.Cur
  // [.........◾◾◾◾◾◾◾] [◾◾◾◾◾◾◾.....]
  //           a      b  a      b
  //           tail             head
  member this.get (time: _DateTime) (duration: _TimeSpan) (f: GetCallback)
                  : (InputStreamGetResult * _DateTime * _TimeSpan) =
    let cbs = this.CbStateSnapshot
    let deliver (timeTail: _DateTime) duration =
      let size = nFramesOf beesConfig.InSampleRate duration
      let timeHead = timeTail + duration
      assert (cbs.Segs.TimeTail <= timeTail) ; assert (timeHead <= cbs.Segs.TimeHead)
      let deliverSegPortion (seg: Seg) =
        let p = seg.getPortion timeTail duration
        f (cbs.Ring, size, p.index, p.nFrames, p.time, p.duration)
      if cbs.Segs.Old.Active  &&  timeTail < cbs.Segs.Old.HeadTime then  deliverSegPortion cbs.Segs.Old
      if                          cbs.Segs.Cur.TailTime < timeHead then  deliverSegPortion cbs.Segs.Cur
    let haveTime     = cbs.Segs.TimeTail
    let haveDuration = cbs.Segs.Duration
    let ndt = _DateTime.MinValue in let nts = _TimeSpan.Zero
    match (time, duration, haveTime, haveDuration) with
    | BeforeData             ->               (InputStreamGetResult.ErrorBeforeData    , ndt, nts)
    | AfterData              ->               (InputStreamGetResult.ErrorAfterData     , ndt, nts)
    | ClippedBothEnds (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedBothEnds, t  , d  )
    | ClippedTail     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedTail    , t  , d  )
    | ClippedHead     (t, d) -> deliver t d ; (InputStreamGetResult.WarnClippedHead    , t  , d  )
    | OK              (t, d) -> deliver t d ; (InputStreamGetResult.ResultOK           , t  , d  )  

  member this.Get (from: _DateTime, duration: _TimeSpan, f: GetCallback) =
    this.get from duration f
    
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––



  // let getSome timeStart count  : (int * int) seq = seq {
  //   if cbMessage.Segs.Old.Active then
  //     if timeStart >= segHead then
  //       // return empty sequence
  //     let timeOffset = timeStart - cbMessage.Segs.Old.TimeTail
  //     assert (timeOffset >= 0)
  //     let nFrames = cbMessage.Segs.Old.NFramesOf timeOffset
  //     let indexStart = cbMessage.Segs.Old.Tail + nFrames
  //     if indexStart < cbMessage.Segs.Old.Head then
  //       yield (indexStart, nFrames)
  //   if cbMessage.Segs.Cur.Active then yield (cbMessage.Segs.Cur.Tail, cbMessage.Segs.Cur.NFrames)
  // }

  //
  // let x = timeTail
  // let get (dateTime: _DateTime) (duration: _TimeSpan) (worker: Worker) =
  //   let now = _DateTime.Now
  //   let timeStart = max dateTime timeTail
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
    // timeTail <-
    //   if dateTime < timeTail then  timeTail
    //                          else  dateTime
    // timeTail

  member private is.offsetOfDateTime (dateTime: _DateTime)  : Option<Seg * int> =
    if not (is.timeTail <= dateTime && dateTime <= is.timeHead) then Some (is.CbStateLatest.Segs.Cur, 1)
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


// let cbAtomically cbState f =
//   let (cbs: CbState) = cbState
//   let rec spin() =
//     if Volatile.Read &cbs.isInCallback then spin()
//     f cbs // Copy out the stuff needed from cbState.
//     if Volatile.Read &cbs.isInCallback then spin()
//   spin()


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

