
open BeesUtil.SaveAsMp3



let samples = [|0f; 0.1f; 0.2f; 0.3f|]

saveAsMp3 "test1" 44100 1 samples
