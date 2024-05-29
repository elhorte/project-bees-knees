module BeesUtil.SaveAsMp3

open NAudio.Wave
open NAudio.Lame

open BeesUtil.PortAudioUtils  

/// <summary>
/// Saves the given audio samples as an MP3 file at the given filePath.
/// </summary>
/// <param name="filePath">The path of the audio file to save.</param>
/// <param name="frameRate">The input sampling frames per second of.</param>
/// <param name="nChannels">The number of samples in each audio frame.</param>
/// <param name="samples">The audio samples to save.</param>
let saveAsMp3 (filePath: string) (frameRate: float) nChannels (samples: float32[]) =
  let frameRate      = int (round frameRate)
  let samplesAsInt16 = convertFloat32ToInt16 samples
  let outFormat      = WaveFormat(frameRate, nChannels)
  use outWriter      = new LameMP3FileWriter(filePath, outFormat, LAMEPreset.ABR_128)
  outWriter.Write(samplesAsInt16, 0, samplesAsInt16.Length)
