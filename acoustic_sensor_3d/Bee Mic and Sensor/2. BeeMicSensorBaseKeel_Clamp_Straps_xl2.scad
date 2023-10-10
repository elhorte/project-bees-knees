$fn=50;
//SCREW_SIZE = .5; // Screw size in mm
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

KEEL_WIDTH=9.0;
KEEL_HEIGHT=9.0;
KEEL_LENGTH=110;

VENT_OFFSET = 2.5;
VENT_L = 16.5;
VENT_R = -18.5;

MOUNT_HOLE_OFFSET = 9;
difference() {
    union() {
        // measuring posts
        //translate([0,  MOUNT_HOLE_OFFSET+15, 0]) cylinder(h=7, d=1.0);            
        //translate([0, MOUNT_HOLE_OFFSET+30, 0]) cylinder(h=7, d=1.0);
        
        // keel
        translate([0,62.5,-5])
        rotate([90,0,0])
        difference() {
            linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_HEIGHT], center=true); 
            // front of keel slope
            //(x, z, y
            translate([-5, -5, 102.5])
            rotate([45, 0, 0])
            cube([10, 11, 8]);  
            
            // back of keel slope
            translate([-5, -10, 1])
            rotate([-45, 0, 0])
            cube([10, 11, 8]); 
            
            //center cutout - vent
            // y, z, x
            translate([-1.0,-6, 39.0])
            rotate([0,0,0])
            //y, z, x
            cube([1.5, 12, 27]);
            
            // screw holes
            rotate([90,0,0])
            union() {
                // x,y,z
                //translate([0.0, KEEL_LENGTH-35.0, -4.6]) #cylinder(h=4, d=2.8); 
                translate([0.0, KEEL_LENGTH-36.0, -4.6]) cylinder(h=4, d=2.8); 
                translate([0.0, KEEL_LENGTH-86.5, -4.6]) cylinder(h=4, d=2.8);   
            }
            // thru slots for straps rear
            rotate([90, 0, 0])
            translate([-7.0, 25,-1]) 
            cube([14, 15, 2]);
            // thru slots for straps front            
            rotate([90, 0, 0])
            translate([-7.0, 77,-1]) 
            cube([14, 15, 2]);
            /*
            // convex bottom
            // (x,z,y
            translate([0,-16.4,4]) 
            #cylinder(h=92, d=25);
            */
        }
        // Inverted L-shaped C-clamp
        difference() {
            translate([KEEL_WIDTH/2-3, KEEL_LENGTH-25, -0.5])
            rotate([90, 0, 0])
            union(){
                // Vertical arm of the C-clamp 2
                translate([2.0, 0, 19]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([0, 19, -5]) cube([2, 8, 2]);
                // Vertical arm of the C-clamp 1
                translate([-7, 0, 19]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([-5.0, 19,-5]) cube([2, 8, 2]);
                // clamp bed
                rotate([90, 0, 0])
                translate([-7.0, 19,-0]) cube([11, 8, 2]);
            }
        }
    }
}

