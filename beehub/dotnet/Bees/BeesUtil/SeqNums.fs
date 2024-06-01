module BeesUtil.SeqNums

open System
open System.Threading


type SeqNumsResult<'T> =
  | Stable       of 'T
  | TimedOut of string

type SeqNumsResultInternal<'T> =
  | OK_       of 'T
  | TimedOut_ of string
  | Trying

let seqNumsInitValue = uint16 -1

/// A pair of sequence numbers for producer/consumer synchronization without locking.

type SeqNums = { mutable S : uint32 } with

  static member New() = SeqNums.Make seqNumsInitValue seqNumsInitValue

  /// Enters the critical section on behalf of a producer.
  member sn.EnterUnstable() =  let n1, n2 =  sn.GetPair() in sn.Set (n1 + 1us)  n2

  /// Leaves the critical section on behalf of a producer
  member sn.LeaveUnstable() =  let n1, n2 =  sn.GetPair() in sn.Set  n1        (n2 + 1us)

  member sn.NeverEntered = sn.N1 = seqNumsInitValue
    
  /// Calls a function on behalf of a consumer one or more times until the last time,
  /// which is guaranteed to be while stable, i.e., not in the critical section.
  member sn.WhenStable                timeout (f: unit -> 'T)                        : SeqNumsResult<'T> =
         sn.WhenStableInternal false  timeout  f              Int32.MaxValue ignore
  member sn.WhenStableAndEntered      timeout (f: unit -> 'T)                        : SeqNumsResult<'T> =
         sn.WhenStableInternal true   timeout  f              Int32.MaxValue ignore

  /// Get one or the other sequence number.
  member sn.N1 =  sn.Get()        |> uint16
  member sn.N2 =  sn.Get() >>> 16 |> uint16

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Internals

  static member Make n1 n2 =  { S = (uint32 n2 <<< 16) ||| uint32 n1 }
  member sn.Set (n1: uint16) (n2: uint16) =  Volatile.Write(&sn.S, (SeqNums.Make n1 n2).S)
  member sn.Get()                         =  Volatile.Read  &sn.S
  member sn.GetPair() =  let n2n1 =  sn.Get() in  uint16 n2n1, uint16 (n2n1 >>> 16)

  member sn.IsStable()  : bool * uint16 =
    let n1, n2 =  sn.GetPair()
    if n1 = n2 then  true , n2
               else  false, uint16 -1 // value ignored

  member sn.WhenStableInternal needEntered timeout (f: unit -> 'T) maxTries print  : SeqNumsResult<'T> =
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

