$fn=75;

BOX_W = 40;
BOX_L = 100;
BOX_H = 2.0;

CORNER_RADIUS = 1.0;

WALL = 1.0;

SENSOR_MOUNT_OFFSET = 5;
MIC_MOUNT_OFFSET = 100;
CABLE_GUIDE_OFFSET = 42;

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
    translate([BOX_W/-2+WALL-0.6, BOX_L/-2+0.6, WALL+1]) 
    cube([WALL, BOX_L-(WALL*2)+0.9, 3]);
        
    translate([(BOX_W/2)-(WALL*1.8)+0.6, BOX_L/-2+0.6, WALL+1]) 
    cube([WALL,BOX_L-(WALL*2)+0.9,3]);
}

// Mic Channel Cover
module micChannelCover() {
    translate([0,-51.0, 1.0])
    rotate([90,0,0])
    linear_extrude(23.0) square([6.1,2], center=true);
}

// Mounting Studs
module mountingStuds() {
    // Mic Mounting Studs
    translate([0, MIC_MOUNT_OFFSET, 0.0])
    union() {
        translate([-4.5, -142.5, 0]) cylinder(h=7, d=2.8); 
        translate([4.5, -142.5, 0]) cylinder(h=7, d=2.8); 
    }
    
    // Sensor Mounting Studs and Cable Runs
    union() {
        // sensor mounts
        translate([-10, SENSOR_MOUNT_OFFSET+30, 0]) cylinder(h=7, d=1.5); 
        translate([0, SENSOR_MOUNT_OFFSET-0, 0]) cylinder(h=7, d=1.5); 
        translate([10, SENSOR_MOUNT_OFFSET+30, 0]) cylinder(h=7, d=1.5); 
        // cable guides
        //translate([-11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
        //translate([11, CABLE_GUIDE_OFFSET-0, 0]) cylinder(h=7, d=2.5);
        //translate([-6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5);
        //translate([6, CABLE_GUIDE_OFFSET+7, 0]) cylinder(h=7, d=2.5); 
    }
}

// Cutouts
module cutouts() {
    // Center Vent y,x,z
    translate([-1.5, 10,-2])
    cube([3, 22, 6]);

    // Mic Vents
    for(pos = [-59, -64, -69])
        translate([0.0, pos, -1]) cylinder(h=4, d=2.5); 

    // Screw Holes
    for(pos = [-2, 45])
        translate([0.0, pos, -1]) cylinder(h=4, d=2.9);
}

// Combine modules
rotate([180, 180, -90]) {
    translate([0, -BOX_L/2, 0]) {
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
