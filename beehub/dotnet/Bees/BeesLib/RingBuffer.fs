module BeesLib.RingBuffer

open System
open System.Runtime.InteropServices
open System.Threading.Tasks
open BeesLib.AsyncConcurrentQueue
open BeesLib.BeesConfig


type BufType     = float32
type BufArray    = BufType array
type Buf         = Buf    of BufArray
type BufRef      = BufRef of BufArray ref
type BufRefMaker = unit -> BufRef


  
type RingBuffer(beesConfig: BeesConfig) =

  let frameSize = beesConfig.InChannelCount * sizeof<BufType>

  let frameCountToByteCount frameCount =  int frameCount * frameSize

  let nFrames   = beesConfig.RingBufferDuration.Seconds * beesConfig.InSampleRate * frameSize
  let nBytes    = frameCountToByteCount nFrames
  let ring = Marshal.AllocHGlobal(nBytes)
  let ringSpan =
    new Span<byte>(ring.ToPointer(), nBytes)
    |> MemoryMarshal.Cast<byte, float32>

  let mutable nextInput = 0
    
  let advanceIndex nBytes =
    let indexNew = nextInput + nBytes
    let excess = indexNew - nBytes
    nextInput <- if excess < 0 then  nextInput + int nBytes else  0

  let getPtr nFrames =
    let result = ringSpan.Slice(nextInput, sliceLength)
    advanceIndex (frameCountToByteCount nFrames)
    result

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
