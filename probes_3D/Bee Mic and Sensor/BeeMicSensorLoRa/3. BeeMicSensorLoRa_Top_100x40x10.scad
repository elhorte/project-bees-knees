$fn=75;

BOX_W = 40;
BOX_L = 100;
BOX_H = 12;

WALL = 0.8;
CORNER_RADIUS = 0.8;

MIC_OUTSIDE_W=8.3;
MIC_OUTSIDE_H=10.5;
MIC_INSIDE_W=6.3;
MIC_L=27.5;

module roundedRectangle(width, length, radius) {
    difference() {
        offset(r=radius) square([width, length], center=true);
        offset(r=radius - WALL) square([width-WALL, length-WALL], center=true);
    }
}

module mainLid() {
    // sides of box
    linear_extrude(BOX_H)
    roundedRectangle(BOX_W, BOX_L, CORNER_RADIUS);
    // base of box
    translate([0, 0, BOX_H-WALL]) {
        linear_extrude(WALL) square([BOX_W, BOX_L], center=true);
    }
    
    // backwall on top of battery platform
    translate([0, 9, 8]) {
        rotate([90, 90, 0])
        #linear_extrude(1) square([7, 42], center=true);    
    }
    
    // battery platform
    translate([0, 29, 3.5]) {
        linear_extrude(1) square([40, 42], center=true);
    }
}

module micBox() {
    translate([0, -50.5, 4])
    rotate([90, 0, 0])
    linear_extrude(MIC_L) square([MIC_OUTSIDE_W, MIC_OUTSIDE_H], center=true);
}

/*
module vent(x, y, vent_offset) {
    translate([x, y, BOX_H + vent_offset]) {
        rotate([90, 0, 90]) {
            cylinder(h=3.0, d=2.0, center=true);
        }
    }
}
*/
module cutouts() {
    translate([45, 0, 3])
    // Inside mic channel
    rotate([90, 0, 90])  // x,y,z
    #linear_extrude(MIC_L  +4.1) square([MIC_INSIDE_W, MIC_OUTSIDE_H], center=true);
      
    // front of keel slope
    translate([72, 4.5, 10])
    rotate([-45, 0, -90])
    //(x, z, y)
    #cube([10, 11, 8]); 
    
    // battery platform
    translate([-30, 0, 4.5])
    rotate([0, 0, 0])
    linear_extrude(10.0) square([42, 42], center=true);

    // Cable exit
    translate([0, -51.0, BOX_H-18.5])
    rotate([90, 0, 0])
    #linear_extrude(3.0) square([10, 6], center=true);
}

// put it all together x,y,z
translate([50, 0, 0]) { // offset model to start on 0, 0, 0
    difference() {
        rotate([180, 180, 270]) { // Flipping the entire object along the X axis
            union() {
                // y, x, z
                translate([0, 0, 0]) { 
                    mainLid();
                    micBox();
                }
            }
        }
        cutouts();
    }
}
