module BeesUtil.PlaySound

open System
open BeesLib
open PortAudioSharp
open InputStream

// let playSound inputStream (soundData: float[]) =
//     let paStream = (inputStream: InputStream).PaStream
//     // Create a buffer from soundData and create PAStreamParameters for output
//     let buffer = soundData |> Array.map (fun x -> Convert.ToInt32(x))
//
//     // Write data to the stream
//     paStream.WriteStream(stream, buffer, buffer.Length) |> ignore
//
//     // Stop the stream
//     paStream.Pa_StopStream(stream) |> ignore
//
//     // Close the stream
//     paStream.Pa_CloseStream(stream) |> ignore
//
//     // Terminate PortAudioSharp
//     paStream.Pa_Terminate() |> ignore
//
// // Create a float array (your actual sound data)
// let mySoundData = Array.init 44100 (fun _ -> 1.f)
// playSound mySoundData