$fn=75;

BOX_W = 38;
BOX_L = 105;
BOX_H = 8.5;

WALL = 0.8;

CORNER_RADIUS = 0.8;

MIC_OUTSIDE_W=8.3;
MIC_OUTSIDE_H=10.5;

MIC_INSIDE_W=6.3;
MIC_L=27.5;

MIC_OFFSET_X = 0;
MIC_OFFSET_Y = -33.4;
MIC_OFFSET_Z = -0.9;

VENT_OFFSET = -4.5;
VENT_L = 19.0;
VENT_R = -19.0;

module roundedRectangle(width, length, radius) {
    difference() {
        offset(r=radius) square([width, length], center=true);
        offset(r=radius - WALL) square([width - WALL, length - WALL], center=true);
    }
}

module mainLid() {
    // sides of box
    linear_extrude(BOX_H)
    roundedRectangle(BOX_W, BOX_L, CORNER_RADIUS);
    // base of box
    translate([0, 0, BOX_H - WALL]) {
        linear_extrude(WALL) square([BOX_W, BOX_L], center=true);
    }
}

module micBox() {
        translate([0, -53.2, 3.2])
        rotate([90, 0, 0])
        linear_extrude(MIC_L) square([MIC_OUTSIDE_W, MIC_OUTSIDE_H], center=true);
    }
//}

module vent(x, y, vent_offset) {
    translate([x, y, BOX_H + vent_offset]) {
        rotate([90, 0, 90]) {
            cylinder(h=3.0, d=2.0, center=true);
        }
    }
}

module cutouts() {
    translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]) {
        // Inside mic channel
        translate([0, +110, BOX_H-18])
        rotate([90, 0, 0])
        linear_extrude(MIC_L  +4.1) square([MIC_INSIDE_W, MIC_OUTSIDE_H], center=true);
        
        // Mic lid clearance at mic box opening
        //translate([0, -17, BOX_H-0.10])
        //rotate([90, 0, 0])
        //linear_extrude(2.0) square([9, 2.2], center=true);
    }

    // Cable exit
    translate([0, -51.0, BOX_H-18.5])
    rotate([90, 0, 0])
    linear_extrude(3.0) square([10, 6], center=true);
    
    // front of keel slope
    translate([-5, BOX_L-26, -23.5])
    rotate([45, 0, 0])
    //(x, z, y)
    #cube([10, 11, 8]); 
}

// put it all together
translate([0, 53, 17]) { // offset model to start on 0, 0, 0
    difference() {
        rotate([180, 0, 0]) { // Flipping the entire object along the X axis
            union() {
                translate([0, 0, 9.0]) { 
                    mainLid();
                    micBox();
                }
            }
        }
        cutouts();
    }
}
