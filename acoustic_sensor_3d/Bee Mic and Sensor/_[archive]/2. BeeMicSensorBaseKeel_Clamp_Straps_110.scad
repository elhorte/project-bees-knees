$fn=50;

KEEL_W=9.0;
KEEL_H=9.0;
KEEL_L=110;

difference() {
    union() {
        // measuring posts
        //translate([0,  MOUNT_HOLE_OFFSET+15, 0]) cylinder(h=7, d=1.0);            
        //translate([0, MOUNT_HOLE_OFFSET+30, 0]) cylinder(h=7, d=1.0);
        
        // keel
        rotate([90,0,0])
        linear_extrude(KEEL_L) square([KEEL_W, KEEL_H], center=true); 
        // cable clamp
        translate([1.5, 4, 4.5])
        rotate([90, 0, 0])
        union(){
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
    
    // front of keel slope
    translate([-5, -KEEL_L-6, -3])
    rotate([-45, 0, 0])
    //(x, z, y)
    cube([10, 11, 8]); 
    
    // rear of keel slope
    translate([-5, -1, -10])
    rotate([45, 0, 0])
    //(x, z, y)
    cube([10, 11, 8]);  
 
    //center cutout - vent
    translate([-1.0, -42.0, -5.0])
    rotate([90,0,0])
    //y, z, x
    cube([1.5, 10, 25]);
    
    // screw holes
    translate([0, -22, 0]) cylinder(h=5, d=2.8); 
    translate([0.0, -72, 0]) cylinder(h=5, d=2.8);   

    // thru slots for straps
    translate([-7.0, -42,-1]) cube([14, 18, 2]);       
    translate([-7.0, -92,-1]) cube([14, 18, 2]);
}

