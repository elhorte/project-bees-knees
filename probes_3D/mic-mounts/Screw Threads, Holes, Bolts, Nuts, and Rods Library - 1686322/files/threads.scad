// Created in 2016 by Ryan A. Colyer.
// This work is released with CC0 into the public domain.
// https://creativecommons.org/publicdomain/zero/1.0/
//
// http://www.thingiverse.com/thing:1686322


// For internal use, this creates the polyhedrons that make up the threads.
module ThreadTooth(pitch, ir, or, ang, angstep) {
  hoff = pitch*ang/360;
  // The 1.005 is a fudge factor for overlap rounding errors.
  angnext = ang + 1.005*angstep;
  hoffnext = pitch*angnext/360;

  irx1 = cos(ang)*ir;
  iry1 = sin(ang)*ir;
  orx1 = cos(ang)*or;
  ory1 = sin(ang)*or;

  irx2 = cos(angnext)*ir;
  iry2 = sin(angnext)*ir;
  orx2 = cos(angnext)*or;
  ory2 = sin(angnext)*or;

  zl1 = hoff;
  zm1 = hoff+pitch/2;
  zh1 = hoff+pitch;
  zl2 = hoffnext;
  zm2 = hoffnext+pitch/2;
  zh2 = hoffnext+pitch;

  polyhedron(
    points = [
      // These are fudge factors for overlap rounding errors.
      [-0.01*irx1,-0.01*iry1,zl1], [-0.01*irx1,-0.01*iry1,zh1+0.2*pitch],
      [irx1,iry1,zl1], [irx1,iry1,zh1],
      [orx1,ory1,zm1],
      [irx2,iry2,zl2], [irx2,iry2,zh2],
      [orx2,ory2,zm2]],
    faces = [[0,1,3],[0,3,2],[2,3,4],[1,0,6],[0,5,6],[6,5,7],[0,2,5],[1,6,3],
      [2,4,7],[2,7,5],[3,7,4],[3,6,7]]
  );
}


// Provides standard metric thread pitches.
function ThreadPitch(diameter) =
  (diameter <= 64) ?
    lookup(diameter, [
      [2, 0.4],
      [2.5, 0.45],
      [3, 0.5],
      [4, 0.7],
      [5, 0.8],
      [6, 1.0],
      [7, 1.0],
      [8, 1.25],
      [10, 1.5],
      [12, 1.75],
      [14, 2.0],
      [16, 2.0],
      [18, 2.5],
      [20, 2.5],
      [22, 2.5],
      [24, 3.0],
      [27, 3.0],
      [30, 3.5],
      [33, 3.5],
      [36, 4.0],
      [39, 4.0],
      [42, 4.5],
      [48, 5.0],
      [52, 5.0],
      [56, 5.5],
      [60, 5.5],
      [64, 6.0]
    ]) :
    diameter * 6.0 / 64;


// Provides standard metric hex head widths across the flats.
function HexAcrossFlats(diameter) =
  (diameter <= 64) ?
    lookup(diameter, [
      [2, 4],
      [2.5, 5],
      [3, 5.5],
      [3.5, 6],
      [4, 7],
      [5, 8],
      [6, 10],
      [7, 11],
      [8, 13],
      [10, 16],
      [12, 18],
      [14, 21],
      [16, 24],
      [18, 27],
      [20, 30],
      [22, 34],
      [24, 36],
      [27, 41],
      [30, 46],
      [33, 50],
      [36, 55],
      [39, 60],
      [42, 65],
      [48, 75],
      [52, 80],
      [56, 85],
      [60, 90],
      [64, 95]
    ]) :
    diameter * 95 / 64;

// Provides standard metric hex head widths across the corners.
function HexAcrossCorners(diameter) =
  HexAcrossFlats(diameter) / cos(30);


