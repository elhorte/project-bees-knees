module BeesUtil.PortAudioUtils

open System
open PortAudioSharp

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudio Utils

let exitWithTrouble exitValue (e: PortAudioException) message =
  printfn "Trouble: %s: %A %A" message e.ErrorCode e.Message
  Environment.Exit exitValue


/// Load the native library and initialize the PortAudio library.  
let initPortAudio() =
  try
    PortAudio.LoadNativeLibrary()
    PortAudio.Initialize()
  with :? PortAudioException as e -> exitWithTrouble 2 e "Initializing PortAudio"

let terminatePortAudio() =
  PortAudio.Terminate()

let floatToMicrosecondsFractionOnly (time: float) : int =
  int (1_000_000.0 * (time % 1.0))
