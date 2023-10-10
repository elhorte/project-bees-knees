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

        // Calculate the starting position of the mic channel cover
        MIC_START_X = ((BOX_W - MIC_W) / 2)+CENTER_OFFSET; 

        // Draw the mic channel cover positioned at the edge of the box
        translate([MIC_START_X, BOX_L-1, 0]) 
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
        translate([(BOX_W/2)+CENTER_OFFSET-4.5, BOX_L-10, 0]) cylinder(h=7, d=2.3); 
        translate([(BOX_W/2)+CENTER_OFFSET+4.5, BOX_L-10, 0]) cylinder(h=7, d=2.3); 

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
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+4, -2]) cylinder(h=4, d=2.5); 
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+10, -2]) cylinder(h=4, d=2.5); 
    translate([(BOX_W/2)+CENTER_OFFSET, BOX_L+16, -2]) cylinder(h=4, d=2.5);
 
    // screw holes
    translate([(BOX_W/2)+CENTER_OFFSET, 6, -2]) cylinder(h=4, d=2.9); 
    translate([(BOX_W/2)+CENTER_OFFSET, 56, -2]) cylinder(h=4, d=2.9);    
}

