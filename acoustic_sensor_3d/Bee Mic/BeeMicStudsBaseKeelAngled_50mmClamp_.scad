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
    translate([0,-18.6,WALL-0.7])
    rotate([90,0,0])
    linear_extrude(20.0) square([6.1,1.5], center=true);
    
    // mic mounting studs
    difference() {
      translate([0, KEEL_LENGTH, 0.0])
            
      //rotate([0, 0, 0])
      union() {
        // mounting stud for sensor
        // x, z, y
        translate([-4.5, -57, 0]) cylinder(h=6, d=3); 
        translate([4.5, -57, 0]) cylinder(h=6, d=3); 
      }
    }
 
    // keel
    translate([0,37.5,-5])
    rotate([90,0,0])

    difference() {
      linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_HEIGHT], center=true); 
      // back of keel slope
      translate([-5, -10, 1])
      rotate([-45, 0, 0])
      cube([10, 11, 8]); 
      // front of keeo slope
      translate([-5, -5, 43])
      rotate([45, 0, 0])
      cube([10, 11, 8]);          
    }
      
      
    // Inverted L-shaped C-clamp
    difference() {
      translate([KEEL_WIDTH/2-2, KEEL_LENGTH-18, -0.5])
      rotate([90, 0, 0])
      union() {
        // Vertical arm of the C-clamp 2
        translate([0, 0, -4]) cube([1, 5, 8]);
        // Horizontal arm of the C-clamp
        rotate([90, 0, 0])
        translate([-1.5, -4, -5]) cube([1.5, 8, 1]);
          
        // Vertical arm of the C-clamp 1
        translate([-6, 0, -4]) cube([1, 5, 8]);
        // Horizontal arm of the C-clamp
        rotate([90, 0, 0])
        translate([-5, -4,-5]) cube([1.5, 8, 1]);
      }
    }
  }
}
