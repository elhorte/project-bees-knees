
open BeesLib.ItemPool

let startCount = 4

// Run with breakpoints to see how it works.
type TestItem() =
  inherit IPoolItem()
  let mutable num = 0
  override this.SeqNum
    with get() = num
    and set(value) = num <- value
  override this.ToString() = sprintf "TestItem %d ha" this.SeqNum

let test (pool: ItemPool<TestItem>) =
  let busies = ResizeArray<TestItem>()
  let rec takeWhileOk n =
    match pool.Take() with
    | Some item -> busies.Add item
                   pool.ItemUseBegin()
                   if n > 1 then takeWhileOk (n - 1) 
    | None   -> printf "None available"
  takeWhileOk startCount
  while busies.Count > 0 do
    let item = busies[0] in busies.RemoveAt 0
    pool.ItemUseEnd item
  printfn "pool count: %d" pool.CountAvail


do
  let minCount   = 2
  let pool = ItemPool<TestItem>(startCount, minCount, fun () -> new TestItem())
  test pool

