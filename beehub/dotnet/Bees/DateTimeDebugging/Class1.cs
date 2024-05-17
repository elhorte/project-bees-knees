namespace DateTimeDebugging;

public struct _DateTime : IComparable {
  public int    Millisecond { get; }
  public int    TimeOfDay    => Millisecond;
  
  private _DateTime(int ms) => Millisecond = ms;

  public static _DateTime MinValue => new _DateTime(0);
  public static _DateTime BadValue => new _DateTime(99999);
  public static _DateTime MaxValue => BadValue;
  public static _DateTime Now { get; set; }
  static _DateTime() { Now = new _DateTime(100); }
  public static _DateTime UtcNow   => new _DateTime(100);
  public static _DateTime Today    => new _DateTime(0);

  public int    Second => 0;
  
  public _DateTime AddSeconds(double s) => new _DateTime((int) Math.Round ((double) Millisecond + s / 1000.0));
  
  public static _DateTime operator +(_DateTime dt , _TimeSpan ts ) => new(dt .Millisecond + ts .Milliseconds);
  public static _DateTime operator -(_DateTime dt , _TimeSpan ts ) => new(dt .Millisecond - ts .Milliseconds);
  public static _TimeSpan operator -(_DateTime dt1, _DateTime dt2) => new(dt1.Millisecond - dt2.Millisecond);

  public int CompareTo(object? obj) => Millisecond.CompareTo(((_DateTime?) obj)?.Millisecond);

  public override String ToString() => "" + Millisecond;
  public String ToString(string s) => ToString();
}

public struct _TimeSpan  : IComparable {
  public double TotalMilliseconds { get; }
  public int    Milliseconds      => (int) Math.Round(TotalMilliseconds);
  public double TotalSeconds      => TotalMilliseconds / 1000.0;
  public double TotalMicroseconds => TotalMilliseconds * 1000;

  public _TimeSpan(double totalMilliseconds) => TotalMilliseconds = totalMilliseconds;

  public static _TimeSpan Zero     => new _TimeSpan(0);
  public static _TimeSpan MinValue => new _TimeSpan(0);
  public static _TimeSpan BadValue => _TimeSpan.FromSeconds(99.999999);
  public static _TimeSpan MaxValue => BadValue;

  public static _TimeSpan FromMilliseconds(double s) => new _TimeSpan(s);
  public static _TimeSpan FromMinutes     (double s) => new _TimeSpan(s * 1000.0 * 60);
  public static _TimeSpan FromSeconds     (double s) => new _TimeSpan(s * 1000.0);
  public static _TimeSpan FromDays        (double s) => new _TimeSpan(s * 1000.0 * 24 * 60 * 60);

  public static _TimeSpan operator +(_TimeSpan ts1, _TimeSpan ts2) => new(ts1.TotalMilliseconds + ts2.TotalMilliseconds);
  public static _TimeSpan operator -(_TimeSpan ts1, _TimeSpan ts2) => new(ts1.TotalMilliseconds - ts2.TotalMilliseconds);
  public static _TimeSpan operator *(_TimeSpan ts1, double x     ) => new(ts1.TotalMilliseconds * x                    );
  public static _TimeSpan operator /(_TimeSpan ts1, double x     ) => new(ts1.TotalMilliseconds / x                    );
  public static double    operator /(_TimeSpan ts1, _TimeSpan ts2) =>     ts1.TotalMilliseconds / ts2.TotalMilliseconds ;

  public double Seconds => TotalMilliseconds * 1000.0;

  public int CompareTo(object? obj) => TotalMilliseconds.CompareTo(((_TimeSpan?) obj)?.TotalMilliseconds);

  public override String ToString() => "" + (int) Math.Round(TotalMilliseconds);
  public String ToString(string s) => ToString();
}