module Bees.BufferPool

open System.Collections.Concurrent

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// Buffer pool

type BufType = float32
type Buf     = Buf of BufType array

type BufferPool(capacity: int, lowWaterMark: int) =

  let pool = ConcurrentBag<Buf>()
  // debugging:
  let debugging = false
  let mutable size = 0
  let mutable stamp = 1
  let changeSize n = size <- size + n
  
  let poolAdd buf =
    pool.Add buf
    changeSize 1

  let take() =
    let ok, obj = pool.TryTake()
    if ok then
      changeSize -1
      obj
    else
      failwith "BufferPool: pool is empty"

  let addBufOfSize n =
    let newArray = Array.zeroCreate<BufType> n
    if debugging then newArray[0] <- float32 stamp ; stamp <- stamp + 1
    poolAdd(Buf newArray)

  let addNewBuf() = addBufOfSize 1024

  let rec addBufsIfNeeded() =
    if pool.Count < lowWaterMark then
      addNewBuf()
      addBufsIfNeeded() 

  /// Adds n Bufs to the pool, then remove them all.
  /// This is a workaround for lack of capacity argument
  /// to the ConcurrentBag constructor.
  let rec setPoolCapacity n =
    match n with
    | n when n <= 0 -> ()
    | _ ->
      addBufOfSize 1
      setPoolCapacity (n - 1)
      take() |> ignore

  do
    assert pool.IsEmpty
    setPoolCapacity(capacity)    // ridiculously more than number of cores
    assert pool.IsEmpty
    assert (size = 0)
    for i in 1..lowWaterMark do  addNewBuf()

  member this.Size            = size
  member this.BufUseBegin _   = addBufsIfNeeded()
  member this.Take()          = take()
  member this.BufUseEnd buf   = poolAdd buf //; printfn "released"

  // static member test() =
  //   let capacity = 3
  //   let lowWaterMark = 2
  //   let bufPool = BufferPool(capacity, lowWaterMark)
  //   let bufs = ResizeArray<Buf>(capacity)
  //   for i in 1..capacity do
  //     let buf = bufPool.Take()
  //     bufs.Add buf
  //     bufPool.BufUseBegin buf
  //   for buf in bufs
  //     do bufPool.BufUseEnd buf
