module Bees.Parallel

open System


type IFParallelRunner<'T,'R> = 
    abstract member Submit: Func<Async<'T>> -> unit
    abstract member Results: Async<seq<'R>>

type ParallelRunner<'T,'R>(maxDegreesOfParallelism: int) =
    interface IFParallelRunner<'T,'R> with 
        member this.Submit (task: Func<Async<'T>>) = 
            // Implement logic here
            ()

        member this.Results = 
            // Implement logic here
            async { return seq [] }

// let runner = ParallelRunner<int,string>(4)