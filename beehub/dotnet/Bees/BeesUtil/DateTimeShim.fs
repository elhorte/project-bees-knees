module BeesUtil.DateTimeShim

// Every usage of this file must have both of these:
//   open DateTimeDebugging
//   open BeesUtil.DateTimeShim

// To use System.DateTime and System.TimeSpan, 
// comment these out
// open DateTimeDebugging
// let UsingFakeDateTime = true

// Or to use the DateTimeDebugging.cs versions of _DateTime and _TimeSpan,
// comment these out 
type _DateTime = System.DateTime
type _TimeSpan = System.TimeSpan
let UsingFakeDateTime = false
