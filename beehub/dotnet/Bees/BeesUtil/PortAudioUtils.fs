module BeesUtil.PortAudioUtils

open System
open PortAudioSharp

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudio Utils

let paTryCatchRethrow f =
  try f()
  with
  | :? PortAudioException as ex -> 
    printfn $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    raise ex
  | ex ->
    printfn $"Exception: %s{ex.Message}"
    raise ex

let exitWithTrouble exitValue (e: PortAudioException) message =
  printfn "Exiting with trouble: %s: %A %A" message e.ErrorCode e.Message
  Environment.Exit exitValue


/// Load the native library and initialize the PortAudio library.  
let initPortAudio() =
  paTryCatchRethrow(fun () -> 
    PortAudio.LoadNativeLibrary()
    PortAudio.Initialize() )

let terminatePortAudio() =
  PortAudio.Terminate()

let floatToMicrosecondsFractionOnly (time: float) : int =
  int (1_000_000.0 * (time % 1.0))
