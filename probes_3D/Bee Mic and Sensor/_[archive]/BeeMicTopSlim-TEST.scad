$fn=50;
BOX_W = 38; // Box Width
BOX_L = 86;// Box Length
BOX_H = 6.5; // Box Height
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

MIC_OUTSIDE_WIDTH=8.3;
MIC_OUTSIDE_HEIGHT=9.0;
MIC_INSIDE_WIDTH=6.3;
MIC_LENGTH=23;

CON_OUTSIDE=5;
CON_INSIDE=4;
CON_LENGTH=3;

MIC_OFFSET_X = 0;
MIC_OFFSET_Y = -26.0;
MIC_OFFSET_Z = 0;



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
            // outside shape
            translate([0,-18.0,BOX_H-3])
            rotate([90,0,0])
            #linear_extrude(MIC_LENGTH) square([MIC_OUTSIDE_WIDTH,MIC_OUTSIDE_HEIGHT], center=true);
        }
    }
    translate([MIC_OFFSET_X, MIC_OFFSET_Y, MIC_OFFSET_Z]){
        // inside mio channel
        translate([0,-13.8,BOX_H-0.2]) // inside
        rotate([90,0,0])
        linear_extrude(MIC_LENGTH+3.1) square([MIC_INSIDE_WIDTH,MIC_OUTSIDE_HEIGHT], center=true); 
        
        // mic lid clearance
        translate([0,-17.25,BOX_H+1.11])
        rotate([90,0,0])
        linear_extrude(2.0) square([9,2.2], center=true);   
        
        // mic lid clearance
        translate([0,-17.25,BOX_H+1.11])
        rotate([90,0,0])
        linear_extrude(2.0) square([9,2.2], center=true);
    }

    translate([0,19.3,BOX_H-1])
    rotate([90,0,0])
    //cylinder(h=CON_LENGTH+1,r=CON_INSIDE/2);
    linear_extrude(2.0) square([6,3], center=true);
}