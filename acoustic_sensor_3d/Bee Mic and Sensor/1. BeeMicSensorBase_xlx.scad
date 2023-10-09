$fn=50;

// Box dimensions
BOX_W = 38;  // Box Width
BOX_L = 105; // Box Length
BOX_H = 1.0; // Box Height

// Mic channel cover dimensions
MIC_W = 6.1;
MIC_L = 23;
MIC_H = 1.0;

// Corner radius
CORNER_RADIUS = 1.0;

CENTER_OFFSET = -1;

WALL = 1.0;

difference() {
    union() {
        // Draw the box with rounded corners
        linear_extrude(height = BOX_H)
        offset(r = CORNER_RADIUS)
        square([BOX_W - (2*CORNER_RADIUS), BOX_L - (2*CORNER_RADIUS)], center = false);

        // Calculate the starting position of the mic channel cover to center it on the box's edge
        MIC_START_X = ((BOX_W - MIC_W) / 2)+CENTER_OFFSET; 

        // Draw the mic channel cover positioned at the edge of the box
        translate([MIC_START_X, BOX_L-1, 0]) // This will always position the mic channel at the edge
        cube([MIC_W, MIC_L, MIC_H]);

        // Lid rails
        RAIL_H = 3; // Rail height

        // Left rail
        translate([WALL-1, 0, BOX_H])
        cube([WALL, BOX_L - 2*WALL, RAIL_H]);

        // Right rail
        translate([BOX_W - 2*WALL-1, 0, BOX_H])
        cube([WALL, BOX_L - 2*WALL, RAIL_H]);

        // Mic studs
        translate([(BOX_W/2)+CENTER_OFFSET-4.5, BOX_L-10, 0]) cylinder(h=7, d=2.5); 
        translate([(BOX_W/2)+CENTER_OFFSET+4.5, BOX_L-10, 0]) cylinder(h=7, d=2.5); 

        // sensor mounts
        //(x,y,y)
        translate([((BOX_W/2)+CENTER_OFFSET-10), BOX_L-60, 0]) cylinder(h=7, d=1.8); 
        translate([(BOX_W/2)+CENTER_OFFSET, BOX_L-90, 0]) cylinder(h=7, d=1.8); 
        translate([((BOX_W/2)+CENTER_OFFSET+10), BOX_L-60, 0]) cylinder(h=7, d=1.8); 

        // cable runs
        //(x, y, z)
        translate([(BOX_W/2)+CENTER_OFFSET-12, 10, 0]) cylinder(h=7, d=2.5);
        translate([(BOX_W/2)+CENTER_OFFSET+12, 10, 0]) cylinder(h=7, d=2.5);

        translate([(BOX_W/2)+CENTER_OFFSET-7, 6, 0]) cylinder(h=7, d=2.5);
        translate([(BOX_W/2)+CENTER_OFFSET+7, 6, 0]) cylinder(h=7, d=2.5);   
    }

    // center cutout - vent in base of box
    translate([(BOX_W/2)+CENTER_OFFSET-1.0,20,-4])
    rotate([90,0,90])
    cube([30, 6, 2]);

    // mic vents
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+4, -2]) #cylinder(h=4, d=2.5); 
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+10, -2]) #cylinder(h=4, d=2.5); 
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+16, -2]) #cylinder(h=4, d=2.5);
 
    // screw holes
    translate([(BOX_W/2)+CENTER_OFFSET, 6, -2]) cylinder(h=4, d=2.9); 
    translate([(BOX_W/2)+CENTER_OFFSET, 56, -2]) cylinder(h=4, d=2.9);    
}


/*

CORNER_RADIUS = 1.0; // Radius of corners
WALL = 0.8;// Wall Thickness

SENSOR_MOUNT_OFFSET = -5;

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
        translate([0,-49.6,0])
        rotate([90,0,0])
        linear_extrude(23.0) square([6.1,2.0], center=true);
    }   
}    
        // sensor mounting studs
        translate([0, BOX_L, 0.0])
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
        translate([0, BOX_L, 0.0])
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
 
    // screw holes
    translate([0.0, -17.5, -2]) cylinder(h=4, d=2.9); 
    translate([0.0, 43, -2]) cylinder(h=4, d=2.9);    
    
    //translate([0.0, -37.5, -2]) cylinder(h=4, d=2.0);  
    
}
*/