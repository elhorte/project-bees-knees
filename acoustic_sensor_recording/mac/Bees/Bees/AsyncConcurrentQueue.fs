module Bees.AsyncConcurrentQueue

open System.Collections.Concurrent
open FSharp.Control

/// A thread-safe queue with nonlocking, nonallocating Put() and TakeAsync() methods
type AsyncConcurrentQueue<'T> () =

  let queue = ConcurrentQueue<'T>()
  let signal = new System.Threading.SemaphoreSlim(0)

  /// <summary>
  /// Adds an object to the end of the ConcurrentQueue.
  /// No allocation or locking is done.
  /// </summary>
  member this.add(item: 'T) =
    queue.Enqueue(item)
    signal.Release() |> ignore

  member this.get() = async {
    let! _ = Async.AwaitTask(signal.WaitAsync())
    let success, item = queue.TryDequeue()
    if success then return item
    else return failwith "Couldn't dequeue item from queue." }

  member this.getAsyncSeq() = 
    AsyncSeq.initInfiniteAsync (fun _ -> this.get())

  /// <summary>
  /// Calls f on each item as it becomes available from the queue
  /// </summary>
  member this.iter f =
    this.getAsyncSeq()
    |> AsyncSeq.iter f
    |> Async.Start

  member this.print() = this.iter  (fun item -> printfn "%A" item)
