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

module cutouts() {
    translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]) {
        // Inside mic channel
        translate([0, +110, BOX_H-18])
        rotate([90, 0, 0])
        linear_extrude(MIC_LENGTH+4.1) square([MIC_INSIDE_WIDTH, MIC_OUTSIDE_HEIGHT], center=true);
    }

    // Cable exit
    translate([0, -51.0, BOX_H-18.5])
    rotate([90, 0, 0])
    #linear_extrude(3.0) square([10, 6], center=true);
}

difference() {
    rotate([180, 0, 0]) { // Flipping the entire object along the X axis
        union() {
            translate([0, 0, 9.0]) { // Moving the lid to the opposite side of the base frame
                translate([-BOX_W/2, BOX_L/2, -BOX_H]) { // Shifting the center of the back to (0,0,0)
                    mainLid();
                    micBox();
                }
            }
        }
    }
    cutouts();
}
