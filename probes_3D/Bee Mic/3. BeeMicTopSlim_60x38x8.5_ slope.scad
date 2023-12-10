$fn=75;

BOX_W = 38.4;
BOX_L = 60.4;
BOX_H = 8.5;

WALL = 1.0;

CORNER_RADIUS = 0.8;

MIC_OUTSIDE_W=8.3;
MIC_OUTSIDE_H=10.0;

MIC_INSIDE_W=6.3;
MIC_L=25.5;

MIC_OFFSET_X = 0;
MIC_OFFSET_Y = -20.4;
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
        translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]) {
            translate([0, -10.4, 3])
            rotate([90, 0, 0])
            linear_extrude(MIC_L) square([MIC_OUTSIDE_W, MIC_OUTSIDE_H], center=true);
        }
    }
//}


module cutouts() {
    rotate([180, 0, 0]) {   // Flipping the entire object along the X axis
        translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]) {
            // Inside mic channel
            translate([0, -3.5, BOX_H-8])
            rotate([90, 0, 0])
            linear_extrude(MIC_L+4.1) square([MIC_INSIDE_W, MIC_OUTSIDE_H], center=true);
        }
    }
    
    // front of keel slope
    translate([-5, MIC_L+29.0, -14])
    rotate([45, 0, 0])
    //(x, z, y)
    cube([10, 11, 8]); 
    
    // Cable exit
    translate([0, -29.0, BOX_H-9.5])
    rotate([90, 0, 0])
    linear_extrude(3.0) square([10, 6], center=true);
    

}

// put it all together
translate([0, 31, 8]) { // offset model to start on 0, 0, 0
    difference() {
        rotate([180, 0, 0]) { // Flipping the entire object along the X axis
            union() {
                mainLid();
                micBox();
            }
        }
        cutouts();
    }
}
