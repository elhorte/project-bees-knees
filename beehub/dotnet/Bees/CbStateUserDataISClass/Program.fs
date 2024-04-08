
open System
open System.Runtime.InteropServices

open PortAudioSharp
open BeesLib.DebugGlobals


open System.Threading
open System.Threading.Tasks

open BeesLib.CbMessagePool



//–––––––––––––––––––––––––––––––––––––––––––––––––––

let dummyInstance<'T>() =
  System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(typeof<'T>)
  |> unbox<'T>

let delayMs print ms =
  if print then Console.Write $"\nDelay %d{ms}ms. {{"
  (Task.Delay ms).Wait()
  if print then Console.Write "}"

let awaitForever() = delayMs false Int32.MaxValue

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let paTryCatch f (exit: Exception -> unit) =
  try
    f()
  with
  | :? PortAudioException as ex -> 
    Console.WriteLine $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    exit  ex
    raise ex
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    exit  ex
    raise ex

let paTryCatchRethrow f = paTryCatch f (fun e -> ()                 )

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type CallbackHandoff = {
  F            : unit -> unit
  Semaphore    : SemaphoreSlim
  Cts          : CancellationTokenSource
  mutable Task : Task option } with
 
  static member New f = {
    F         = f
    Semaphore = new SemaphoreSlim(0)
    Cts       = new CancellationTokenSource()
    Task      = None }

  member private ch.doHandoffs() =
    let loop() = 
      while not ch.Cts.Token.IsCancellationRequested do
        ch.Semaphore.WaitAsync().Wait()
        ch.F()
      ch.Semaphore.Dispose()
      ch.Cts      .Dispose()
      ch.Task <- None
    match ch.Task with
    | Some _ -> ()
    | None   -> ch.Task <- Some (Task.Run loop)

  member ch.Start   () = ch.doHandoffs()
  member ch.Stop    () = ch.Cts.Cancel()
  member ch.HandOff () = ch.Semaphore.Release() |> ignore

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// Not a struct becuase it persists across calls to callback.
type CbState = {
  // callback args
  mutable Input           : IntPtr
  mutable Output          : IntPtr
  mutable FrameCount      : uint32
  mutable TimeInfo        : PortAudioSharp.StreamCallbackTimeInfo
  mutable StatusFlags     : PortAudioSharp.StreamCallbackFlags
  // callback result
  mutable SegCur          : Seg
  mutable SegOld          : Seg
  mutable SeqNum          : uint64
  mutable InputRingCopy   : IntPtr // where input was copied to
  mutable TimeStamp       : DateTime
  // more stuff
  mutable IsInCallback    : bool
  mutable NRingFrames     : int
  mutable NGapFrames      : int
  mutable CallbackHandoff : CallbackHandoff
  mutable WithEcho        : bool
  mutable WithLogging     : bool
  TimeInfoBase            : DateTime // for getting UTC from timeInfo.inputBufferAdcTime
  FrameSize               : int
  RingPtr                 : IntPtr
  DebugSimulating         : bool } with
    
  member this.SegOldest = if this.SegOld.Active then this.SegOld else this.SegCur


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Copy data from the audio driver into our ring.

let callback input output frameCount (timeInfo: StreamCallbackTimeInfo byref) statusFlags userDataPtr =
  let (input : IntPtr) = input
  let (output: IntPtr) = output
  let handle = GCHandle.FromIntPtr(userDataPtr)
  let cbs = handle.Target :?> CbState
  Console.Write "."
  Volatile.Write(&cbs.IsInCallback, true)
  let nFrames = int frameCount
  
  cbs.Input        <- input
  cbs.Output       <- output
  cbs.FrameCount   <- frameCount // in the ”block“ to be copied
  cbs.TimeInfo     <- timeInfo
  cbs.StatusFlags  <- statusFlags
  cbs.SeqNum       <- cbs.SeqNum + 1UL

  if cbs.WithEcho then
    let size = uint64 (frameCount * uint32 cbs.FrameSize)
    Buffer.MemoryCopy(input.ToPointer(), output.ToPointer(), size, size)

  let printCurAndOld msg =
    if not cbs.DebugSimulating then () else 
    let sCur = cbs.SegCur.Print "cur"
    let sOld = cbs.SegOld.Print "old"
    Console.WriteLine $"%s{sCur} %s{sOld} %s{msg}"
  let prepSegs() =
    // state is Empty, AtBegin, Moving, AtEnd, Chasing
    printCurAndOld ""
    let nextHead = cbs.SegCur.Head + nFrames
    if nextHead <= cbs.NRingFrames then
      // state is not AtEnd
      // state is Empty, AtBegin, Moving, Chasing
      // The block will fit after SegCur.Head
      do // maybe trim SegCur.Tail
        let nUsableFrames = cbs.NRingFrames - cbs.NGapFrames
        cbs.SegCur.Tail <- max cbs.SegCur.Tail (nextHead - nUsableFrames)
        // state is unchanged
      do // maybe trim SegOld.Tail
        if cbs.SegOld.Active then
          // state is Chasing
          // SegOld is active and ahead of SegCur.
          assert (cbs.SegCur.Head < cbs.SegOld.Tail)
          // Trim nFrames from the SegOld.Tail or if SegOld is too small, make it inactive.
          if cbs.SegOld.NFrames > nFrames then
            cbs.SegOld.Tail <- cbs.SegOld.Tail + nFrames
            // state is Chasing
          else
            cbs.SegOld.Reset()
            // state is AtBegin
        // state is AtBegin, Chasing
    else
      // state is AtEnd
      // The block will not fit after SegCur.Head.
      let exchangeSegs() =
        assert not cbs.SegOld.Active
        let tmp = cbs.SegCur  in  cbs.SegCur <- cbs.SegOld  ;  cbs.SegOld <- tmp
        // if SegCur.Head <> 0 then  Console.WriteLine "head != 0"
        // assert (SegCur.Head = 0)
        cbs.SegCur.TimeHead <- tbdDateTime
      exchangeSegs()
      printCurAndOld "exchanged"
      assert (cbs.SegCur.Head = 0)
      // SegCur starts fresh with head = 0, tail = 0.
      // Trim away SegOld.Tail to ensure the gap.
      cbs.SegOld.Tail <- nFrames + cbs.NGapFrames
      // state is Chasing
 
  prepSegs() // may update SegCur.Head, used by copyToRing()
  // At this point state cannot be AtEnd.
  // Below, after the block is appended to SegCur, the state can be AtEnd.
//cbs.Logger.Add cbs.SeqNum cbs.TimeStamp "cb bufs=" ""
  do
    // Copy the block to the ring.
    // Copy from callback data to the head of the ring and return a pointer to the copy.
    let indexToVoidptr index  : voidptr =
      let indexByteOffset = index * cbs.FrameSize
      let intPtr = cbs.RingPtr + (IntPtr indexByteOffset)
      intPtr.ToPointer()
    let srcPtr = input.ToPointer()
    let dstPtr = indexToVoidptr cbs.SegCur.Head
    let size   = int64 (nFrames * cbs.FrameSize)
    Buffer.MemoryCopy(srcPtr, dstPtr, size, size)
    cbs.InputRingCopy <- IntPtr dstPtr
    let timeHead = cbs.TimeInfoBase + TimeSpan.FromSeconds timeInfo.inputBufferAdcTime
    cbs.SegCur.AdvanceHead nFrames timeHead
  cbs.CallbackHandoff.HandOff()
  Volatile.Write(&cbs.IsInCallback, false)
  PortAudioSharp.StreamCallbackResult.Continue


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream

// initPortAudio() must be called before this constructor.
type InputStream( sampleRate       : int              ,
                  frameSize        : int              ,
                  inputParameters  : StreamParameters ,
                  outputParameters : StreamParameters ) =

  let nRingFrames       = 37
  let nGapFrames        = 4
  let nRingBytes        = int nRingFrames * frameSize
  let startTime         = DateTime.UtcNow

  let cbState = {
    // callback args  
    Input           = IntPtr.Zero
    Output          = IntPtr.Zero
    FrameCount      = 0u
    TimeInfo        = PortAudioSharp.StreamCallbackTimeInfo()
    StatusFlags     = PortAudioSharp.StreamCallbackFlags()
    // callback result
    SegCur          = Seg.NewEmpty nRingFrames sampleRate
    SegOld          = Seg.NewEmpty nRingFrames sampleRate
    SeqNum          = 0UL
    InputRingCopy   = IntPtr.Zero
    TimeStamp       = DateTime.MaxValue // placeholder
    // more stuff
    IsInCallback    = false
    NRingFrames     = nRingFrames
    NGapFrames      = nGapFrames
    CallbackHandoff = dummyInstance<CallbackHandoff>()  // tbd
    WithEcho        = false
    WithLogging     = false
    TimeInfoBase    = startTime  // timeInfoBase + adcInputTime -> cbState.TimeStamp
    FrameSize       = frameSize
    RingPtr         = Marshal.AllocHGlobal(nRingBytes)
//  Logger          = Logger(8000, startTime)
    DebugSimulating = simulatingCallbacks  }

  let callbackStub = PortAudioSharp.Stream.Callback(
    // The intermediate lambda here is required to avoid a compiler error.
    fun        input output frameCount  timeInfo statusFlags userDataPtr ->
      callback input output frameCount &timeInfo statusFlags userDataPtr )
  let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                        outParams       = Nullable<_>(outputParameters)        ,
                                                                        sampleRate      = sampleRate                           ,
                                                                        framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                        streamFlags     = StreamFlags.ClipOff                  ,
                                                                        callback        = callbackStub                         ,
                                                                        userData        = cbState                              ) )
  
  member val CbState  = cbState 
  member val PaStream = paStream
  
  member this.Start() =
    this.CbState.CallbackHandoff <- CallbackHandoff.New this.AfterCallback
    this.CbState.CallbackHandoff.Start()
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Start() )
  
  member this.Stop () =
    this.CbState.CallbackHandoff.Stop ()
    if this.CbState.DebugSimulating then ()
    else
    paTryCatchRethrow(fun() -> this.PaStream.Stop () )

  member this.Callback(input, output, frameCount, timeInfo: StreamCallbackTimeInfo byref, statusFlags, userDataPtr) =
              callback input  output  frameCount &timeInfo                                statusFlags  userDataPtr

  member this.AfterCallback() =
    Console.Write ","

  
  interface IDisposable with
    member this.Dispose() =
      System.Console.WriteLine("Disposing inputStream")
      this.PaStream.Dispose()

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

