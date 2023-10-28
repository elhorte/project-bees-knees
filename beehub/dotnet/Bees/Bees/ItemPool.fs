module Bees.ItemPool


open System.Collections.Concurrent
open CpuStopwatch

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// A pool of items that can be taken from the pool without risk of a GC.

[<AbstractClass>]
type IPoolItem() =
  abstract SeqNum : int with get, set


type ItemPool<'Item when 'Item :> IPoolItem>(startCount: int, minCount: int, creator: unit -> 'Item) =

  let pool = ConcurrentBag<'Item>()
  // debugging:
  let mutable countAvail = 0
  let mutable countInUse = 0

  let changeCount n = countAvail <- countAvail + n
  let changeInUse n = countInUse <- countInUse + n

  let poolAdd item =
    pool.Add item
    changeCount +1
    changeInUse -1
    assert (countAvail = pool.Count)

  let mutable seqNum = -1  // ok to be overwritten when item is used

  let addNewItem() =
    let item = creator()
    item.SeqNum <- seqNum ; seqNum <- seqNum - 1
    poolAdd item

  do
    assert pool.IsEmpty
    assert (countAvail = 0)
    let n = max minCount startCount
    do
      if n > 0 then  for i in 1..n do  addNewItem() // Stock the pool.
      countInUse = 0  // Zero out the changes to countInUse in poolAdd.
    assert (countAvail = startCount)

  
  let take() =
    let ok, obj = pool.TryTake()
    if ok then
      changeCount -1
      changeInUse +1
      assert (countAvail = pool.Count)
      Some obj
    else
      None

  // Ensure the pool has at least lowWaterMark Bufs.
  let addItemsIfNeeded() = while countAvail < minCount do  addNewItem()

  let giveBack item =
    poolAdd item


  member this.Take()           = take()
  member this.ItemUseBegin()   = addItemsIfNeeded()
  member this.ItemUseEnd item  = poolAdd item //; printfn "released"
  member this.CountAvail       = countAvail
  member this.CountInUse       = countInUse


  member this.Test() =
    let busies = ResizeArray<'Item>()
    let rec takeWhileOk n =
      match this.Take() with
      | Some item -> busies.Add item
                     this.ItemUseBegin()
                     if n > 1 then takeWhileOk (n - 1) 
      | None   -> printf "None available"
    takeWhileOk startCount
    for item in busies
      do this.ItemUseEnd item
    busies.Clear()
    printfn "pool count: %d" this.CountAvail


// type TestItem() =
//   inherit IPoolItem()
//   let mutable num = 0
//   override this.seqNum
//     with get() = num
//     and set(value) = num <- value
//   member this.ToString() = sprintf "TestItem %d ha" this.seqNum
//
// do
//   let startCount = 10
//   let minCount   = 2
//   let pool = ItemPool<TestItem>(startCount, minCount, fun () -> new TestItem())
//   pool.Test()
