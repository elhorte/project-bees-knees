module BeesUtil.DateTimeShim

// Comment these out to use the DateTimeDebugging versions of _DateTime and _TimeSpan 

open DateTimeDebugging
// type _DateTime = System.DateTime
// type _TimeSpan = System.TimeSpan

// let max (d1: _DateTime) (d2: _DateTime) =
//     if d1.Milliseconds > d2.Milliseconds then d1.Milliseconds
//                                          else d2.Milliseconds
//
// let min (d1: _DateTime) (d2: _DateTime) =
//     if d1.Milliseconds < d2.Milliseconds then d1.Milliseconds
//                                          else d2.Milliseconds