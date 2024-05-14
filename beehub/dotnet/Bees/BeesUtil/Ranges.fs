module BeesUtil.Ranges

open System


type RangeClip =
| BeforeData     
| AfterData      
| ClippedTail    
| ClippedHead    
| ClippedBothEnds
| RangeOK        

let inline clipRange (wantBegin: ^T) (wantLength: ^TL) (haveBegin: ^T) (haveLength: ^TL)  : RangeClip * ^T * ^TL =
  let inline add t  tl = t  + tl
  let inline sub t1 t2 = t1 - t2
  let wantEnd: ^T = add wantBegin wantLength
  let haveEnd: ^T = add haveBegin haveLength
  match () with
  | _ when wantEnd   <= haveBegin                           ->  ( BeforeData     , haveBegin, sub haveBegin haveBegin)
  | _ when                             haveEnd <= wantBegin ->  ( AfterData      , haveEnd  , sub haveEnd   haveEnd  ) 
  | _ when wantBegin <  haveBegin  &&  haveEnd <  wantEnd   ->  ( ClippedBothEnds, haveBegin, sub haveEnd   haveBegin) 
  | _ when wantBegin <  haveBegin                           ->  ( ClippedTail    , haveBegin, sub wantEnd   haveBegin) 
  | _ when                             haveEnd <  wantEnd   ->  ( ClippedHead    , wantBegin, sub haveEnd   wantBegin) 
  | _                                                       ->  assert (haveBegin <= wantBegin)
                                                                assert (wantEnd   <= haveEnd  )
                                                                ( RangeOK        , wantBegin, sub wantEnd   wantBegin)

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
