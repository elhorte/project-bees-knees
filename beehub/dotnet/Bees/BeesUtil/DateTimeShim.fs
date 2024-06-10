module BeesUtil.DateTimeShim



#if USE_FAKE_DATE_TIME

// open DateTimeDebugging

// let UsingFakeDateTime = true

type _DateTime = DateTimeFakes._DateTime
type _TimeSpan = DateTimeFakes._TimeSpan

#else

// let UsingFakeDateTime = false

type _DateTime = System.DateTime
type _TimeSpan = System.TimeSpan

#endif