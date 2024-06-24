module BeesUtil.PortAudioUtils

open System
open PortAudioSharp

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


type PaTime = float
let  PaTimeBad = 0.0
let  dummySample = 9999999f  // 


/// Load the native library and initialize the PortAudio library.  
let initPortAudio() =
  paTryCatchRethrow(fun () -> 
    PortAudio.LoadNativeLibrary()
    PortAudio.Initialize() )

let terminatePortAudio() =
  PortAudio.Terminate()


/// input of 1.0 gets 1.0 output.  input of 1.0 - 70db gets 0.0 output; lower input clips to 0.0 
let convertToDb (dbRange: float) (value: float) =
    let dbFactor = 20.0
    let logBase  = 10.0
    let minValue = logBase ** (-dbRange / dbFactor)
    (dbFactor * log10 (max minValue value) + dbRange) / dbRange 
