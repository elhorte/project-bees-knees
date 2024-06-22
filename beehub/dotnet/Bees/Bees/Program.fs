
open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.SaveAudioFile
open BeesLib.BeesConfig
open BeesLib.Keyboard

//–––––––––––––––––––––––––––––––––––––
// Main

[<EntryPoint>]
let main _ =
  initPortAudio()
  let sampleRate, inputParameters, outputParameters = prepareArgumentsForStreamCreation false
  beesConfig <- {
    LocationId                 = 1
    HiveId                     = 1
    PrimaryDir                 = "primary"
    MonitorDir                 = "monitor"
    PlotDir                    = "plot"
    InputStreamAudioDuration   = _TimeSpan.FromMinutes 16
    InputStreamRingGapDuration = _TimeSpan.FromSeconds 1
    SampleSize                 = sizeof<float32>
    WithEcho                   = false 
    WithLogging                = false
    Simulating                 = NotSimulating 
    InputParameters            = inputParameters
    OutputParameters           = outputParameters
    InChannelCount             = inputParameters.channelCount
    InFrameRate                = sampleRate  }
  printBeesConfig beesConfig

  try
    (processKeyboardCommands beesConfig).Wait() 
  finally
    () // printfn "Main task done." 

  terminatePortAudio() // ; printfn "PortAudioSharp Terminated"
  printfn "Exiting."
  0
