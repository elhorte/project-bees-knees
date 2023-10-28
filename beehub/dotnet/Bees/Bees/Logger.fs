module Bees.Logger

open System
open System.Text

type LogEntry(seqNum: int, timestamp: DateTime, message: string, data: obj) =
  new() = LogEntry(0, DateTime.MinValue, "", null)
  member val seqNum    : int      = seqNum      with get, set
  member val Timestamp : DateTime = timestamp   with get, set
  member val Message   : string   = message     with get, set
  member val Data      : obj      = data        with get, set

/// An in-memory logger accepting a fixed number of entries.
/// Has a start time and a preallocated number of entries,
/// which are modified in place.
/// 
type Logger (capacity: int, startTime: DateTime) =
  let entryBuf = Array.init<LogEntry> capacity (fun _ -> LogEntry())
  let mutable count = 0
  let mutable entries = ArraySegment<LogEntry>(entryBuf, 0, 0)

  member this.Entries  with get() = entries

  member this.Add seqNum (timestamp: DateTime) (message: string) (data: obj) =
    if count < capacity then
      let entry = entryBuf[count]
      entry.seqNum    <- seqNum
      entry.Timestamp <- timestamp
      entry.Message   <- message
      entry.Data      <- data
      count <- count + 1
      entries <- ArraySegment<LogEntry>(entryBuf, 0, count)

  member this.Clear() = count <- 0
    
  member this.EntryToString elapsedPrev (entry: LogEntry) = 
    let elapsed = entry.Timestamp - startTime
    String.Format("{0:D3}: {1}  {2}  {3} {4}\n",
                  entry.seqNum                                     ,
                  elapsed                .ToString("ss'.'ffffff") ,
                  (elapsed - elapsedPrev).ToString(  "'.'ffffff") ,
                  entry.Message                                   ,
                  entry.Data)

  override this.ToString() =
    let sb = StringBuilder()
    let print elapsedPrev (entry: LogEntry) =
      let elapsed = entry.Timestamp - startTime
      sb.Append (this.EntryToString elapsedPrev entry) |> ignore
      elapsed
    if entries.Count > 0 then
      printfn "\nLog:"
      entries
      |> Seq.fold print TimeSpan.Zero |> ignore
    printfn ""
    sb.AppendFormat("Log entries: {0}\n", count) |> ignore
    sb.ToString()
