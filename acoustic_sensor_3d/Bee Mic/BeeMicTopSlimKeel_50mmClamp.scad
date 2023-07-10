$fn=50;
BOX_W = 28; // Box Width
BOX_L = 36;// Box Length
BOX_H = 1.0; // Box Height
//SCREW_SIZE = .5; // Screw size in mm
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

KEEL_WIDTH=9.0;
KEEL_HEIGHT=9.0;
KEEL_LENGTH=50;

difference() {
  union() {
    linear_extrude( BOX_H )
    difference(){
      offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
      offset( r= CORNER_RADIUS - WALL ) square( [BOX_W-WALL, BOX_L-WALL],  center=true );
    };

    coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];

    translate ( [-BOX_W/2, -BOX_L/2] )
    hull()
    for (i = coordinates)
      translate(i) sphere(CORNER_RADIUS);

    translate([BOX_W/-2+WALL,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

    translate([BOX_W/2-WALL*1.8,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

    // mic channel cover
    translate([0,-17,WALL-1])
    rotate([90,0,0])
    #linear_extrude(22.2) square([6.1,1.0], center=true);
    
    // keel
    translate([0,32.5,-5])
    rotate([90,0,0])
    #linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_HEIGHT], center=true); 

    // Inverted L-shaped C-clamp
    difference() {
      translate([KEEL_WIDTH/2-2, KEEL_LENGTH-18, -0.5])
      rotate([90, 0, 0])
      union() {
        // Vertical arm of the C-clamp 2
        translate([0, 0, 0]) cube([1, 5, 8]);
        // Horizontal arm of the C-clamp
        rotate([90, 0, 0])
        translate([-1.5, 0, -5]) cube([1.5, 8, 1]);
          
        // Vertical arm of the C-clamp 1
        translate([-6, 0, 0]) cube([1, 5, 8]);
        // Horizontal arm of the C-clamp
        rotate([90, 0, 0])
        translate([-5, 0,-5]) cube([1.5, 8, 1]);


        // Horizontal arm of the C-clamp
        //rotate([90, 0, 0])
        //translate([-5, 0, -5]) cube([5, 5, 1]);
      }
      // Cable hole
      //translate([0, 0, -1]) cylinder(h=4, r=0.8, center=true);
    }
  }
}
