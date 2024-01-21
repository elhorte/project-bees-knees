module ConsoleReadAsync.ConcurrentFlag

open System
open System.Threading


type ConcurrentFlag() =

  let semaphore = new SemaphoreSlim(0, 1)
  
  let waitAsync cancellationToken = task {
    try
      let ct = (cancellationToken : CancellationToken)
      do! semaphore.WaitAsync(ct)
      return true
    with _ ->
      return false }
    
  member this.Ready with get() = semaphore.CurrentCount = 0

  member this.MakeReady()      = semaphore.Release() |> ignore
      
  member this.Wait()           = semaphore.Wait()
  member this.WaitAsync()      = semaphore.WaitAsync()
  member this.WaitAsync(cancellationToken: CancellationToken) = waitAsync cancellationToken

  member this.Dispose()        = semaphore.Dispose()
    
  interface IDisposable with
    member this.Dispose() = this.Dispose()
