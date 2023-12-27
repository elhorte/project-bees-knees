module BeesLib.AsyncConcurrentQueue

open System.Collections.Concurrent
open FSharp.Control

/// Like ConcurrentQueue but with DequeueAsync() method.
type AsyncConcurrentQueue<'T> () =

  let queue = ConcurrentQueue<'T>()
  let signal = new System.Threading.SemaphoreSlim(0)

  /// <summary>
  /// Adds an object to the end of the ConcurrentQueue.
  /// No allocation or locking is done.
  /// </summary>
  member this.Enqueue(item: 'T) =
    queue.Enqueue(item)
    signal.Release() |> ignore

  member this.DequeueAsync() = async {
    do! Async.AwaitTask(signal.WaitAsync())
    let success, item = queue.TryDequeue()
    if success then return item
    else return failwith "Couldn't take item from queue." }

  member this.GetAsyncSeq() = 
    AsyncSeq.initInfiniteAsync (fun _ -> this.DequeueAsync())

  /// <summary>
  /// Calls f on each item as it becomes available from the queue
  /// </summary>
  member this.iter f =
    this.GetAsyncSeq()
    |> AsyncSeq.iter f
    |> Async.Start

  member this.print() = this.iter  (fun item -> printfn "%A" item)
