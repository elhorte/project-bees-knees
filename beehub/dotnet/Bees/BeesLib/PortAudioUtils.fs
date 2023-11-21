module BeesLib.PortAudioUtils

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
  with
  | :? PortAudioException as e -> exitWithTrouble 2 e "Initializing PortAudio"


let floatToMicrosecondsFractionOnly (time: float) : int =
  int (1_000_000.0 * (time % 1.0))


/// DeviceInfo to a string, replacement for missing ToString()  
let deviceInfoToString (deviceInfo: DeviceInfo) : string =
  sprintf @"DeviceInfo [
  name=%s
  hostApi=%d
  maxInputChannels=%i
  maxOutputChannels=%i
  defaultSampleRate=%f
  defaultLowInputLatency=%f
  defaultLowOutputLatency=%f
  defaultHighInputLatency=%f
  defaultHighOutputLatency=%f
]"  
    deviceInfo.name 
    deviceInfo.hostApi
    deviceInfo.maxInputChannels 
    deviceInfo.maxOutputChannels 
    deviceInfo.defaultSampleRate 
    deviceInfo.defaultLowInputLatency 
    deviceInfo.defaultLowOutputLatency 
    deviceInfo.defaultHighInputLatency 
    deviceInfo.defaultHighOutputLatency 

