
type SmpInd  = SmpInd  of int * int  // A Sample Integer is a value and a number of bytes
type S32BInd = S32BInd of int       // A Sample Integer is a value and a number of bytes
type FrmInd  = FrmInd  of int * int  // A Frame Integer is a value and a number of samples

// Define extension methods
type Ring = { Ring: float32 array } with
    member this.Item (index: SmpInd ) = match index with SmpInd (i    , _          ) -> this.Ring[i                       ]
    member this.Item (index: S32BInd) = match index with S32BInd s32Ind              -> this.Ring[s32Ind * sizeof<float32>]
    member this.Item (index: FrmInd ) = match index with FrmInd (frame, sampleCount) -> this.Ring[frame * sampleCount     ]

// Usage
let sa = { Ring = [| for i in 0..64 -> float32 i |] }

let smpInd = SmpInd  (10, sizeof<float32>)
let s32Ind = S32BInd  10      // start at sample 10
let frmInd = FrmInd  (10, 2)  // start at frame 10 with 2 samples per frame

let valAtSampleIndex = sa[smpInd]
let valAtS32Index    = sa[s32Ind]
let valAtFrameIndex  = sa[frmInd]

printfn "%f" valAtSampleIndex // prints the value at sample index 5
printfn "%f" valAtS32Index    // prints the value at frame index 2 (considering 2 samples per frame)
printfn "%f" valAtFrameIndex  // prints the value at frame index 2 (considering 2 samples per frame)
