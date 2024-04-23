namespace DateTimeDebugging;

public struct _DateTime : IComparable {
  public double TotalMilliseconds { get; }
  public int    Milliseconds => (int)TotalMilliseconds;
  public int    TimeOfDay    => (int)TotalMilliseconds;
  
  public _DateTime(double totalMilliseconds) => TotalMilliseconds = totalMilliseconds;

  public static _DateTime MinValue => new _DateTime(0);
  public static _DateTime MaxValue => new _DateTime(int.MaxValue);
  public static _DateTime Now      => new _DateTime(100);
  public static _DateTime UtcNow   => new _DateTime(100);
  public static _DateTime Today    => new _DateTime(0);
  
  public static _DateTime operator +(_DateTime dt , _TimeSpan ts ) => new(dt .TotalMilliseconds + ts .TotalMilliseconds);
  public static _DateTime operator -(_DateTime dt , _TimeSpan ts ) => new(dt .TotalMilliseconds - ts .TotalMilliseconds);
  public static _TimeSpan operator -(_DateTime dt1, _DateTime dt2) => new(dt1.TotalMilliseconds - dt2.TotalMilliseconds);

  public int CompareTo(object? obj) => TotalMilliseconds.CompareTo(((_DateTime?) obj)?.TotalMilliseconds);

  public override String ToString() => "" + (int)TotalMilliseconds;
  public String ToString(string s) => ToString();
}

public struct _TimeSpan  : IComparable {
  public double TotalMilliseconds { get; }
  public int    Milliseconds => (int)TotalMilliseconds;
  public double TotalSeconds => TotalMilliseconds / 1000.0;
  public double TotalMicroseconds => TotalMilliseconds * 1000;

  public _TimeSpan(double totalMilliseconds) => TotalMilliseconds = totalMilliseconds;

  public static _TimeSpan Zero => new _TimeSpan(0);
  
  public static _TimeSpan FromMilliseconds(double s) => new _TimeSpan(s);
  public static _TimeSpan FromMinutes     (double s) => new _TimeSpan(s * 1000.0 * 60);
  public static _TimeSpan FromSeconds     (double s) => new _TimeSpan(s * 1000.0);
  public static _TimeSpan FromDays        (double s) => new _TimeSpan(s * 1000.0 * 24 * 60 * 60);

  public static _TimeSpan operator +(_TimeSpan ts1, _TimeSpan ts2) => new(ts1.TotalMilliseconds + ts2.TotalMilliseconds);
  public static _TimeSpan operator -(_TimeSpan ts1, _TimeSpan ts2) => new(ts1.TotalMilliseconds - ts2.TotalMilliseconds);

  public int CompareTo(object? obj) => TotalMilliseconds.CompareTo(((_TimeSpan?) obj)?.TotalMilliseconds);

  public override String ToString() => "" + (int)TotalMilliseconds;
  public String ToString(string s) => ToString();
}