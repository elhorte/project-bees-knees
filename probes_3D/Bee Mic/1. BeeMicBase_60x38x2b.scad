$fn=75;

BOX_W = 38;
BOX_L = 60;
BOX_H = 2.0;

CORNER_RADIUS = 1.0;

WALL = 1.0;

SENSOR_MOUNT_OFFSET = 10;
MIC_MOUNT_OFFSET = -20;
CABLE_GUIDE_OFFSET = 20;
MIC_HOLE_OFFSET = -37;

module roundedRectangle(width, length, radius) {
    offset(r=radius) square([width, length], center=true);
}

// Main Box Shape
module mainBox() {
    linear_extrude(BOX_H)
    roundedRectangle(BOX_W, BOX_L, CORNER_RADIUS);
}

// Lid Rails
module lidRails() {
    translate([BOX_W/-2+WALL-0.4, BOX_L/-2+0.6, WALL+1]) 
    cube([WALL, BOX_L-(WALL*2)+0.7, 3]);
        
    translate([(BOX_W/2)-(WALL*2.0)+0.4, BOX_L/-2+0.6, WALL+1]) 
    cube([WALL,BOX_L-(WALL*2)+0.7,3]);
}

// Mic Channel Cover
module micChannelCover() {
    translate([0,-28.8, 1.0])
    rotate([90,0,0])
    linear_extrude(23.0) square([6.1,2], center=true);
}

// Mounting Studs
module mountingStuds() {
    // Mic Mounting Studs
    translate([0, MIC_MOUNT_OFFSET, 0.0])
    union() {
        translate([-4.5, 0, 0]) cylinder(h=7, d=2.3); 
        translate([4.5, 0, 0]) cylinder(h=7, d=2.3); 
    }
    
    // Sensor Mounting Studs and Cable Runs
    union() {
        // sensor mounts
        //translate([-10, SENSOR_MOUNT_OFFSET-0, 0]) cylinder(h=7, d=1.5); 
        //translate([0, SENSOR_MOUNT_OFFSET+30, 0]) cylinder(h=7, d=1.5); 
        //translate([10, SENSOR_MOUNT_OFFSET-0, 0]) cylinder(h=7, d=1.5); 
        // cable guides
        translate([-11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
        translate([11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
        translate([-6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5);
        translate([6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5); 
    }
}

// Cutouts
module cutouts() {
    // Mic Vents
    for(pos = [MIC_HOLE_OFFSET-0, MIC_HOLE_OFFSET-5, MIC_HOLE_OFFSET-10])
        translate([0.0, pos, -1]) cylinder(h=4, d=2.5); 

    // Screw Holes
    for(pos = [-15, 25])
        translate([0.0, pos, -1]) cylinder(h=4, d=2.9);
}

// Combine modules
rotate([180, 180, 0]) {
    translate([0, -BOX_L/2-1, 0]) {
        difference() {
            union() {
                mainBox();
                lidRails();
                micChannelCover();
                mountingStuds();
            }
            cutouts();
        }
    }
}
