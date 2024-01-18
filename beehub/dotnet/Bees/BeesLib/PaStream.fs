module BeesLib.PaStream


open System

open BeesUtil.Util
open PortAudioSharp
open BeesLib.InputStream
open BeesUtil.PortAudioUtils

// See Theory of Operation comment before main at the end of this file.


//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
// callback –> CbMessage –> CbMessageQueue handler

/// Main does the following:
/// - Initialize PortAudio.
/// - Create everything the callback will need.
///   - sampleRate, inputParameters, outputParameters
///   - a CbMessageQueue, which
///     - accepts a CbMessage from each callback
///     - calls the given handler asap for each CbMessage queued
///   - a CbContext struct, which is passed to each callback
/// - runs the cbMessageQueue
/// The audio callback is designed to do as little as possible at interrupt time:
/// - grabs a CbMessage from a preallocated ItemPool
/// - copies the input data buf into the CbMessage
/// - inserts the CbMessage into in the CbMessageQueue for later processing

// <summary>
//   Creates a Stream.Callback that:
//   <list type="bullet">
//     <item><description> Allocates no memory because this is a system-level callback </description></item>
//     <item><description> Gets a <c>CbMessage</c> from the pool and fills it in        </description></item>
//     <item><description> Posts the <c>CbMessage</c> to the <c>cbMessageQueue</c>     </description></item>
//   </list>
// </summary>
// <param name="cbContextRef"> A reference to the associated <c>CbContext</c> </param>
// <param name="cbMessageQueue" > The <c>CbMessageQueue</c> to post to           </param>
// <returns> A Stream.Callback to be called by PortAudioSharp                 </returns>

//–––––––––––––––––––––––––––––––––––––
// PortAudioSharp.Stream

/// <summary>
///   Creates an audio stream, to be started by the caller.
///   The stream will echo input to output if desired.
/// </summary>
/// <param name="inputParameters" > Parameters for input audio stream                               </param>
/// <param name="outputParameters"> Parameters for output audio stream                              </param>
/// <param name="sampleRate"      > Audio sample rate                                               </param>
/// <param name="withEchoRef"     > A Boolean determining if input should be echoed to output       </param>
/// <param name="withLoggingRef"  > A Boolean determining if the callback should do logging         </param>
/// <param name="cbMessageQueue"     > CbMessageQueue object handling audio stream                  </param>
/// <returns>A CbContext struct to be passed to each callback</returns>
let makeInputStream beesConfig inputParameters outputParameters sampleRate withEcho withLogging  : InputStream =
  initPortAudio()
  let inputStream = new InputStream(beesConfig, withEcho, withLogging)
  let callback = PortAudioSharp.Stream.Callback(
    // This fun has to be here because of a limitation of the compiler, apparently.
    fun                    input  output  frameCount  timeInfo  statusFlags  userDataPtr ->
    // PortAudioSharp.StreamCallbackResult.Continue )
      inputStream.Callback(input, output, frameCount, timeInfo, statusFlags, userDataPtr) )
  let paStream = tryCatchRethrow (fun () -> new PortAudioSharp.Stream(inParams        = Nullable<_>(inputParameters )        ,
                                                                      outParams       = Nullable<_>(outputParameters)        ,
                                                                      sampleRate      = sampleRate                           ,
                                                                      framesPerBuffer = PortAudio.FramesPerBufferUnspecified ,
                                                                      streamFlags     = StreamFlags.ClipOff                  ,
                                                                      callback        = callback                             ,
                                                                      userData        = Nullable()                           ) )
  inputStream.PaStream <- paStream
  tryCatchRethrow(fun() -> inputStream.Start())
  inputStream

//––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
