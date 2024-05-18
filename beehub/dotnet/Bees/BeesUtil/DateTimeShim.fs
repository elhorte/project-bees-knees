module BeesUtil.DateTimeShim



#if USE_FAKE_DATE_TIME

// open DateTimeDebugging

// let UsingFakeDateTime = true

type _DateTime = DateTimeDebugging._DateTime
type _TimeSpan = DateTimeDebugging._TimeSpan

#else

// let UsingFakeDateTime = false

type _DateTime = System.DateTime
type _TimeSpan = System.TimeSpan

#endif