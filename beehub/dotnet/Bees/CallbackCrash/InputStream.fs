module CallbackCrash.InputStream

open System
open PortAudioSharp


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

let paTryCatch f (exit: Exception -> unit) =
  try
    f()
  with
  | :? PortAudioException as ex -> 
    Console.WriteLine $"PortAudioException: ErrorCode: %A{ex.ErrorCode} %s{ex.Message}"
    exit  ex
    raise ex
  | ex ->
    Console.WriteLine $"Exception: %s{ex.Message}"
    exit  ex
    raise ex

let paTryCatchRethrow f = paTryCatch f (fun e -> ()                 )

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// InputStream


let callback input output frameCount timeInfo statusFlags userDataPtr =
  Console.Write "."
  PortAudioSharp.StreamCallbackResult.Continue
  

type InputStream = { paStream : PortAudioSharp.Stream } with 
  
  // initPortAudio() must be called before this.
  static member New ( sampleRate       : float            )
                    ( inputParameters  : StreamParameters )
                    ( outputParameters : StreamParameters ) =

    let callbackStub = PortAudioSharp.Stream.Callback(
      // The intermediate lambda here is required to avoid a compiler error.
      fun        input output frameCount timeInfo statusFlags userDataPtr ->
        callback input output frameCount timeInfo statusFlags userDataPtr )
    let paStream = paTryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                          outParams       = Nullable<_>(outputParameters)        ,
                                                                          sampleRate      = sampleRate                           ,
                                                                          framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                          streamFlags     = StreamFlags.ClipOff                  ,
                                                                          callback        = callbackStub                         ,
                                                                          userData        = ""                                   ) )
    { paStream = paStream } 
  
  member is.Start() = paTryCatchRethrow(fun() -> is.paStream.Start())
  member is.Stop () = paTryCatchRethrow(fun() -> is.paStream.Stop ())

  interface IDisposable with
    member this.Dispose() =
      System.Console.WriteLine("Disposing inputStream")
      this.paStream.Dispose()


