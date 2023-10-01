$fn=50;
BOX_W = 38; // Box Width
BOX_L = 100;// Box Length
BOX_H = 1.0; // Box Height
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 0.8;// Wall Thickness

SENSOR_MOUNT_OFFSET = -5;

KEEL_WIDTH=9.0;
KEEL_HEIGHT=10.0;
KEEL_LENGTH=100;

VENT_OFFSET = 2.5;
VENT_L = 16.5;
VENT_R = -18.5;
 
difference() {
    // main box shape
    union() {
        linear_extrude(BOX_H)
        difference(){
            offset(r=CORNER_RADIUS) square([BOX_W, BOX_L], center=true);
            offset(r=CORNER_RADIUS - WALL) square([BOX_W-WALL, BOX_L-WALL], center=true);
        };
        coordinates = [[0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0]];
        translate([-BOX_W/2, -BOX_L/2])
        hull()
        for (i = coordinates)
            translate(i) sphere(CORNER_RADIUS);
    
        // lid rails
        translate([BOX_W/-2+WALL,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);
        translate([BOX_W/2-WALL*1.8,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

        // mic channel cover
        translate([0,-49.6,WALL-1])
        rotate([90,0,0])
        linear_extrude(23.0) square([6.1,2.0], center=true);
        
        // sensor mounting studs
        translate([0, KEEL_LENGTH, 0.0])
        union() {
            // sensor mounts
            translate([-10, SENSOR_MOUNT_OFFSET-90, 0]) cylinder(h=7, d=1.8); 
            translate([0, SENSOR_MOUNT_OFFSET-60, 0]) cylinder(h=7, d=1.8); 
            translate([10, SENSOR_MOUNT_OFFSET-90, 0]) cylinder(h=7, d=1.8); 
            // cable runs
            translate([-11, -60, 0]) cylinder(h=7, d=2.5);
            translate([11, -60, 0]) cylinder(h=7, d=2.5);
            translate([-6, -52, 0]) cylinder(h=7, d=2.5);
            translate([6, -52, 0]) cylinder(h=7, d=2.5);            
        } 
        
        // mic mounting studs
        translate([0, KEEL_LENGTH, 0.0])
        union() {
            translate([-4.5, -140, 0]) cylinder(h=7, d=2.2); 
            translate([4.5, -140, 0]) cylinder(h=7, d=2.2); 
        }
    }
    //
    // ==============  Cut outs ======================================================
    //
    // center cutout - vent in base of box
    translate([-1.0,-2.5,-4])
    rotate([90,0,90])
    cube([30, 6, 2]);

    // mic vents
    translate([0.0, -57, -2]) cylinder(h=4, d=2.5); 
    translate([0.0, -62, -2]) cylinder(h=4, d=2.5); 
    translate([0.0, -67, -2]) cylinder(h=4, d=2.5);
/*
    // keel
    translate([0,62.5,-5])
    rotate([90,0,0])
    linear_extrude(KEEL_LENGTH) square([KEEL_WIDTH+0.5, KEEL_HEIGHT], center=true); 
*/    
    // screw holes
    translate([0.0, -17.5, -2]) cylinder(h=4, d=2.9); 
    translate([0.0, 43, -2]) cylinder(h=4, d=2.9);    
    
    //translate([0.0, -37.5, -2]) cylinder(h=4, d=2.0);  
    
}
