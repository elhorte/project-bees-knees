module BeesUtil.Ranges

open System


type RangeClip =
| BeforeData      = 0
| AfterData       = 1
| ClippedTail     = 2
| ClippedHead     = 3
| ClippedBothEnds = 4
| RangeOK         = 5

#nowarn "64"  // in case the inline is removed on clipRange for debugging

let inline clipRange (wantBegin: ^T) (wantLength: ^TL) (haveBegin: ^T) (haveLength: ^TL)  : RangeClip * ^T * ^TL =
  let inline add (t: ^T) (tl: ^TL) = t  + tl
  let inline sub (t1: ^T) (t2: ^T) = t1 - t2
  let wantEnd: ^T = add wantBegin wantLength
  let haveEnd: ^T = add haveBegin haveLength
  match () with
  | _ when wantEnd   <= haveBegin                           ->  ( RangeClip.BeforeData     , haveBegin, sub haveBegin haveBegin)
  | _ when                             haveEnd <= wantBegin ->  ( RangeClip.AfterData      , haveEnd  , sub haveEnd   haveEnd  ) 
  | _ when wantBegin <  haveBegin  &&  haveEnd <  wantEnd   ->  ( RangeClip.ClippedBothEnds, haveBegin, sub haveEnd   haveBegin) 
  | _ when wantBegin <  haveBegin                           ->  ( RangeClip.ClippedTail    , haveBegin, sub wantEnd   haveBegin) 
  | _ when                             haveEnd <  wantEnd   ->  ( RangeClip.ClippedHead    , wantBegin, sub haveEnd   wantBegin) 
  | _                                                       ->  assert (haveBegin <= wantBegin)
                                                                assert (wantEnd   <= haveEnd  )
                                                                ( RangeClip.RangeOK        , wantBegin, sub wantEnd   wantBegin)

(*
let a1 = clipRange 2 1 3 1
let a2 = clipRange 4 1 3 1
let a3 = clipRange 2 2 3 1
let a4 = clipRange 3 2 3 1
let a5 = clipRange 2 3 3 1
let a6 = clipRange 3 1 3 1
*)

(*
let wantT = DateTime.Today
let wantD = TimeSpan.FromSeconds(5)
let haveT = DateTime.Today
let haveD = TimeSpan.FromSeconds(3)

let x1 = clipRange wantT wantD haveT haveD
*)
