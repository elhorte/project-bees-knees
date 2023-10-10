$fn=50;
BOX_W = 38; // Box Width
BOX_L = 105;// Box Length
BOX_H = 8.0; // Box Height
CORNER_RADIUS = 0.8; // Radius of corners
WALL = 0.8;// Wall Thickness all sides

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

difference() {
    union() {
        linear_extrude( BOX_H )
        difference(){
            offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
            offset(r= CORNER_RADIUS - WALL) square([BOX_W-WALL, BOX_L-WALL], center=true );
        };
        coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];
        translate ( [-BOX_W/2, -BOX_L/2] )
            hull()
            for (i = coordinates)
            translate(i) sphere(CORNER_RADIUS);
            
        translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]){
            // mic box
            translate([0,-18.0,BOX_H-3])
            rotate([90,0,0])
            linear_extrude(MIC_LENGTH)square([MIC_OUTSIDE_WIDTH,MIC_OUTSIDE_HEIGHT], center=true);
        }
    }
    translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]){
        // inside mic channel
        translate([0,-13.8,BOX_H-0.2]) // inside
        rotate([90,0,0])
        linear_extrude(MIC_LENGTH+3.1) square([MIC_INSIDE_WIDTH,MIC_OUTSIDE_HEIGHT], center=true); 
        
        // mic lid clearance at mic box opening
        translate([0,-17,BOX_H+1.60])
        rotate([90,0,0])
        linear_extrude(2.0) square([9,2.2], center=true);   
    }
    // cable exit
    translate([0,54.0,BOX_H-2.5])
    rotate([90,0,0])
    #linear_extrude(3.0) square([10,6], center=true);
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

/*
// save for archiving

module waterdrop() {
    difference(){
        // Main drop shape
        # cylinder(r1=0, r2=0.1875, h=0.375, center=false);
        
        // To subtract from the base to make it rounded like a waterdrop
        translate([0, 0, -0.05])
        sphere(r=0.1875);
    }
}

for(i=[0:2]){
    translate([i*0.5, 0, 0]){
        waterdrop();
    }
}
*/