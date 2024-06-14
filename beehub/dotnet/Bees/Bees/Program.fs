
open System
open System.Threading
open System.Threading.Tasks
open FSharp.Control

open BeesUtil.DateTimeShim

open BeesUtil.DebugGlobals
open BeesUtil.PortAudioUtils
open BeesLib.SaveAudioFile
open BeesLib.BeesConfig
open BeesLib.Keyboard
open BeesLib.Commands

let waitForKeyboardCommands() = task {
  startKeyboardBackground()
  use cts = new CancellationTokenSource()
  printfn "Reading keyboard..."
  do! keyboardKeyInput "" cts
 }

let mainTask() =
  try
    let t = task {
      do! waitForKeyboardCommands() }
    t.Wait() 
    printfn "Main task done." 
  finally
    printfn "Exiting."

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

  mainTask()

  printfn "Terminating PortAudio..." ; terminatePortAudio()
  printfn "Terminated"
  0
