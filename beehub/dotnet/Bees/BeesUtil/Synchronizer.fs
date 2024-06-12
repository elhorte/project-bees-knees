module BeesUtil.Synchronizer

open System
open System.Threading


type SynchronizerResult<'T> =
  | Stable   of 'T
  | TimedOut of string

type SynchronizerResultInternal<'T> =
  | OK_       of 'T
  | TimedOut_ of string
  | Trying

let synchronizerInitValue = uint16 -1

/// Reader–writer synchronization for a single writer using a variant of a seqlock.
type Synchronizer = {
  mutable S : uint32 }  // two int16 sequence numbers, written as a pair atomically
with

  static member New() = Synchronizer.Make synchronizerInitValue synchronizerInitValue

  /// Enters the critical section on behalf of a writer.
  member sn.EnterUnstable() =  let n1, n2 =  sn.GetPair() in sn.Set (n1 + 1us)  n2

  /// Leaves the critical section on behalf of a writer
  member sn.LeaveUnstable() =  let n1, n2 =  sn.GetPair() in sn.Set  n1        (n2 + 1us)

  member sn.NeverEntered = sn.N1 = synchronizerInitValue
    
  /// Calls a function on behalf of a reader one or more times until the last time,
  /// which is guaranteed to be while stable, i.e., not during the critical section.
  member sn.WhenStable                timeout (f: unit -> 'T)                        : SynchronizerResult<'T> =
         sn.WhenStableInternal false  timeout  f              Int32.MaxValue ignore

  /// Calls a function on behalf of a reader one or more times until the last time,
  /// which is guaranteed to be while stable, i.e., not during the critical section;
  /// also delays until the critical section has been entered at least once.
  member sn.WhenStableAndEntered      timeout (f: unit -> 'T)                        : SynchronizerResult<'T> =
         sn.WhenStableInternal true   timeout  f              Int32.MaxValue ignore

  /// Get the sequence number incremented when entering the critical section.
  member sn.N1 =  sn.Get()        |> uint16
  /// Get the sequence number incremented when leaving the critical section.
  member sn.N2 =  sn.Get() >>> 16 |> uint16

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Internals

  static member Make n1 n2 =  { S = (uint32 n2 <<< 16) ||| uint32 n1 }
  member sn.Set (n1: uint16) (n2: uint16) =  Volatile.Write(&sn.S, (Synchronizer.Make n1 n2).S)
  member sn.Get()                         =  Volatile.Read  &sn.S
  member sn.GetPair() =  let n2n1 =  sn.Get() in  uint16 n2n1, uint16 (n2n1 >>> 16)

  member sn.IsStable()  : bool * uint16 =
    let n1, n2 =  sn.GetPair()
    if n1 = n2 then  true , n2
               else  false, uint16 -1 // value ignored

  member sn.WhenStableInternal needEntered timeout (f: unit -> 'T) maxTries print  : SynchronizerResult<'T> =
    let mutable result =  Trying
    let mutable nTries =  0
    let startTime =  DateTime.Now
    let tryAgain message =
      let noGo =  maxTries > 0 && nTries >= maxTries  ||  maxTries = 0 && DateTime.Now - startTime >= timeout
      if noGo then  result <- TimedOut_ message
              else  nTries <- nTries + 1
                    print $"Trying again %s{message}"
    let trying() =  match result with Trying -> true | _ -> false 
    while trying() do
      let notReady = needEntered && sn.NeverEntered
      match sn.IsStable() with
      | false, _                 ->  tryAgain "while unstable"
      | true , _ when notReady   ->  tryAgain "while never entered"
      | true , n2 ->
      let funResult =  f()
      match sn.GetPair() with
      | nn1, _   when nn1 <> n2  ->  tryAgain "while working"
      | nn1, nn2 when nn1 <> nn2 ->  failwith "SeqSums: N1 ok but N2 changed while running the function"
      | _ ->
      result <- OK_ funResult
    match result with
    | OK_       x -> Stable x
    | TimedOut_ s -> TimedOut s
    | Trying      -> failwith "Can’t return Trying result"

