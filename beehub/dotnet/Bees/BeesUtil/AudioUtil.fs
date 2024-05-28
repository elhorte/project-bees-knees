module BeesUtil.AudioUtil


/// <summary>
/// Saves the given audio samples as an MP3 file at the given filePath.
/// </summary>
/// <param name="saveFunction">The function to save in a specific format.</param>
/// <param name="filePath">The path of the MP3 file to save.</param>
/// <param name="frameRate">The sample rate of the audio samples.</param>
/// <param name="nChannels">The number of channels in the audio samples.</param>
/// <param name="samples">The audio samples to save.</param>
let saveToFile f (filePath: string) (frameRate: float) (nChannels: int) (samples: float32[]) =
  try
    f filePath frameRate nChannels samples
  with
  | :? System.IO.IOException as ex ->
    printfn "Failed to write to file %s, Error: %s" filePath ex.Message
  | ex ->
    printfn "An error occurred: %s" ex.Message 