module BeesLib.BeesConfig

open System.Text

open DateTimeDebugging
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
  InChannelCount             : int
  InFrameRate                : double  } with

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
  System.Console.WriteLine (sb.ToString())