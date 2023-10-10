$fn=50;

CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

KEEL_W=9.0;
KEEL_H=9.0;
KEEL_L=105;

VENT_OFFSET = 2.5;
VENT_L = 16.5;
VENT_R = -18.5;
 
difference() {
    union() {
        // keel
        rotate([90,0,0])
        linear_extrude(KEEL_L) square([KEEL_W, KEEL_H], center=true); 
            
        // Inverted L-shaped C-clamp
        translate([0, 0, 4.5])
        rotate([90, 0, 0])
        union() {
            // Vertical arm of the C-clamp 2
            //(x, y, z)
            translate([3.5, 0, 0]) cube([2, 5, 8]);
            // Horizontal arm of the C-clamp
            rotate([90, 0, 0]) translate([2, 0, -5]) cube([2, 8, 2]);
            
            // Vertical arm of the C-clamp 1
            translate([-5.5, 0, 0]) cube([2, 5, 8]);
            // Horizontal arm of the C-clamp
            rotate([90, 0, 0]) translate([-4, 0,-5]) cube([2, 8, 2]);
            
            // clamp bed
            rotate([90, 0, 0]) translate([-5.5, 0,-0]) cube([11, 8, 2]);
        }
    }
    
    // back of keel slope
    //(x, y, z)
    translate([-5, -1, -11])
    rotate([45, 0, 0])
    cube([10, 11, 8]);  
    
    // front of keel slope
    translate([-5, -KEEL_L-6, -3])
    rotate([-45, 0, 0])
    cube([10, 11, 8]); 
    
    //center cutout - vent
    // x, y, z
    translate([-1.0, -39, -6])
    rotate([90,0,0])
    //y, z, x
    cube([1.5, 12, 27]);
    
    // screw holes
    rotate([0,0,0])
    union() {
        // (x,y,z)
        //translate([0.0, KEEL_LENGTH-35.0, -4.6]) #cylinder(h=4, d=2.8); 
        translate([0.0, -83, 1]) cylinder(h=4, d=2.8); 
        translate([0.0, -22.5, 1]) cylinder(h=4, d=2.8);   
    }
    
    // thru slots for straps
    rotate([0, 0, 0])
    translate([-7.0, -80,-1]) cube([14, 15, 2]);
    rotate([0, 0, 0])
    translate([-7.0, -40,-1]) cube([14, 15, 2]);
}

