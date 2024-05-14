module BeesUtil.PortAudioUtils

open System
open PortAudioSharp

open DateTimeDebugging
open DateTimeShim


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudio Utils

let paTryCatch f (exit: Exception -> unit) =
  try
    f()
  with
  | :? PortAudioException as ex -> 
    Console.WriteLine $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    exit  ex
    raise ex
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    exit  ex
    raise ex

let paTryCatchRethrow f = paTryCatch f (fun e -> ()                 )
let paTryCatchExit    f = paTryCatch f (fun e -> Environment.Exit(2))

let paExitWithTrouble exitValue (e: PortAudioException) message =
  Console.WriteLine "Exiting with trouble: %s{message}: %A{e.ErrorCode} %A{e.Message}"
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

let durationToNFrames frameRate (duration: _TimeSpan) =
  let nFramesApprox = duration.TotalSeconds * frameRate
  int (round nFramesApprox)
