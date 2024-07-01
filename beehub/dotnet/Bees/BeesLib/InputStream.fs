module BeesLib.InputStream

open System
open System.Runtime.InteropServices
open System.Threading

open PortAudioSharp

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.Util
open BeesUtil.PortAudioUtils
open BeesUtil.CallbackHandoff
open BeesUtil.Synchronizer
open BeesUtil.SubscriberList
open BeesLib.BeesConfig
open BeesLib.AudioBuffer
open CSharpHelpers


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// An InputStream object makes recent input data available to clients via a buffer.
//
// The interface to the operating system’s audio I/O is provided by the PortAudio library,
// which is written in C and made available on .NET via the PortAudioSharp library, written
// in C#.  An InputStream object is a wrapper for a PortAudioSharp Stream object.  The
// InputStream constructor sets up a callback function that is called from a system interrupt
// but runs in managed code.  The callback function is written to be quick and not to do any
// allocations.
//
// A client gets data from the InputStream via the Buffer member.
//
// The InputStream class is callable from C# or F# and is written in F#.

/// Callback state.
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
// The callback – Copies data from the audio driver into the Buffer,
// then hands off to a background Task for further processing in managed code.

let mutable threshold = 0 // for debugging, to get a printout from at reasonable intervals

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let cbs     = GCHandle.FromIntPtr(userDataPtr).Target :?> CbState
  let buffer  = cbs.Buffer
  let inputBufferAdcTime = timeInfo.inputBufferAdcTime
  let inputBufferAdcDateTime() =
    let f = cbs.PaStreamTime()
    let secondsSinceAdcTime = f - inputBufferAdcTime
    let timeTilNow = _TimeSpan.FromSeconds secondsSinceAdcTime
    _DateTime.Now - timeTilNow
  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 buffer.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)
  cbs.Synchronizer.EnterUnstable()
  // callback args from PortAudioSharp
  cbs.Input       <- input
  cbs.Output      <- output
  cbs.FrameCount  <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo    <- timeInfo
  cbs.StatusFlags <- statusFlags
  buffer.AddSystemData(input, frameCount, inputBufferAdcDateTime)
  do
    let curHeadNS = buffer.LatestBlockIndex * buffer.InChannelCount
    let nSamples  = int frameCount          * buffer.InChannelCount
    UnsafeHelpers.CopyPtrToArrayAtIndex(input, buffer.Ring, curHeadNS, nSamples)
  cbs.Synchronizer.LeaveUnstable()
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
  let synchronizer     = Synchronizer.New()
  let bufConfig = {
    AudioDuration  = cbSimAudioDuration sim (fun () -> beesConfig.InputStreamAudioDuration        )
    GapDuration    = cbSimGapDuration   sim (fun () -> beesConfig.InputStreamRingGapDuration * 2.0)
    Simulating     = sim
    InChannelCount = beesConfig.InChannelCount
    InFrameRate    = beesConfig.InFrameRate } 

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
    Buffer             = AudioBuffer(bufConfig, synchronizer)
    Synchronizer       = synchronizer
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

  member  this.echoEnabled   () = Volatile.Read &cbState.WithEcho
  member  this.loggingEnabled() = Volatile.Read &cbState.WithLogging

  member val  CbState = cbState
  member val  Buffer  = cbState.Buffer

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  /// <summary>
  /// Starts the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.Buffer.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow (fun() -> paStream.Start() )
    printfn $"InputStream size:    {cbState.Buffer.NRingBytes / 1_000_000} MB for {cbState.Buffer.MaxDuration}"
    printfn $"InputStream nFrames: {this.CbState.Buffer.NRingFrames}"

  /// <summary>
  /// Stops the input stream and the PortAudio stream owned by it.
  /// </summary>
  member this.Stop() =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.Buffer.Simulating <> NotSimulating then ()
    else
    paTryCatchRethrow(fun() -> paStream.Stop () )

  
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
    let cbs    = this.CbState
    let buffer = this.Buffer
    subscriberList.Broadcast (this, cbs)
//  if buffer.Simulating <> NotSimulating then ()
//  else
//  if buffer.LatestBlockIndex > threshold then
//    threshold <- threshold + int (roundAway buffer.FrameRate)
//    let sinceStart = cbs.TimeInfo.inputBufferAdcTime - paStream.Time
//    Console.WriteLine $"%6d{buffer.Segs.Cur.Head} %3d{buffer.Segs.Cur.Head / int cbs.FrameCount} %10f{sinceStart}"
//  if this.Buffer.Simulating = NotSimulating then Console.Write ","
   
//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

  interface IDisposable with
    member this.Dispose() =
  //  Console.WriteLine("Disposing inputStream")
  //  this.PaStream.Dispose()  // I think this crashes because PaStream doesn’t like being closed twice.
      ()
