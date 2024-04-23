module BeesUtil.DebugGlobals

open DateTimeDebugging
open DateTimeShim

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

type SimIntsData = {
  NData: int
  NGap : int  }
type SimTimesData = {
  AudioDuration : _TimeSpan
  GapDuration   : _TimeSpan  }
type SimulatingCallbacks = NotSimulating | SimInts of SimIntsData | SimTimes of SimTimesData
// let mutable simulatingCallbacks = NotSimulating
let cbSimNDataFrames   sim f = match sim with | SimInts  d -> d.NData         | _ -> f()
let cbSimNGapFrames    sim f = match sim with | SimInts  d -> d.NGap          | _ -> f() 
let cbSimAudioDuration sim f = match sim with | SimTimes d -> d.AudioDuration | _ -> f()
let cbSimGapDuration   sim f = match sim with | SimTimes d -> d.GapDuration   | _ -> f()

let mutable inCallback = false 

