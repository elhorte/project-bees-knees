module BeesUtil.PortAudioConfig

open System
open System.Text

open PortAudioSharp

open BeesUtil.DebugGlobals
open BeesUtil.DateTimeShim



//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// PortAudioConfig

type PortAudioConfig = {
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

let printPortAudioConfig bc =
  let sb = StringBuilder()
  sb.AppendLine "PortAudioConfig:"                                              |> ignore
  sb.AppendLine $"  InputStreamAudioDuration   {bc.InputStreamAudioDuration  }" |> ignore
  sb.AppendLine $"  InputStreamRingGapDuration {bc.InputStreamRingGapDuration}" |> ignore
  sb.AppendLine $"  SampleSize                 {bc.SampleSize                }" |> ignore
  sb.AppendLine $"  InChannelCount             {bc.InChannelCount            }" |> ignore
  sb.AppendLine $"  InFrameRate                {bc.InFrameRate               }" |> ignore
  Console.WriteLine (sb.ToString())