PortAudio.LoadNativeLibrary()
PortAudio.Initialize()

/// Creates and returns the sample rate and the input parameters.
let prepareArgumentsForStreamCreation verbose =
  let log string = if verbose then  printfn string else  ()
  let defaultInput = PortAudio.DefaultInputDevice         in log $"Default input device = %d{defaultInput}"
  let inputInfo    = PortAudio.GetDeviceInfo defaultInput
  let nChannels    = inputInfo.maxInputChannels           in log $"Number of channels = %d{nChannels}"
  let sampleRate   = int inputInfo.defaultSampleRate      in log $"Sample rate = %d{sampleRate} (default)"
  let sampleFormat = SampleFormat  .Float32
  let sampleSize   = sizeof<float32>
  let inputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultInput                      ,
    channelCount              = nChannels                         ,
    sampleFormat              = sampleFormat                      ,
    suggestedLatency          = inputInfo.defaultHighInputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                       )
  log $"%s{inputInfo.ToString()}"
  log $"inputParameters=%A{inputParameters}"
  let defaultOutput = PortAudio .DefaultOutputDevice      in log $"Default output device = %d{defaultOutput}"
  let outputInfo    = PortAudio .GetDeviceInfo defaultOutput
  let outputParameters = PortAudioSharp.StreamParameters(
    device                    = defaultOutput                       ,
    channelCount              = nChannels                           ,
    sampleFormat              = sampleFormat                        ,
    suggestedLatency          = outputInfo.defaultHighOutputLatency ,
    hostApiSpecificStreamInfo = IntPtr.Zero                         )
  log $"%s{outputInfo.ToString()}"
  log $"outputParameters=%A{outputParameters}"
  let frameSize = sampleSize * nChannels
  sampleRate, frameSize, inputParameters, outputParameters

