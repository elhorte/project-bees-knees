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
open BeesUtil.Synchronizer
open BeesUtil.RangeClipper
open BeesUtil.SubscriberList
open BeesLib.BeesConfig
open BeesLib.AudioBuffer
open CSharpHelpers


let dummyDateTime = _DateTime.MaxValue
let dummyTimeSpan = _TimeSpan.MaxValue


let durationOf frameRate nFrames  = _TimeSpan.FromSeconds (float nFrames / frameRate)
let nFramesOf  frameRate duration = int (round ((duration: _TimeSpan).TotalMicroseconds / 1_000_000.0 * frameRate))


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


type CbState = {
  // callback args from PortAudioSharp
  mutable Input              : IntPtr  // block of incoming data 
  mutable Output             : IntPtr  // block of outgoing data
  mutable FrameCount         : uint32
  mutable TimeInfo           : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags        : PortAudioSharp.StreamCallbackFlags
  // more stuff
  Buffer                     : AudioBuffer
  mutable Synchronizer       : Synchronizer
  mutable WithEcho           : bool              // echo    is in effect
  mutable WithLogging        : bool              // logging is in effect
  // these are modified once, as early as possible
  mutable CallbackHandoff    : CallbackHandoff   // for handing off events for further processing in managed code
  mutable PaStreamTime       : unit -> PaTime  } // Function to get the current date and time, in PaTime units

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The callback – Copy data from the audio driver into our ring.

let mutable threshold = 0 // for debugging, to get a printout from at reasonable intervals

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle  = GCHandle.FromIntPtr(userDataPtr)
  let cbs     = handle.Target :?> CbState
  let buffer  = cbs.Buffer
  let nFrames = int frameCount

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 buffer.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  cbs.Synchronizer.EnterUnstable()

  // callback args from PortAudioSharp
  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags

  let inputBufferAdcDateTime() =
    let f = cbs.PaStreamTime()
    let secondsSinceAdcTime = f - timeInfo.inputBufferAdcTime
    let timeTilNow = _TimeSpan.FromSeconds secondsSinceAdcTime
    _DateTime.Now - timeTilNow
  buffer.AddSystemData(input, frameCount, inputBufferAdcDateTime) 
  let curHeadNS = buffer.LatestBlockIndex * buffer.InChannelCount
  let nSamples  = nFrames                 * buffer.InChannelCount
  UnsafeHelpers.CopyPtrToArrayAtIndex(input, buffer.Ring, curHeadNS, nSamples)
//Console.Write "."
//if cbs.Synchronizer.N1 % 20us = 0us then  Console.WriteLine $"%6d{cbs.Segs.Cur.Head} %3d{cbs.Segs.Cur.Head / nFrames} %10f{timeInfo.inputBufferAdcTime - cbs.TimeInfoBase}"
  cbs.Synchronizer.LeaveUnstable()

//cbs.Logger.Add cbs.SeqNum2 cbs.TimeStamp "cb bufs=" ""
  cbs.CallbackHandoff.HandOff()
  PortAudioSharp.StreamCallbackResult.Continue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// The InputStream class

// initPortAudio() must be called before this constructor.
type InputStream(beesConfig: BeesConfig) =
  let inputParameters  = beesConfig.InputParameters
  let outputParameters = beesConfig.OutputParameters
  let withEcho         = beesConfig.WithEcho
  let withLogging      = beesConfig.WithLogging
  let sim              = beesConfig.Simulating 
  let bufConfig = {
    AudioBufferDuration    = cbSimAudioDuration sim (fun () -> beesConfig.InputStreamAudioDuration                    )
    AudioBufferGapDuration = cbSimGapDuration   sim (fun () -> beesConfig.InputStreamRingGapDuration * 2.0            )
    SampleSize             = sizeof<float32>
    Simulating             = sim
    InChannelCount         = 1 // inputParameters.channelCount
    InFrameRate            = 1000 } 
  // When unmanaged code calls managed code (e.g., a callback from unmanaged to managed),
  // the .NET CLR ensures that the garbage collector will not move referenced managed objects
  // in memory during the execution of that managed code.
  // This happens automatically and does not require manual pinning.

  let cbState = {
    // callback args from PortAudioSharp
    Input              = IntPtr.Zero
    Output             = IntPtr.Zero
    FrameCount         = 0u
    TimeInfo           = PortAudioSharp.StreamCallbackTimeInfo()
    StatusFlags        = PortAudioSharp.StreamCallbackFlags()
    // affected by callbacks
    Buffer             = AudioBuffer(bufConfig)
    Synchronizer       = Synchronizer.New()
    // more stuff
    WithEcho           = withEcho
    WithLogging        = withLogging
    // these are modified once, as early as possible
    CallbackHandoff    = dummyInstance<CallbackHandoff>()
    PaStreamTime       = fun () -> PaTimeBad  }

  let paStream =
    if cbState.Buffer.Simulating <> NotSimulating then
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
  let subscriberList = new SubscriberList<InputStream*CbState>()

  do
