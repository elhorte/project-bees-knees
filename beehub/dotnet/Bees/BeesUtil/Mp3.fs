module BeesUtil.Mp3

open NAudio.Lame
open NAudio.Wave


/// <summary>
/// Saves the given audio samples as an MP3 file at the given filePath.
/// </summary>
/// <param name="filePath">The path of the MP3 file to save.</param>
/// <param name="frameRate">The sample rate of the audio samples.</param>
/// <param name="nChannels">The number of channels in the audio samples.</param>
/// <param name="samples">The audio samples to save.</param>
let saveAsMp3 (filePath: string) (frameRate: float) nChannels (samples: float32[]) =
  let frameRate = int (round frameRate)
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
  let outFormat = WaveFormat(frameRate, nChannels)
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
