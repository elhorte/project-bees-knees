
open BeesUtil.SaveAsMp3
open NAudio.Lame



let samples = [|0f; 0.1f; 0.2f; 0.3f|]

saveAsMp3 LAMEPreset.ABR_128 44100 1 "test1" samples 
