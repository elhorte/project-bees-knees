module BeesLib.DebugGlobals


let mutable inCallback = false 
let getInCallback() = inCallback 
let setInCallback value = inCallback <- value