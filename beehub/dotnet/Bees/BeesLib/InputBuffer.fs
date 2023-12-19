module BeesLib.InputBuffer

open System
open System.Collections.Concurrent
open System.Threading.Tasks
open BeesLib.AsyncConcurrentQueue
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList

type Worker = Buf -> int -> int


type TakeFunctions =
  | TakeWrite of (BufRef -> int -> unit)
  | TakeDone  of (int -> unit)

type InputCallback = {
    FromRef          : BufRef
    FrameCount       : uint32
    CompletionSource : TaskCompletionSource<unit> }

type InputTake = {
    Data: TakeFunctions
    CompletionSource: TaskCompletionSource<unit> }

type Request =
  | Callback of InputCallback
  | Take     of InputTake
  
type InputBuffer(config: Config, timeSpan: TimeSpan, source: CbMessageWorkList) =

  let queue = AsyncConcurrentQueue<Request>()
  
  let mutable bufBegin = DateTime.Now
  let mutable earliest = DateTime.Now
  let mutable index    = 0
  let duration = config.bufferDuration
  let nSamples = config.bufferDuration.Seconds * config.inSampleRate * config.nChannels
  let nBytes = frameCountToByteCount nSamples
  let buffer = Array.init nSamples (fun _ -> float32 0.0f)

  let advanceIndex count =
    let indexNew = index + int count
    let excess = indexNew - nBytes
    index <- if excess < 0 then  index + int count else  0
  
  let callback inputCallback =
    let from = match inputCallback.FromRef with BufRef arrRef -> !arrRef
    let size = frameCountToByteCount inputCallback.FrameCount 
    System.Buffer.BlockCopy(from, 0, buffer, index, size)
    advanceIndex inputCallback.FrameCount
    inputCallback.CompletionSource.SetResult()
  
  let take inputTake =
    let from = match inputTake.FromRef with BufRef arrRef -> !arrRef
    let size = frameCountToByteCount inputTake.FrameCount 
    System.Buffer.BlockCopy(from, 0, buffer, index, size)
    advanceIndex inputTake.FrameCount
    inputTake.CompletionSource.SetResult()

  let doRequest request =
    match request with
    | Callback x ->  callback x
    | Take x     ->  take x
  
  // Method to process queue items
  let rec processQueue() = async {
    let! request = queue.DequeueAsync()
    doRequest request
    return! processQueue()
  }
    
  do
    source.Subscribe(callback)
    do Async.StartImmediate(processQueue())

  let get (dateTime: DateTime) (duration: TimeSpan) (worker: Worker) =
    let now = DateTime.Now
    let beginDt =
      if   dateTime > now      then  now
      elif dateTime < earliest then  earliest
                               else  dateTime
    ()
    
  let keep (duration: TimeSpan) =
    assert (duration > TimeSpan.Zero)
    let now = DateTime.Now
    let dateTime = now - duration
    earliest <- 
      if dateTime < earliest then  earliest
                             else  dateTime
    earliest
    
  /// Reach back as close as possible to a time in the past.
  member this.Get(dateTime: DateTime, duration: TimeSpan, worker: Worker)  : unit =
    get dateTime duration worker

  /// Keep as much as possible of the given TimeSpan
  /// and return the start DateTime of what is currently kept.
  member this.Keep(duration: TimeSpan)  : DateTime = keep duration

  // Method to submit a job
  member this.Callback(cbMessage: CbMessage, workId: WorkId, unsubscribeMe: Unsubscriber) =
    let inputCallback = {
      FromRef          = cbMessage.InputSamplesCopyRef
      FrameCount       = cbMessage.FrameCount
      CompletionSource = TaskCompletionSource<unit>() }
    let request = Callback inputCallback
    queue.Enqueue(request)
    TaskCompletionSource<unit>().Task

  // Method to submit a job
  member this.PostPrint(data: string) =
    let completionSource = TaskCompletionSource<unit>()
    let request = Print { Data = data; CompletionSource = completionSource }
    queue.Enqueue(request)
    completionSource.Task
