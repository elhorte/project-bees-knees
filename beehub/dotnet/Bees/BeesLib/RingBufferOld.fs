module BeesLib.RingBufferOld

// open System
// open System.Collections.Concurrent
// open System.Threading.Tasks
// open BeesLib.AsyncConcurrentQueue
// open BeesLib.CbMessagePool
// open BeesLib.CbMessageWorkList
//
// type Worker = Buf -> int -> int
//
//
// type TakeFunctions =
//   | TakeWrite of (BufRef -> int -> unit)
//   | TakeDone  of (int -> unit)
//
// type CallbackJob = {
//   CbMessage        : CbMessage
//   CompletionSource : TaskCompletionSource<unit> }
//
// type TakeJob = {
//   Data: TakeFunctions
//   CompletionSource: TaskCompletionSource<unit> }
//
// type Job =
//   | Callback of CallbackJob
//   | Take     of TakeJob
//   
// type RingBufferOld( beesConfig        : BeesConfig        ,
//                  cbMessageWorkList : CbMessageWorkList ) =
//
//   let jobQueue = AsyncConcurrentQueue<Job>()
//   
//   let mutable bufBegin = DateTime.Now
//   let mutable earliest = DateTime.Now
//   let mutable index    = 0
//   let duration = beesConfig.ringBufferDuration
//   let nSamples = beesConfig.ringBufferDuration.Seconds * beesConfig.inSampleRate * beesConfig.nChannels
//   let nBytes = frameCountToByteCount nSamples
//   let buffer = Array.init nSamples (fun _ -> float32 0.0f)
//
//   let advanceIndex count =
//     let indexNew = index + count
//     let excess = indexNew - nBytes
//     index <- if excess < 0 then  index + int count else  0
//   
//   let handleCallback inputCallback =
//     let cbMessage = inputCallback.CbMessage
//     let (BufRef bufArrayRef) = cbMessage.InputSamplesCopyRef
//     let from = !bufArrayRef
//     let size = int cbMessage.FrameCount 
//     System.Buffer.BlockCopy(from, 0, buffer, index, size)
//     advanceIndex size
//     inputCallback.CompletionSource.SetResult()
//   
//   let handleTake inputTake =
//     ()
//     // let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
//     // let size = frameCountToByteCount inputTake.FrameCount 
//     // System.Buffer.BlockCopy(from, 0, buffer, index, size)
//     // advanceIndex inputTake.FrameCount
//     // inputTake.CompletionSource.SetResult()
//   
//   // Method to process jobQueue items
//   let rec processQueue() = task {
//     let! job = jobQueue.DequeueAsync()
//     match job with
//     | Callback x ->  handleCallback x
//     | Take     x ->  handleTake     x
//     return! processQueue() }
//
//   // Submit a job
//   let doCallback cbMessage _ _ =
//     let callbackJob = {
//       CbMessage        = cbMessage
//       CompletionSource = TaskCompletionSource<unit>() }
//     jobQueue.Enqueue(Callback callbackJob)
//
//   do
//     cbMessageWorkList.Subscribe(doCallback)
//     Task.Run<unit> (fun () -> task { do! processQueue() }) |> ignore
//
//   
//   let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
//     let now = DateTime.Now
//     let beginDt =
//       if   dateTime > now      then  now
//       elif dateTime < earliest then  earliest
//                                else  dateTime
//     ()
//     
//   let keep (duration: TimeSpan) =
//     assert (duration > TimeSpan.Zero)
//     let now = DateTime.Now
//     let dateTime = now - duration
//     earliest <- 
//       if dateTime < earliest then  earliest
//                              else  dateTime
//     earliest
//     
//   /// Reach back as close as possible to a time in the past.
//   member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
//     get dateTime duration worker
//
//   /// Keep as much as possible of the given TimeSpan
//   /// and return the start DateTime of what is currently kept.
//   member this.Keep(duration: TimeSpan)  : DateTime = keep duration
//
//   // Method to submit a job
//   member this.Callback(cbMessage: CbMessage, workId: WorkId, unsubscribeMe: Unsubscriber) =
//     doCallback cbMessage workId unsubscribeMe
