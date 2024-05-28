module BeesUtil.SaveAsWave

open NAudio.Wave


open BeesUtil.PortAudioUtils

/// <summary>
/// Saves the given audio samples as an Wave file at the given filePath.
/// </summary>
/// <param name="filePath">The path of the audio file to save.</param>
/// <param name="frameRate">The input sampling frames per second of.</param>
/// <param name="nChannels">The number of samples in each audio frame.</param>
/// <param name="samples">The audio samples to save.</param>
let saveAsWave (filePath: string) (frameRate: float) nChannels (samples: float32[]) =
  let frameRate      = int (round frameRate)
  let samplesAsInt16 = convertFloat32ToInt16 samples
  let outFormat      = WaveFormat(frameRate, nChannels)
  use outWriter      = WaveFileWriter(filePath, outFormat)
  outWriter.Write(samplesAsInt16, 0, samplesAsInt16.Length)
