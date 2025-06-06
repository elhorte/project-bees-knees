$fn=50;
BOX_W = 28;  // Box Width
BOX_L = 200; // Box Length
BOX_H = 1.0; // Box Height
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

difference() {
  union() {
  linear_extrude( BOX_H )
    difference(){
      offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
      offset( r= CORNER_RADIUS - WALL ) square( [BOX_W-WALL, BOX_L-WALL],   center=true );
    };

  coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];

  translate ( [-BOX_W/2, -BOX_L/2] )
    hull()
    for (i = coordinates)
      translate(i) sphere(CORNER_RADIUS);

    translate([BOX_W/-2+WALL,BOX_L/-2+1,WALL]) cube([WALL,BOX_L-(WALL*2),3]);

    translate([BOX_W/2-WALL*1.8,BOX_L/-2+1,WALL]) cube([WALL,BOX_L-(WALL*2),3]);

  }
}