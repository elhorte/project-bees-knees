$fn=50;
BOX_W = 28; // Box Width
BOX_L = 200;// Box Length
BOX_H = 9.5; // Box Height (adjusted to have 4mm base thickness)
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1;// Wall Thickness

//KEEL_OUTSIDE_WIDTH=9.1;
KEEL_WIDTH=9.2;
KEEL_DEPTH=2;
KEEL_LENGTH=32;

CON_OUTSIDE=6;
CON_INSIDE=4;
CON_LENGTH=3;

difference() {
  union() {
  linear_extrude( BOX_H )
    difference(){
      offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
      offset(r= CORNER_RADIUS - WALL) square([BOX_W-WALL, BOX_L-WALL], center=true );
    };

    coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];

    translate ( [-BOX_W/2, -BOX_L/2] )
      hull()
      for (i = coordinates)
        translate(i) sphere(CORNER_RADIUS);
  }
  // opposite audio connector side
  translate([0,-67.75,BOX_H-10])
  rotate([90,0,0])
  #linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_DEPTH], center=true);  
  
  // audio connector side
  translate([0,101,BOX_H-10])
  rotate([90,0,0])
  #linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_DEPTH], center=true);  
  
  translate([0,102.0,BOX_H-5])
  rotate([90,0,0])
  cylinder(h=CON_LENGTH,r=CON_INSIDE/2);
  
  translate([0,102.0,BOX_H-4])
  rotate([90,0,0])
  //cylinder(h=CON_LENGTH+1,r=CON_INSIDE/2);
  linear_extrude(3.0) square([4.0,3], center=true);
}