// Provides standard metric hex (Allen) drive widths across the flats.
function HexDriveAcrossFlats(diameter) =
  (diameter <= 64) ?
    lookup(diameter, [
      [2, 1.5],
      [2.5, 2],
      [3, 2.5],
      [3.5, 3],
      [4, 3],
      [5, 4],
      [6, 5],
      [7, 5],
      [8, 6],
      [10, 8],
      [12, 10],
      [14, 12],
      [16, 14],
      [18, 15],
      [20, 17],
      [22, 18],
      [24, 19],
      [27, 20],
      [30, 22],
      [33, 24],
      [36, 27],
      [39, 30],
      [42, 32],
      [48, 36],
      [52, 36],
      [56, 41],
      [60, 42],
      [64, 46]
    ]) :
    diameter * 46 / 64;

// Provides standard metric hex (Allen) drive widths across the corners.
function HexDriveAcrossCorners(diameter) =
  HexDriveAcrossFlats(diameter) / cos(30);

// Provides metric countersunk hex (Allen) drive widths across the flats.
function CountersunkDriveAcrossFlats(diameter) =
  (diameter <= 14) ?
    HexDriveAcrossFlats(HexDriveAcrossFlats(diameter)) :
    round(0.6*diameter);

// Provides metric countersunk hex (Allen) drive widths across the corners.
function CountersunkDriveAcrossCorners(diameter) =
  CountersunkDriveAcrossFlats(diameter) / cos(30);

// Provides standard metric nut thickness.
function NutThickness(diameter) =
  (diameter <= 64) ?
    lookup(diameter, [
      [2, 1.6],
      [2.5, 2],
      [3, 2.4],
      [3.5, 2.8],
      [4, 3.2],
      [5, 4.7],
      [6, 5.2],
      [7, 6.0],
      [8, 6.8],
      [10, 8.4],
      [12, 10.8],
      [14, 12.8],
      [16, 14.8],
      [18, 15.8],
      [20, 18.0],
      [22, 21.1],
      [24, 21.5],
      [27, 23.8],
      [30, 25.6],
      [33, 28.7],
      [36, 31.0],
      [42, 34],
      [48, 38],
      [56, 45],
      [64, 51]
    ]) :
    diameter * 51 / 64;
  


// This creates a vertical rod at the origin with external threads.  It uses
// metric standards by default.
module ScrewThread(outer_diam, height, pitch=0, tooth_angle=30, tolerance=0.4) {
  pitch = (pitch==0) ? ThreadPitch(outer_diam) : pitch;
  angtotal = 360.1*height/pitch;
  precangstep = 54*tolerance/pitch;
  // An irrational angle step helps prevent rendering errors.
  angstep = (1-PI/1e3)*((precangstep>15) ? 15 : precangstep);
  // Plastic shrinkage and geometric correction factors.
  or = 0.125*tolerance + (outer_diam / 2)/cos(angstep/2);
  ir = outer_diam/2 - (pitch/2)/tan(tooth_angle);

  // The render() here slows down the initial pre-cache run, but greatly
  // improves the ability to rotate and zoom the design.
  render()
  difference() {
    for (a=[-360:angstep:angtotal]) {
      ThreadTooth(pitch, ir, or, a, angstep);
    }
    translate([-2*or,-2*or,-pitch]) cube([4*or,4*or,pitch]);
    translate([-2*or,-2*or,height]) cube([4*or,4*or,2*pitch]);
  }
}


// This creates a threaded hole in its children using metric standards by
// default.
module ScrewHole(outer_diam, height, position=[0,0,0], rotation=[0,0,0], pitch=0, tooth_angle=30, tolerance=0.4) {
  pitch = (pitch==0) ? ThreadPitch(outer_diam) : pitch;
  extra_height = 0.001 * height;

  render()
  difference() {
    children();
    translate(position)
      rotate(rotation)
      translate([0, 0, -extra_height/2])
      ScrewThread(1.01*outer_diam + 1.25*tolerance, height + extra_height,
        pitch, tooth_angle, tolerance);
  }
}


// This inserts a ClearanceHole in its children.
// The rotation vector is applied first, then the position translation,
// starting from a position upward from the z-axis at z=0.
module ClearanceHole(diameter, height, position=[0,0,0], rotation=[0,0,0], tolerance=0.4) {
  extra_height = 0.001 * height;

