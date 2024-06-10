module BeesUtil.AudioUtils


let convertFloat32ToInt16 (input: float32[])  : byte[] =
  let outSize   = sizeof<int16>
  let outSizeM1 = outSize - 1
  let output = Array.zeroCreate<byte> (input.Length * outSize)
  let mutable iOut = 0
  for i in 0 .. input.Length - 1 do
    let sampleAsInt16 = int16 (input[i] * float32 System.Int16.MaxValue)  // Convert float32 to int16
    let sampleAsBytes = System.BitConverter.GetBytes(sampleAsInt16)
    output[iOut .. iOut+outSizeM1] <- sampleAsBytes
    iOut <- iOut + outSize
  output
