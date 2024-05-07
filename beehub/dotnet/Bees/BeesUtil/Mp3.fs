module BeesUtil.Mp3

open NAudio.Lame
open NAudio.Wave


let saveAsMp3 (filePath: string) sampleRate nChannels (samples: float32[]) =
  let sampleSize   = sizeof<float32>
  let sampleSize_1 = sampleSize - 1
  let outputBuffer = Array.zeroCreate<byte> (samples.Length * sampleSize)
  samples
  |> Array.mapi (fun i sample ->
      let iScaled = i * sampleSize
      let bytesArray = System.BitConverter.GetBytes sample
      outputBuffer[iScaled .. iScaled + sampleSize_1] <- bytesArray
  ) |> ignore
  
  // Use NAudio.Lame to save amplified buffer to mp3
  let outFormat = WaveFormat(sampleRate, nChannels)
  try
    use outWriter = new LameMP3FileWriter(filePath, outFormat, LAMEPreset.ABR_128)
    try
      outWriter.Write(outputBuffer, 0, outputBuffer.Length)
    with
    | :? System.IO.IOException as ex ->
      printfn "Failed to write to file %s, Error: %s" filePath ex.Message
    | ex ->
      printfn "An error occurred: %s" ex.Message 
  with
  | :? System.IO.IOException as ex ->
    printfn "Failed to write to file %s, Error: %s" filePath ex.Message
  | ex ->
    printfn "An error occurred: %s" ex.Message 
