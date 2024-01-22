module BeesLib.BeesConfig

open System


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
