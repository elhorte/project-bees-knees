$fn=50;
BOX_W = 38; // Box Width
BOX_L = 86;// Box Length
BOX_H = 1.0; // Box Height
//SCREW_SIZE = .5; // Screw size in mm
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

KEEL_WIDTH=9.0;
KEEL_HEIGHT=9.0;
KEEL_LENGTH=100;

VENT_OFFSET = 2.5;
VENT_L = 16.5;
VENT_R = -18.5;

module vent(x, y, vent_offset) {
    translate([x, y, BOX_H + vent_offset]) {
        rotate([90, 0, 90]) {
            #linear_extrude(2.5) square([6, 4], center=true);
        }
    }
}
    
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
    
        // lid rail
        translate([BOX_W/-2+WALL,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

        // lid rail
        translate([BOX_W/2-WALL*1.8,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

        // mic channel cover
        // x, y, z
        translate([0,-44.0,WALL-0.7])
        rotate([90,0,0])
        #linear_extrude(20.0) square([6.1,1.5], center=true);

        // mic mounting studs
        difference() {
            translate([0, KEEL_LENGTH, 0.0])
            
            //rotate([0, 0, 0])
            union() {
                // mounting stud for sensor
                // x, z, y
                translate([-4.5, -133, 0]) cylinder(h=5, d=3); 
                translate([4.5, -133, 0]) cylinder(h=5, d=3); 
            }
        }
 
        // keel
        translate([0,62.5,-5])
        rotate([90,0,0])

        difference() {
            linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_HEIGHT], center=true); 
            // back of keel slope
            translate([-5, -10, 1])
            rotate([-45, 0, 0])
            #cube([10, 11, 8]); 
            // front of keeo slope
            translate([-5, -5, 93])
            rotate([45, 0, 0])
            #cube([10, 11, 8]);          
        }
        
        // sensor mounting studs
        difference() {
            translate([0, KEEL_LENGTH, 0.0])
            //rotate([0, 0, 0])
            union() {
                // mounting stud for sensor
                // x, z, y
                translate([0, -105, 0]) cylinder(h=5, d=1.8); 
                translate([-10, -75, 0]) cylinder(h=5, d=1.8); 
                translate([10, -75, 0]) cylinder(h=5, d=1.8); 
            }
        }
          
        // Inverted L-shaped C-clamp
        difference() {
            translate([KEEL_WIDTH/2-3, KEEL_LENGTH-18, -0.5])
            rotate([90, 0, 0])
            union() {
                // Vertical arm of the C-clamp 2
                // x, z, y
                translate([2.0, 0, 21]) cube([1, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([0, 21, -5]) cube([2, 8, 1]);
                  
                // Vertical arm of the C-clamp 1
                translate([-6, 0, 21]) cube([1, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([-5.0, 21,-5]) cube([2, 8, 1]);
            }
        }
    }
    
    // gas sensor vents
    vent(VENT_L, 29.0, VENT_OFFSET);
    vent(VENT_L, 21.0, VENT_OFFSET);
    vent(VENT_L, 13.0, VENT_OFFSET);
    vent(VENT_L, 5.0, VENT_OFFSET);
    vent(VENT_L, -3.0, VENT_OFFSET);
    vent(VENT_L, -11.0, VENT_OFFSET);
    
    vent(VENT_R, 29.0, VENT_OFFSET);
    vent(VENT_R, 21.0, VENT_OFFSET);
    vent(VENT_R, 13.0, VENT_OFFSET);
    vent(VENT_R, 5.0, VENT_OFFSET);
    vent(VENT_R, -3.0, VENT_OFFSET);
    vent(VENT_R, -11.0, VENT_OFFSET);   
    
}
