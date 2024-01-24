module BeesLib.BeesConfig

open System
open System.Text


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// BeesConfig

type BeesConfig = {
  LocationId                  : int
  HiveId                      : int
  PrimaryDir                  : string
  MonitorDir                  : string
  PlotDir                     : string
  inputStreamBufferedDuration : TimeSpan
  SampleSize                  : int
  InChannelCount              : int
  InSampleRate                : int  }

let printBeesConfig bc =
  let sb = StringBuilder()
  sb.AppendLine "BeesConfig:"                                                     |> ignore
  sb.AppendLine $"  LocationId                  {bc.LocationId                 }" |> ignore
  sb.AppendLine $"  HiveId                      {bc.HiveId                     }" |> ignore
  sb.AppendLine $"  PrimaryDir                  {bc.PrimaryDir                 }" |> ignore
  sb.AppendLine $"  MonitorDir                  {bc.MonitorDir                 }" |> ignore
  sb.AppendLine $"  PlotDir                     {bc.PlotDir                    }" |> ignore
  sb.AppendLine $"  inputStreamBufferedDuration {bc.inputStreamBufferedDuration}" |> ignore
  sb.AppendLine $"  SampleSize                  {bc.SampleSize                 }" |> ignore
  sb.AppendLine $"  InChannelCount              {bc.InChannelCount             }" |> ignore
  sb.AppendLine $"  InSampleRate                {bc.InSampleRate               }" |> ignore
  System.Console.WriteLine (sb.ToString())