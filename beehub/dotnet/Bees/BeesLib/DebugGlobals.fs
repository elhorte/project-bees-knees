module BeesLib.DebugGlobals


let mutable simulating = false 
let mutable inCallback = false 
let getInCallback() = inCallback 
let setInCallback value = inCallback <- value