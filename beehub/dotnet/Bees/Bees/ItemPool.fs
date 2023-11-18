module Bees.ItemPool


open System.Collections.Concurrent

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// A pool of items that can be taken from the pool without risk of a GC.

[<AbstractClass>]
type IPoolItem() =
  abstract SeqNum : int with get, set


type ItemPool<'Item when 'Item :> IPoolItem>(startCount: int, minCount: int, creator: unit -> 'Item) =

  let pool          = ConcurrentBag<'Item>()
  let returnedItems = ConcurrentBag<'Item>()
  
  // modified only at interrupt time
  let mutable countAvail = 0
  let mutable countInUse = 0
  let mutable seqNum = -1  // ok to be overwritten when item is used

  
  // Functions called only at interrupt time

  let changeAvail n = countAvail <- countAvail + n
  let changeInUse n = countInUse <- countInUse + n
  
  let addReturnedItems() =
    assert (countAvail = pool.Count)
    let r = returnedItems.Count
    changeAvail +r
    changeInUse -r
    let rec moveEm() =
      let ok, item = returnedItems.TryTake()
      if ok then
        pool.Add item
        moveEm()
    moveEm()
    assert (returnedItems.Count = 0)
    assert (countAvail = pool.Count)
 
  let take() =
    addReturnedItems()
    let ok, obj = pool.TryTake()
    if ok then
      changeAvail -1
      changeInUse +1
      assert (countAvail = pool.Count)
      Some obj
    else
      None

  
  // Functions called at non-interrupt time

  let poolAdd item = returnedItems.Add item

  let addNewItem() =
    let item = creator()
    item.SeqNum <- seqNum ; seqNum <- seqNum - 1
    poolAdd item

  let addNewItems n = for i in 1..n do  addNewItem() // Add to the pool.

  let addItemsIfNeeded() = addNewItems (minCount - countAvail)

        
  do
    if startCount <> 0 then  // see CbMessage constructor
      assert (countAvail = 0)
      assert pool.IsEmpty
      let n = max minCount startCount
      addNewItems n  // Stock the pool.
      countInUse <- 0  // Zero out the changes to countInUse in poolAdd.
      assert (countAvail = pool.Count)


  // Always called at interrupt time
  member this.Take()           = take()
  
  // Never called at interrupt time
  member this.ItemUseBegin()   = addItemsIfNeeded()
  member this.ItemUseEnd item  = poolAdd item
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
