module BeesLib.BeesConfig

open System
open System.Text

open PortAudioSharp

open BeesUtil.DebugGlobals
open BeesUtil.DateTimeShim


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// BeesConfig

type BeesConfig = {
  LocationId                 : int
  HiveId                     : int
  PrimaryDir                 : string
  MonitorDir                 : string
  PlotDir                    : string
  InputStreamAudioDuration   : _TimeSpan
  InputStreamRingGapDuration : _TimeSpan // long enough for the largest automatically adjusted frameCount arg to callback
  SampleSize                 : int
  WithEcho                   : bool
  WithLogging                : bool
  Simulating                 : Simulating
  InputParameters            : PortAudioSharp.StreamParameters
  OutputParameters           : PortAudioSharp.StreamParameters
  InChannelCount             : int
  InFrameRate                : double  }
with

  member this.FrameSize = this.SampleSize * this.InChannelCount

let printBeesConfig bc =
  let sb = StringBuilder()
  sb.AppendLine "BeesConfig:"                                                   |> ignore
  sb.AppendLine $"  LocationId                 {bc.LocationId                }" |> ignore
  sb.AppendLine $"  HiveId                     {bc.HiveId                    }" |> ignore
  sb.AppendLine $"  PrimaryDir                 {bc.PrimaryDir                }" |> ignore
  sb.AppendLine $"  MonitorDir                 {bc.MonitorDir                }" |> ignore
  sb.AppendLine $"  PlotDir                    {bc.PlotDir                   }" |> ignore
  sb.AppendLine $"  InputStreamAudioDuration   {bc.InputStreamAudioDuration  }" |> ignore
  sb.AppendLine $"  InputStreamRingGapDuration {bc.InputStreamRingGapDuration}" |> ignore
  sb.AppendLine $"  SampleSize                 {bc.SampleSize                }" |> ignore
  sb.AppendLine $"  InChannelCount             {bc.InChannelCount            }" |> ignore
  sb.AppendLine $"  InFrameRate                {bc.InFrameRate               }" |> ignore
  Console.WriteLine (sb.ToString())


// placeholder for the global value.  Initialized by main.
let mutable beesConfig: BeesConfig = Unchecked.defaultof<BeesConfig>
