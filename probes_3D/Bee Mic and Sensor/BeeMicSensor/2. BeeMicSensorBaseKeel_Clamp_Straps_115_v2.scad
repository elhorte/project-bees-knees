$fn=50;

KEEL_W=9.0;
KEEL_H=9.0;
KEEL_L=115;

module cable_clamp(y_position) {
    translate([1.5, y_position, 4.5]) {
        rotate([90, 0, 0]) {
            union() {
                // Vertical arm of the C-clamp 2
                translate([2.0, 0, 0]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([0, 0, -5]) cube([2, 8, 2]);
                // Vertical arm of the C-clamp 1
                translate([-7, 0, 0]) cube([2, 5, 8]);
                // Horizontal arm of the C-clamp
                rotate([90, 0, 0])
                translate([-5.0, 0,-5]) cube([2, 8, 2]);
                // clamp bed
                rotate([90, 0, 0])
                translate([-7.0, 0,-0]) cube([11, 8, 2]);
            }
        }
    }
}

module cutout_group(y_position) {
    translate([0, y_position, 0]) {
        
        // front of keel slope
        translate([-5, -KEEL_L-1, -3])
        rotate([-45, 0, 0])
        //(x, z, y)
        cube([10, 11, 8]); 

        //center cutout - vent
        translate([-1.0, -34.0, -5.0])
        rotate([90,0,0])
        //y, z, x
        cube([1.5, 10, 22]);

        // screw holes
        translate([0, -22, 0]) cylinder(h=5, d=2.8); 
        translate([0.0, -69, 0]) cylinder(h=5, d=2.8);   

        // thru slots for straps
        translate([-7.0, -32,-1]) cube([14, 18, 2]);       
        translate([-7.0, -92,-1]) cube([14, 18, 2]);
        
    }
}

// translate and rotate so model starts at 0, 0, 0
// someone tell me why this has to be done by hand?
translate([0, 0, KEEL_H/2]) {
    rotate([180, 180, 0]) { // Flipping the entire object along the Y axis
        difference() {
            union() {           
                // keel
                rotate([90,0,0])
                linear_extrude(KEEL_L) square([KEEL_W, KEEL_H], center=true); 
                // cable clamp
                cable_clamp(0);
                // measuring posts
                //translate([0,  MOUNT_HOLE_OFFSET+15, 0]) cylinder(h=7, d=1.0);            
                //translate([0, MOUNT_HOLE_OFFSET+30, 0]) cylinder(h=7, d=1.0);
            }
            
            cutout_group(-5);
            
            // rear of keel slope
            translate([-5, -1, -10])
            rotate([45, 0, 0])
            //(x, z, y)
            cube([10, 11, 8]);  
        }
    }
}

