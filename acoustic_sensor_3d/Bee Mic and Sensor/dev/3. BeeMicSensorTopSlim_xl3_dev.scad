$fn=50;
BOX_W = 38; // Box Width
BOX_L = 105;// Box Length
BOX_H = 8.0; // Box Height
CORNER_RADIUS = 0.8; // Radius of corners
WALL = 0.5;// Wall Thickness all sides

MIC_OUTSIDE_WIDTH=8.3;
MIC_OUTSIDE_HEIGHT=11.0;
MIC_INSIDE_WIDTH=6.3;
MIC_LENGTH=24.5;

CON_OUTSIDE=5;
CON_INSIDE=4;
CON_LENGTH=3;

MIC_OFFSET_X = 0;
MIC_OFFSET_Y = -34.5;
MIC_OFFSET_Z = -0.5;

VENT_OFFSET = -4.5;
VENT_L = 19.0;
VENT_R = -19.0;

module sq_vent(x, y, vent_offset) {
    translate([x, y, BOX_H + vent_offset]) {
        rotate([90, 0, 90]) {
            linear_extrude(2.5) square([2, 2], center=true);
        }
    }
}

module vent(x, y, vent_offset) {
    translate([x, y, BOX_H + vent_offset]) {
        rotate([90, 0, 90]) {
            cylinder(h=3.0, d=2.0, center=true);
        }
    }
}

module roundedRectangle(width, length, radius) {
    union() {
        linear_extrude( BOX_H )
        difference(){
            offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
            offset(r= CORNER_RADIUS - WALL) square([BOX_W-WALL, BOX_L-WALL], center=true );
        };
        coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];
        translate ( [-BOX_W/2, -BOX_L/2] ) {
            hull()
            for (i = coordinates)
            translate(i) sphere(CORNER_RADIUS);
        }
    }
}

module mainLid() {
    linear_extrude(BOX_H)
    roundedRectangle(BOX_W, BOX_L, CORNER_RADIUS);
}

difference() {
    union() {
        mainLid();
        micBox();
    }
    //cutouts();
}



