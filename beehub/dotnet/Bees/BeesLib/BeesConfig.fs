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
  sb.AppendLine "BeesConfig:"
  sb.AppendLine $"  LocationId                  {bc.LocationId                 }"
  sb.AppendLine $"  HiveId                      {bc.HiveId                     }"
  sb.AppendLine $"  PrimaryDir                  {bc.PrimaryDir                 }"
  sb.AppendLine $"  MonitorDir                  {bc.MonitorDir                 }"
  sb.AppendLine $"  PlotDir                     {bc.PlotDir                    }"
  sb.AppendLine $"  inputStreamBufferedDuration {bc.inputStreamBufferedDuration}"
  sb.AppendLine $"  SampleSize                  {bc.SampleSize                 }"
  sb.AppendLine $"  InChannelCount              {bc.InChannelCount             }"
  sb.AppendLine $"  InSampleRate                {bc.InSampleRate               }"
  System.Console.WriteLine (sb.ToString())