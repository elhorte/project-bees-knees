module BeesLib.RingBuffer

open System
open System.Runtime.CompilerServices
open System.Runtime.InteropServices
open System.Threading.Tasks
open BeesLib.AsyncConcurrentQueue
open BeesLib.BeesConfig
open BeesLib.CbMessagePool
open Microsoft.FSharp.NativeInterop


  
type RingBuffer(beesConfig: BeesConfig, cbMessageQueue: CbMessageQueue) =

  let frameSize = beesConfig.InChannelCount * sizeof<BufType>
  let nFrames   = beesConfig.RingBufferDuration.Seconds * beesConfig.InSampleRate
  let nBytes    = int nFrames * frameSize
  let ringPtr   = Marshal.AllocHGlobal(nBytes).ToPointer()
//let ringPtr   = Unsafe.AsRef<byte>(ringPtr)
  let mutable nextIndex = 0
  let mutable highWater = 0

  let advanceIndex nBytes =
    let indexNew = nextIndex + nBytes
    let excess = indexNew - nBytes
    nextIndex <- if excess < 0 then  nextIndex + int nBytes else  0

  let mutable ringPtr : nativeptr<float32> = 0
  let ringPtr = Marshal.AllocHGlobal(nBytes) |> NativePtr.ofNativeInt

  let pointerToNextInput nextIndex: nativeptr<float32> = ringPtr + (nextIndex * sizeof<float32>)

  let ringPtr = Marshal.AllocHGlobal(nBytes).ToPointer()
  let pointerToNextInput nextIndex  : System.IntPtr =
    &ringPtr[nextIndex] 

  let writeBlock (block: nativeint) nFrames =
    let room = nFrames - nextIndex
    if nFrames > room then
      highWater <- nextIndex
      nextIndex <- 0
    let toPtr = pointerToNextInput nextIndex
    Marshal.Copy(toPtr, block, startIndex = 0, length = (int nFrames))
    
    toPtr

  member this.WriteBlock(block: IntPtr, nFrames: int) =
    writeBlock block nFrames

  // let mutable bufBegin = DateTime.Now
  // let mutable earliest = DateTime.Now
  
  // let handleCallback inputCallback =
  //   let cbMessage = inputCallback.CbMessage
  //   let (BufRef bufArrayRef) = cbMessage.InputSamplesCopyRef
  //   let from = !bufArrayRef
  //   let size = int cbMessage.FrameCount 
  //   System.Buffer.BlockCopy(from, 0, buffer, index, size)
  //   advanceIndex size
  //   inputCallback.CompletionSource.SetResult()
  //
  // let handleTake inputTake =
  //   ()
  //   // let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
  //   // let size = frameCountToByteCount inputTake.FrameCount 
  //   // System.Buffer.BlockCopy(from, 0, buffer, index, size)
  //   // advanceIndex inputTake.FrameCount
  //   // inputTake.CompletionSource.SetResult()
  //
  // // Method to process jobQueue items
  // let rec processQueue() = task {
  //   let! job = jobQueue.DequeueAsync()
  //   match job with
  //   | Callback x ->  handleCallback x
  //   | Take     x ->  handleTake     x
  //   return! processQueue() }
  //
  // // Submit a job
  // let doCallback cbMessage _ _ =
  //   let callbackJob = {
  //     CbMessage        = cbMessage
  //     CompletionSource = TaskCompletionSource<unit>() }
  //   jobQueue.Enqueue(Callback callbackJob)
  //
  // do
  //   cbMessageWorkList.Subscribe(doCallback)
  //   Task.Run<unit> (fun () -> task { do! processQueue() }) |> ignore
  //
  //
  // let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
  //   let now = DateTime.Now
  //   let beginDt =
  //     if   dateTime > now      then  now
  //     elif dateTime < earliest then  earliest
  //                              else  dateTime
  //   ()
  //   
  // let keep (duration: TimeSpan) =
  //   assert (duration > TimeSpan.Zero)
  //   let now = DateTime.Now
  //   let dateTime = now - duration
  //   earliest <- 
  //     if dateTime < earliest then  earliest
  //                            else  dateTime
  //   earliest
  //   
  // /// Reach back as close as possible to a time in the past.
  // member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
  //   get dateTime duration worker
  //
  // /// Keep as much as possible of the given TimeSpan
  // /// and return the start DateTime of what is currently kept.
  // member this.Keep(duration: TimeSpan)  : DateTime = keep duration
  //
  // // Method to submit a job
  // member this.Callback(cbMessage: CbMessage, workId: WorkId, unsubscribeMe: Unsubscriber) =
  //   doCallback cbMessage workId unsubscribeMe
