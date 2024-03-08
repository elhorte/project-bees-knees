module BeesUtil.ItemPool


open System
open System.Collections.Concurrent
open System.Threading

// We use records with extension functions here instead of classes with methods
// because calling a class method can allocate and eventually cause a crash when used in the callback.
// Actually happened.

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// A pool of items that can be taken from the pool without risk of a GC.

type PoolItem<'T> = {
  Data             : 'T
  ItemPool         : ItemPool<'T>
  Locker           : Object  
  mutable IdNum    : int }            // debugging

and ItemPool<'T> = {
  Pool        : ConcurrentQueue<PoolItem<'T>>
  MinCount    : int
  DataCreator : ItemPool<'T> -> 'T
  mutable IdNumNext    : int
  mutable SeqNumNext   : int  // for use by 'T
  mutable CountAvailV  : int
  mutable CountInUseV  : int }

//––––––––––––––––––––––––––––––––––

type PoolItem<'T>

  with

  static member New<'T> (pool : ItemPool<'T>) (t: 'T) = {
    Data     = t
    ItemPool = pool
    Locker   = Object()
    IdNum    = 0 }       

  member item.String = $"id={item.IdNum} %A{item.Data}" 

//––––––––––––––––––––––––––––––––––

type ItemPool<'T>

  with

  static member New<'T> (startCount: int) (minCount: int) (dataCreator: ItemPool<'T> -> 'T) =
    let ip = {
      Pool        = ConcurrentQueue<PoolItem<'T>>()
      MinCount    = minCount
      DataCreator = dataCreator
      IdNumNext   = 0 
      SeqNumNext  = 0 
      CountAvailV = 0
      CountInUseV = 0 }
    if startCount <> 0 then  // see CbMessage constructor
      // Stock the pool.
      assert (ip.CountAvail = 0)
      assert ip.Pool.IsEmpty
      let n = max minCount startCount
      ip.createAndAddNewItems n
    ip

  member         ip.CountAvail    = Volatile.Read  &ip.CountAvailV
  member         ip.CountInUse    = Volatile.Read  &ip.CountInUseV
  member private ip.changeAvail n = Volatile.Write(&ip.CountAvailV, ip.CountAvail + n)
  member private ip.changeInUse n = Volatile.Write(&ip.CountInUseV, ip.CountInUse + n)

  // Never used at interrupt time

  member private ip.addToPool (item: PoolItem<'T>) =
    ip.Pool.Enqueue item // can cause allocation and thus GC
    ip.changeAvail +1
    ip.changeInUse -1
    assert (ip.CountAvail = ip.Pool.Count)

  member private ip.addNewItem<'T>()  =
    ip.IdNumNext  <- ip.IdNumNext + 1
    let item = PoolItem.New ip (ip.DataCreator ip)
    item.IdNum <- ip.IdNumNext
    ip.addToPool item

  member         ip.createAndAddNewItems<'T> n =
    if n <= 0 then  ()
    else
    for i in 1..n do
      ip.addNewItem()
      ip.changeInUse +1
    assert (Volatile.Read &ip.CountAvailV  = ip.Pool.Count)
    Volatile.Write(&ip.CountInUseV, 0)
    
  member private ip.AddMoreItemsIfNeeded() =
    ip.createAndAddNewItems (ip.MinCount - Volatile.Read &ip.CountAvailV)

  member         ip.ItemUseBegin ()   = ip.AddMoreItemsIfNeeded()
  member         ip.ItemUseEnd   item = ip.addToPool     item
  member         ip.PoolStats         = sprintf "pool=%A:%A" ip.CountAvail ip.CountInUse

  // Always used at interrupt time

  member         ip.Take() =
    match ip.Pool.TryDequeue() with
    | true, item -> ip.changeAvail -1
                    ip.changeInUse +1
                    assert (ip.CountAvail = ip.Pool.Count)
                    Some item
    | false, _  ->  None

//––––––––––––––––––––––––––––––––––
