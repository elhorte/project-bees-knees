module BeesLib.ItemPool


open System.Collections.Concurrent
open System.Threading

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// A pool of items that can be taken from the pool without risk of a GC.

[<AbstractClass>]
type IPoolItem() =
  abstract SeqNum   : int with get, set
  abstract UseCount : int with get, set
  abstract Locker   : obj with get


type ItemPool<'Item when 'Item :> IPoolItem>(startCount: int, minCount: int, creator: unit -> 'Item) =

  let pool = ConcurrentQueue<'Item>() // TryTake() at interrupt time
 
  
  // At interrupt time or at other times
  
  let countAvail = ref 0
  let countInUse = ref 0

  let changeAvail n = Volatile.Write(&countAvail.contents, Volatile.Read &countAvail.contents + n)
  let changeInUse n = Volatile.Write(&countInUse.contents, Volatile.Read &countInUse.contents + n)
 
  
  // Always used at interrupt time

  let takeFromPool() =
    let ok, obj = pool.TryDequeue()
    if ok then
      changeAvail -1
      changeInUse +1
      assert (Volatile.Read &countAvail.contents = pool.Count)
      Some obj
    else
      None

  
  // Never used at interrupt time

  let mutable seqNumNext = 0  // ok to be overwritten when item is used

  let addToPool (item: 'Item) =
    pool.Enqueue item // can cause allocation and thus GC
    changeAvail +1
    changeInUse -1
    assert (Volatile.Read &countAvail.contents = pool.Count)

  let changeItemUseCount (item: 'Item) n = lock item.Locker (fun () -> item.UseCount <- item.UseCount + n)

  let holdTilRelease (item: 'Item) = changeItemUseCount item +1

  let releaseToPool (item: 'Item) =
    if item.UseCount > 0 then  changeItemUseCount item -1
    if item.UseCount = 0 then  addToPool item

  let addNewItem() =
    let item = creator()
    seqNumNext  <- seqNumNext + 1
    item.SeqNum <- seqNumNext
    addToPool item

  let createAndAddNewItems n =
    if n > 0 then
      for i in 1..n do  addNewItem() // Add to the pool.
      assert (Volatile.Read &countAvail.contents  = pool.Count)
      Volatile.Write(&countInUse.contents, 0)

  let addMoreItemsIfNeeded() = createAndAddNewItems (minCount - Volatile.Read &countAvail.contents)

        
  do
    if startCount <> 0 then  // see CbMessage constructor
      // Stock the pool.
      assert (Volatile.Read &countAvail.contents = 0)
      assert pool.IsEmpty
      let n = max minCount startCount
      createAndAddNewItems n


  // Always used at interrupt time

  member this.Take()          = takeFromPool()

    
  // Never used at interrupt time

  member this.ItemUseBegin()           = addMoreItemsIfNeeded()
  member this.ItemUseEnd (item: 'Item) = addToPool item
  member this.Hold       (item: 'Item) = holdTilRelease item
  member this.Release    (item: 'Item) = releaseToPool  item
  member this.CountAvail               = Volatile.Read &countAvail.contents
  member this.CountInUse               = Volatile.Read &countInUse.contents
