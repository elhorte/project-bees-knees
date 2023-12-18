module BeesLib.InputBuffer

open System
open System.Collections.Concurrent
open System.Threading.Tasks
open BeesLib.AsyncConcurrentQueue
open BeesLib.CbMessagePool
open BeesLib.CbMessageWorkList

type Worker = Buf -> int -> int


type Count = {
    Data: int
    CompletionSource: TaskCompletionSource<int>
}

type Print = {
    Data: string
    CompletionSource: TaskCompletionSource<unit>
}

type Request =
  | Count of Count
  | Print of Print

type InputBuffer(config: Config, timeSpan: TimeSpan, source: CbMessageWorkList) =

  let queue = AsyncConcurrentQueue<Request>()
  let mutable count = 0
  
  let mutable bufBegin = DateTime.Now
  let mutable earliest = DateTime.Now
  let mutable index    = 0
  let duration = config.bufferDuration
  let nSamples = config.bufferDuration.Seconds * config.inSampleRate * config.nChannels
  let size = nSamples * sizeof<float32>
  let buffer = Array.init nSamples (fun _ -> float32 0.0f)

  let doRequest request =
    match request with
    | Count c ->
      count <- count + c.Data
      let result = count
      c.CompletionSource.SetResult(result)
    | Print p ->
      printfn "print %s" p.Data
      p.CompletionSource.SetResult()
  
  // Method to process queue items
  let rec processQueue() = async {
    let! request = queue.DequeueAsync()
    doRequest request
    return! processQueue()
  }

  let advanceIndex count =
    let indexNew = index + int count
    let excess = indexNew - size
    index <- if excess < 0 then  index + int count else  0

  let callback (cbMessage: CbMessage) (workId: WorkId) (unsubscribeMe: Unsubscriber) =
    let from = match cbMessage.InputSamplesCopyRef with BufRef arrRef -> !arrRef
    let size = int cbMessage.FrameCount * sizeof<float32>
    System.Buffer.BlockCopy(from, 0, buffer, index, size)
    advanceIndex cbMessage.FrameCount
    
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
  member this.PostCount(data: int) =
    let completionSource = TaskCompletionSource<int>()
    let request = Count { Data = data; CompletionSource = completionSource }
    queue.Enqueue(request)
    completionSource.Task

  // Method to submit a job
  member this.PostPrint(data: string) =
    let completionSource = TaskCompletionSource<unit>()
    let request = Print { Data = data; CompletionSource = completionSource }
    queue.Enqueue(request)
    completionSource.Task