  render()
  difference() {
    children();
    translate(position)
      rotate(rotation)
      translate([0, 0, -extra_height/2])
      cylinder(h=height + extra_height, r=(diameter/2+tolerance));
  }
}


// This inserts a ClearanceHole with a recessed bolt hole in its children.
// The rotation vector is applied first, then the position translation,
// starting from a position upward from the z-axis at z=0.  The default
// recessed parameters fit a standard metric bolt.
module RecessedClearanceHole(diameter, height, position=[0,0,0], rotation=[0,0,0], recessed_diam=-1, recessed_height=-1, tolerance=0.4) {
  recessed_diam = (recessed_diam < 0) ?
    HexAcrossCorners(diameter) : recessed_diam;
  recessed_height = (recessed_height < 0) ? diameter : recessed_height;
  extra_height = 0.001 * height;

  render()
  difference() {
    children();
    translate(position)
      rotate(rotation)
      translate([0, 0, -extra_height/2])
      cylinder(h=height + extra_height, r=(diameter/2+tolerance));
    translate(position)
      rotate(rotation)
      translate([0, 0, -extra_height/2])
      cylinder(h=recessed_height + extra_height/2,
        r=(recessed_diam/2+tolerance));
  }
}


// This inserts a countersunk ClearanceHole in its children.
// The rotation vector is applied first, then the position translation,
// starting from a position upward from the z-axis at z=0.
// The countersunk side is on the bottom by default.
module CountersunkClearanceHole(diameter, height, position=[0,0,0], rotation=[0,0,0], sinkdiam=0, sinkangle=45, tolerance=0.4) {
  extra_height = 0.001 * height;
  sinkdiam = (sinkdiam==0) ? 2*diameter : sinkdiam;
  sinkheight = ((sinkdiam-diameter)/2)/tan(sinkangle);

  render()
  difference() {
    children();
    translate(position)
      rotate(rotation)
      translate([0, 0, -extra_height/2])
      union() {
        cylinder(h=height + extra_height, r=(diameter/2+tolerance));
        cylinder(h=sinkheight + extra_height, r1=(sinkdiam/2+tolerance), r2=(diameter/2+tolerance), $fn=24*diameter);
      }
  }
}


// Create a standard sized metric bolt with hex head and hex key.
module MetricBolt(diameter, length, tolerance=0.4) {
  drive_tolerance = pow(3*tolerance/HexDriveAcrossCorners(diameter),2)
    + 0.75*tolerance;

  render()
  difference() {
    cylinder(h=diameter, r=(HexAcrossCorners(diameter)/2-0.5*tolerance), $fn=6);
    cylinder(h=diameter,
      r=(HexDriveAcrossCorners(diameter)+drive_tolerance)/2, $fn=6,
      center=true);
  }
  translate([0,0,diameter-0.01]) ScrewThread(diameter, length+0.01, tolerance=tolerance);
}


// Create a standard sized metric countersunk (flat) bolt with hex key drive.
// In compliance with convention, the length for this includes the head.
module MetricCountersunkBolt(diameter, length, tolerance=0.4) {
  drive_tolerance = pow(3*tolerance/CountersunkDriveAcrossCorners(diameter),2)
    + 0.75*tolerance;

  render()
  difference() {
    cylinder(h=diameter/2, r1=diameter, r2=diameter/2, $fn=24*diameter);
    cylinder(h=0.8*diameter,
      r=(CountersunkDriveAcrossCorners(diameter)+drive_tolerance)/2, $fn=6,
      center=true);
  }
  translate([0,0,diameter/2-0.01])
    ScrewThread(diameter, length-diameter/2+0.01, tolerance=tolerance);
}


// Create a standard sized metric hex nut.
module MetricNut(diameter, thickness=0, tolerance=0.4) {
  thickness = (thickness==0) ? NutThickness(diameter) : thickness;
  ScrewHole(diameter, thickness, tolerance=tolerance)
    cylinder(h=thickness, r=HexAcrossCorners(diameter)/2-0.5*tolerance, $fn=6);
}


