
open BeesUtil.ItemPool

let startCount = 4

// Run with breakpoints to see how it works.
type Thingy(pool: ItemPool<Thingy>) =
  
  member val SeqNum = 0  with get, set

  override this.ToString() = sprintf "Thingy seq %d" this.SeqNum

let bumpSeqNum (item: PoolItem<Thingy>) =
    item.ItemPool.SeqNumNext <- item.ItemPool.SeqNumNext + 1
    item.Data.SeqNum     <- item.ItemPool.SeqNumNext
    
let test (pool: ItemPool<Thingy>) =
  let busies = ResizeArray<PoolItem<Thingy>>()
  let once() =
    let rec takeWhileOk n =
      match pool.Take() with
      | Some item -> bumpSeqNum item
                     busies.Add item
                     pool.ItemUseBegin()
                     if n > 1 then takeWhileOk (n - 1) 
      | None   -> printf "None available"
    takeWhileOk startCount
    while busies.Count > 0 do
      let item = busies[0] in busies.RemoveAt 0
      pool.ItemUseEnd item
    printfn "pool count: %d" pool.CountAvail
  once()  // breakpoint here. Inspect the pool.Pool and step, twice 
  once()

let makeThingy (pool: ItemPool<Thingy>) =
  Thingy pool 

do
  let minCount = 2
  let pool = makeItemPool<Thingy> startCount minCount makeThingy
  test pool

