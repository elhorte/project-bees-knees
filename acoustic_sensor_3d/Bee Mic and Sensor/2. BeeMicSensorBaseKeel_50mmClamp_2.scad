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
            translate([-1.0,-5, 40])
            rotate([0,0,0])
            //y, z, x
            #cube([1.5, 12, 25]);
            
            // screw holes
            rotate([90,0,0])
            union() {
                // x,y,z
                //translate([0.0, KEEL_LENGTH-35.0, -4.6]) #cylinder(h=4, d=2.8); 
                translate([0.0, KEEL_LENGTH-24.5, -4.6]) #cylinder(h=4, d=2.8); 
                translate([0.0, KEEL_LENGTH-77.5, -4.6]) #cylinder(h=4, d=2.8);   
            }
        }
        // Inverted L-shaped C-clamp
        difference() {
            translate([KEEL_WIDTH/2-3, KEEL_LENGTH-18, -0.5])
            rotate([90, 0, 0])
            union() {
                // Vertical arm of the C-clamp 2
                translate([1.0, 0, 21]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([0, 21, -5]) cube([2, 8, 2]);
                  
                // Vertical arm of the C-clamp 1
                translate([-6, 0, 21]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([-5.0, 21,-5]) cube([2, 8, 2]);
            }
        }
    }
}