// Create a convenient washer size for a metric nominal thread diameter.
module MetricWasher(diameter) {
  render()
  difference() {
    cylinder(h=diameter/5, r=1.15*diameter, $fn=24*diameter);
    cylinder(h=2*diameter, r=0.575*diameter, $fn=12*diameter, center=true);
  }
}


// Solid rod on the bottom, external threads on the top.
module RodStart(diameter, height, thread_len=0, thread_diam=0, thread_pitch=0) {
  // A reasonable default.
  thread_diam = (thread_diam==0) ? 0.75*diameter : thread_diam;
  thread_len = (thread_len==0) ? 0.5*diameter : thread_len;
  thread_pitch = (thread_pitch==0) ? ThreadPitch(thread_diam) : thread_pitch;
    
  cylinder(r=diameter/2, h=height, $fn=24*diameter);

  translate([0, 0, height])
    ScrewThread(thread_diam, thread_len, thread_pitch);
}


// Solid rod on the bottom, internal threads on the top.
// Flips around x-axis after printing to pair with RodStart.
module RodEnd(diameter, height, thread_len=0, thread_diam=0, thread_pitch=0) {
  // A reasonable default.
  thread_diam = (thread_diam==0) ? 0.75*diameter : thread_diam;
  thread_len = (thread_len==0) ? 0.5*diameter : thread_len;
  thread_pitch = (thread_pitch==0) ? ThreadPitch(thread_diam) : thread_pitch;

  ScrewHole(thread_diam, thread_len, [0, 0, height], [180,0,0], thread_pitch)
    cylinder(r=diameter/2, h=height, $fn=24*diameter);
}


// Internal threads on the bottom, external threads on the top.
module RodExtender(diameter, height, thread_len=0, thread_diam=0, thread_pitch=0) {
  // A reasonable default.
  thread_diam = (thread_diam==0) ? 0.75*diameter : thread_diam;
  thread_len = (thread_len==0) ? 0.5*diameter : thread_len;
  thread_pitch = (thread_pitch==0) ? ThreadPitch(thread_diam) : thread_pitch;
  
  max_bridge = height - thread_len;
  // Use 60 degree slope if it will fit.
  bridge_height = ((thread_diam/4) < max_bridge) ? thread_diam/4 : max_bridge;

  difference() {
    union() {
      ScrewHole(thread_diam, thread_len, pitch=thread_pitch)
        cylinder(r=diameter/2, h=height, $fn=24*diameter);
  
      translate([0,0,height])
        ScrewThread(thread_diam, thread_len, pitch=thread_pitch);
    }
    // Carve out a small conical area as a bridge.
    translate([0,0,thread_len])
      cylinder(h=bridge_height, r1=thread_diam/2, r2=0.1);
  }
}


// Produces a matching set of metric bolts, nuts, and washers.
module MetricBoltSet(diameter, length, quantity=1) {
  for (i=[0:quantity-1]) {
    translate([0, i*4*diameter, 0]) MetricBolt(diameter, length);
    translate([4*diameter, i*4*diameter, 0]) MetricNut(diameter);
    translate([8*diameter, i*4*diameter, 0]) MetricWasher(diameter);
  }
}


module Demo() {
  translate([0,-0,0]) MetricBoltSet(3, 8);
  translate([0,-20,0]) MetricBoltSet(4, 8);
  translate([0,-40,0]) MetricBoltSet(5, 8);
  translate([0,-60,0]) MetricBoltSet(6, 8);
  translate([0,-80,0]) MetricBoltSet(8, 8);

  translate([0,25,0]) MetricCountersunkBolt(5, 10);
  translate([23,18,5])
    scale([1,1,-1])
    CountersunkClearanceHole(5, 8, [7,7,0], [0,0,0])
    cube([14, 14, 5]);

  translate([70, -10, 0])
    RodStart(20, 30);
  translate([70, 20, 0])
    RodEnd(20, 30);
}


Demo();
//MetricBoltSet(6, 8, 10);

