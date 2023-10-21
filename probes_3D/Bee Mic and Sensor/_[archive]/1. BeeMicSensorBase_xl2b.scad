$fn=50;

BOX_W = 38; // Box Width
BOX_L = 105;// Box Length
BOX_H = 1.0; // Box Height
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

SENSOR_MOUNT_OFFSET = 7.5;
MIC_MOUNT_OFFSET = 100;
CABLE_GUIDE_OFFSET = 40;

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
        translate([BOX_W/-2+WALL-0.5, BOX_L/-2+0.6, WALL]) 
        cube([WALL, BOX_L-(WALL*2)+0.9, 3]);
        
        translate([(BOX_W/2)-(WALL*1.8)+0.5, BOX_L/-2+0.6,WALL]) 
        cube([WALL,BOX_L-(WALL*2)+0.9,3]);

        // mic channel cover
        translate([0,-52.8, 0])
        rotate([90,0,0])
        linear_extrude(23.0) square([6.1,2], center=true);

        // mic mounting studs
        translate([0, MIC_MOUNT_OFFSET, 0.0])
        union() {
            translate([-4.5, -142.5, 0]) cylinder(h=7, d=2.3); 
            translate([4.5, -142.5, 0]) cylinder(h=7, d=2.3); 
        }
        
        // sensor mounting studs
        union(){
            // sensor mounts
            translate([-10, SENSOR_MOUNT_OFFSET-0, 0]) cylinder(h=7, d=1.5); 
            translate([0, SENSOR_MOUNT_OFFSET+30, 0]) cylinder(h=7, d=1.5); 
            translate([10, SENSOR_MOUNT_OFFSET-0, 0]) cylinder(h=7, d=1.5); 
            
            // cable runs
            translate([-11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
            translate([11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
            translate([-6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5);
            translate([6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5); 
         
            /// measuring posts ///
            //translate([0, SENSOR_MOUNT_OFFSET-98.0, 0]) cylinder(h=7, d=1.0);            
            //translate([0, SENSOR_MOUNT_OFFSET-48.0, 0]) cylinder(h=7, d=1.0);   
        } 
    }
    
    //
    // ==============  Cut outs ======================================================
    //
    
    // center cutout - vent in base of box
    translate([-1.0, 0,-4])
    rotate([90,0,90])
    cube([30, 6, 2]);

    // mic vents
    translate([0.0, -62, -2]) cylinder(h=4, d=2.5); 
    translate([0.0, -67, -2]) cylinder(h=4, d=2.5); 
    translate([0.0, -72, -2]) cylinder(h=4, d=2.5);

    // screw holes
    translate([0.0, -5, -2]) cylinder(h=4, d=2.9); 
    translate([0.0, 45, -2]) cylinder(h=4, d=2.9);    
}