//  printfn $"{beesConfig.InFrameRate}"
    ()

  member  this.echoEnabled   () = Volatile.Read &cbState.WithEcho
  member  this.loggingEnabled() = Volatile.Read &cbState.WithLogging

  member val  Buffer            = cbState.Buffer
  member val  PaStream          = paStream
  member val  CbState           = cbState
  member val  StartTime         = cbState.Buffer.StartTime
  member val  BeesConfig        = beesConfig
  member val  RingDuration      = cbState.Buffer.MaxDuration
  member val  GapDuration       = cbState.Buffer.GapDuration
  member val  NRingBytes        = cbState.Buffer.NRingBytes

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  /// <summary>
  /// Starts the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.Buffer.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow (fun() -> this.PaStream.Start() )
    printfn $"InputStream size:    {this.NRingBytes / 1_000_000} MB for {this.RingDuration}"
    printfn $"InputStream nFrames: {this.CbState.Buffer.NRingFrames}"

  /// <summary>
  /// Stops the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Stop() =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.Buffer.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Stop () )

  
  /// Subscribe a post-callback handler, which will be called in managed code after each callback.
  member this.Subscribe  (subscriber: SubscriberHandler<InputStream*CbState>)  : Subscription<InputStream*CbState> =
    subscriberList.Subscribe subscriber

  /// Unsubscribe a post-callback handler.
  member this.Unsubscribe(subscription: Subscription<InputStream*CbState>)  : bool =
    subscriberList.Unsubscribe subscription

  
  /// Called only when Simulating, to simulate a callback.
  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  /// <summary>
  /// Called from a <c>Task</c> (managed code) as soon as possible after the callback.
  /// </summary>
  member this.AfterCallback() =
    let cbs = this.CbState
    subscriberList.Broadcast (this, cbs)
    if cbs.Buffer.Simulating <> NotSimulating then ()
    else
    if cbs.Buffer.LatestBlockIndex > threshold then
      threshold <- threshold + int (roundAway cbs.Buffer.FrameRate)
  //  let sinceStart = cbs.TimeInfo.inputBufferAdcTime - this.PaStream.Time
  //  Console.WriteLine $"%6d{cbs.Segs.Cur.Head} %3d{cbs.Segs.Cur.Head / int cbs.FrameCount} %10f{sinceStart}"
  //  if cbState.Simulating = NotSimulating then Console.Write ","
      ()
    
  member this.durationOf nFrames = durationOf this.CbState.Buffer.FrameRate nFrames
  member this.nFramesOf duration = nFramesOf  this.CbState.Buffer.FrameRate duration

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
  member this.CbStateSnapshot : CbState =
    let copyCbState() = this.CbState.Copy()
    let timeout = TimeSpan.FromMicroseconds 1
    match this.CbState.Synchronizer.WhenStableAndEntered timeout copyCbState with
    | Stable cbState -> cbState
    | TimedOut msg -> failwith $"Timed out taking a snapshot of CbState: {msg}" 

  member this.range() = this.CbState.Segs.TailTime, this.CbState.Segs.HeadTime
   
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  interface IDisposable with
    member this.Dispose() =
  //  Console.WriteLine("Disposing inputStream")
  //  this.PaStream.Dispose()  // I think this crashes because PaStream doesn’t like being closed twice.
      ()
