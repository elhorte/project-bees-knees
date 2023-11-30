module BeesLib.Mp3

open NAudio.Lame
// open NAudio.Wave
//
// let saveAsMp3 (outputFile: string) sampleRate nChannels (samples: int16[]) =
//   
//     // Convert int16[] samples to byte[] buffer with BitConverter
//     let buffer = Array.zeroCreate<byte> (samples.Length * 2) // 2 bytes per sample
//     samples
//     |> Array.mapi (fun i sample ->
//         let bytes = System.BitConverter.GetBytes sample
//         buffer[i * 2 .. i * 2 + 1] <- bytes
//     ) |> ignore
//   
//     // Use NAudio.Lame to save amplified buffer to mp3
//     let outFormat = WaveFormat(sampleRate, nChannels)
//     use outWriter = new LameMP3FileWriter(outputFile, outFormat, LAMEPreset.ABR_128)
//     outWriter.Write(buffer, 0, buffer.Length)
//
// // let saveFloat32AsMp3 (samples: float32[]) (outputFile: string) =
