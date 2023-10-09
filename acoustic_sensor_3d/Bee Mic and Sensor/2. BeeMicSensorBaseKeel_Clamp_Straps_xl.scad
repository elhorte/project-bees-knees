$fn=50;
BOX_W = 38; // Box Width
BOX_L = 100;// Box Length
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
 
difference() {
    union() {
        // keel
        translate([0,62.5,-5])
        rotate([90,0,0])
        difference() {
            linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH, KEEL_HEIGHT], center=true); 
            // front of keel slope
            translate([-5, -5, 93])
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
                translate([0.0, KEEL_LENGTH-17.0, -4.6]) cylinder(h=4, d=2.8); // 83
                translate([0.0, KEEL_LENGTH-77.5, -4.6]) cylinder(h=4, d=2.8); // 22.5
            }
            // thru slots for straps
            rotate([90, 0, 0])
            translate([-7.0, 25,-1]) 
            cube([14, 15, 2]);
            rotate([90, 0, 0])
            translate([-7.0, 65,-1]) 
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
            translate([KEEL_WIDTH/2-3, KEEL_LENGTH-18, -0.5])
            rotate([90, 0, 0])
            union() {
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

