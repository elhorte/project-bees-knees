module BeesLib.StreamGeneric

open PortAudioSharp

type StreamGeneric<'T>(
         inParams        : StreamParameters ,
         outParams       : StreamParameters ,
         sampleRate      : float            ,
         framesPerBuffer : uint32           ,
         streamFlags     : StreamFlags      ,
         callback        : Stream.Callback  ,
         context         : 'T               ) =

    inherit Stream (inParams        = inParams        ,
                    outParams       = outParams       ,
                    sampleRate      = sampleRate      ,
                    framesPerBuffer = framesPerBuffer ,
                    streamFlags     = streamFlags     ,
                    callback        = callback        ,
                    userData        = context         ) 
    
    member _.context with get() = context