let showGC f =
  // System.GC.Collect()
  // let starting = GC.GetTotalMemory(true)
  f()
  // let m = GC.GetTotalMemory(true) - starting
  // Console.WriteLine $"gc memory: %i{ m }";

let getArrayPointer byteCount =
  let inputArray = Array.create byteCount (float 0.0)
  let handle = GCHandle.Alloc(inputArray, GCHandleType.Pinned)
  handle.AddrOfPinnedObject()

//–––––––––––––––––––––––––––––––––––––
// Main

let test inputStream frameSize =
  let (inputStream: InputStream) = inputStream
  printfn "calling callback ...\n"
  let frameCount = 4
  let byteCount = frameCount * frameSize
  let input  = getArrayPointer byteCount
  let output = getArrayPointer byteCount
  let mutable timeInfo    = PortAudioSharp.StreamCallbackTimeInfo()
  let statusFlags = PortAudioSharp.StreamCallbackFlags()
  let userDataPtr = GCHandle.ToIntPtr(GCHandle.Alloc(inputStream.CbState))
  for i in 1..40 do
    let fc = if i < 20 then  frameCount else  2 * frameCount
    let m = showGC (fun () -> 
      timeInfo.inputBufferAdcTime <- 0.001 * float i
      inputStream.Callback(input, output, uint32 fc, &timeInfo, statusFlags, userDataPtr) |> ignore 
      delayMs false 1
      Console.WriteLine $"{i}" )
    delayMs false 1
  printfn "\n\ncalling callback done"

let Quiet   = false
let Verbose = true

[<EntryPoint>]
let main _ =
  let sampleRate, frameSize, inputParameters, outputParameters = prepareArgumentsForStreamCreation Quiet
  simulatingCallbacks <- true
  use iS = new InputStream(sampleRate, frameSize, inputParameters, outputParameters)
  GC.Collect()
  try
    iS.Start()
    if simulatingCallbacks then
      test iS frameSize
    else
      printfn "Reading..."
      printfn "Begin"
      awaitForever()
      printfn "Done"
      printfn "Stopping..."
      iS.Stop() 
      printfn "Stopped"
    printfn "Terminating..."
    PortAudio.Terminate()
    printfn "Terminated"
  with
  | :? PortAudioException as e ->
      printfn "While creating the stream: %A %A" e.ErrorCode e.Message
      Environment.Exit(2)
  
  GC.Collect()
  printfn "inputStream: %A" iS
  0