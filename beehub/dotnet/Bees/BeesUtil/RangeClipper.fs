module BeesUtil.RangeClipper


type RangeClip =
| BeforeData      = 0
| AfterData       = 1
| ClippedTail     = 2
| ClippedHead     = 3
| ClippedBothEnds = 4
| RangeOK         = 5

#nowarn "64"  // in case the `inline` on clipRange is removed for debugging

/// <summary>
/// Fits a desired range (<c>wantBegin</c>, <c>wantLength</c>)
/// into a given range (<c>haveBegin</c>, <c>haveLength</c>).
/// </summary>
/// <remarks>
/// Works with any (<c>DT</c> and <c>TS</c>) that can compute DT + TS and DT1 - DT2.
/// <para>
/// <c>RangeClip</c> return values:
/// <br/> - <c>BeforeData</c>: The desired range is before the available data.
/// <br/> - <c>AfterData</c>: The desired range is after the available data.
/// <br/> - <c>ClippedTail</c>: The tail end of the desired range was clipped to fit within the available data.
/// <br/> - <c>ClippedHead</c>: The head of the desired range was clipped to fit within the available data.
/// <br/> - <c>ClippedBothEnds</c>: Both the head and tail of the desired range were clipped to fit within the available data.
/// <br/> - <c>RangeOK</c>: The desired range fits within the available data.
/// </para>
/// </remarks>
/// <param name="wantBegin">The beginning of the desired range.</param>
/// <param name="wantLength">The length of the desired range.</param>
/// <param name="haveBegin">The beginning of the given range.</param>
/// <param name="haveLength">The length of the given range.</param>
/// <returns>
/// A tuple of <c>RangeClip</c> enumeration, the beginning of the possibly-clipped range,
/// and the length of the possibly-clipped range.
/// </returns>
let inline clipRange (wantBegin: ^DT) (wantLength: ^TS) (haveBegin: ^DT) (haveLength: ^TS)  : RangeClip * ^DT * ^TS =
  let inline add (dt : ^DT) (ts : ^TS) = dt  + ts
  let inline sub (dt1: ^DT) (dt2: ^DT) = dt1 - dt2
  let wantEnd: ^DT = add wantBegin wantLength
  let haveEnd: ^DT = add haveBegin haveLength
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

open System

let wantT = DateTime.Today
let wantD = TimeSpan.FromSeconds(5)
let haveT = DateTime.Today
let haveD = TimeSpan.FromSeconds(3)

let x1 = clipRange wantT wantD haveT haveD
*)
