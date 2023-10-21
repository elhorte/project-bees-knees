$fn=50;

BOX_W = 38;
BOX_L = 105;
BOX_H = 8.0;
WALL = 0.5;
CORNER_RADIUS = 0.5;

MIC_OUTSIDE_WIDTH=8.3;
MIC_OUTSIDE_HEIGHT=10.0;
MIC_INSIDE_WIDTH=6.3;
MIC_LENGTH=24.5;

MIC_OFFSET_X = 0;
MIC_OFFSET_Y = -34.0;
MIC_OFFSET_Z = 0;

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
        translate([0, -53.0, 3])
        rotate([90, 0, 0])
        linear_extrude(MIC_LENGTH) square([MIC_OUTSIDE_WIDTH, MIC_OUTSIDE_HEIGHT], center=true);
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
        translate([0, -13.8, BOX_H+3])
        rotate([90, 0, 0])
        linear_extrude(MIC_LENGTH+4.1) square([MIC_INSIDE_WIDTH, MIC_OUTSIDE_HEIGHT], center=true);
        
        // Mic lid clearance at mic box opening
        translate([0, -17, BOX_H-0.10])
        rotate([90, 0, 0])
        linear_extrude(2.0) square([9, 2.2], center=true);
    }

    // Cable exit
    translate([0, 54.0, BOX_H+2.5])
    rotate([90, 0, 0])
    linear_extrude(3.0) square([10, 6], center=true);

    /*
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
    */
}

difference() {
    union() {
        translate([0, 0, 9.0]) { // Moving the lid to the opposite side of the base frame
            mainLid();
            micBox();
        }
    }
    cutouts();
}
