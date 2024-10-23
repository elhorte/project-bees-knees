$fn=75;

BOX_W = 40;
BOX_L = 100;
BOX_H = 12;
BATT_H = 3.0;
WALL = 1.1;
CORNER_RADIUS = 1.0;

MIC_OUTSIDE_W=8.3;
MIC_OUTSIDE_H=14;
MIC_INSIDE_W=6.3;
MIC_L=27.5;

module roundedRectangle(width, length, radius) {
    difference() {
        offset(r=radius) square([width, length], center=true);
        offset(r=radius-WALL) square([width-WALL, length-WALL], center=true);
    }
}

module mainLid() {
    // sides of box
    linear_extrude(BOX_H)
    roundedRectangle(BOX_W, BOX_L, CORNER_RADIUS);
    // base of box
    translate([0, 0, BOX_H-WALL]) {
        linear_extrude(WALL) square([BOX_W, BOX_L], center=true);
    }
    
    // backwall on top of battery platform
    translate([0, 9, 7.0]) {
        rotate([90, 90, 0])
        #linear_extrude(WALL) square([8, 41.5], center=true);    
    }
    
    // battery platform
    translate([0, 28.9, 2]) {
        #linear_extrude(WALL) square([40, 42], center=true);
    }
}

module micBox() {
    translate([0, -50.5, 5.0]) //y,x,z
    rotate([90, 0, 0])
    linear_extrude(MIC_L) square([MIC_OUTSIDE_W, MIC_OUTSIDE_H], center=true);
}

module cutouts() {
    // Inside mic channel
    translate([45, 0, 2])
    rotate([90, 0, 90])  // x,y,z
    #linear_extrude(MIC_L  +4.1) square([MIC_INSIDE_W, 10], center=true);
      
    // front of keel slope
    translate([65, 4.5, 15]) // x, y, z
    rotate([-45, 0, -90])
    //(y, z, x)
    #cube([10, 21, 8]); 
    
    // battery platform
    translate([-30, 0, 3.0])
    rotate([0, 0, 0])
    linear_extrude(10.0) square([42, 42], center=true);
    /*
    // Cable exit
    translate([0, -51.0, BOX_H-18.5])
    rotate([90, 0, 0])
    #linear_extrude(3.0) square([10, 6], center=true);
    */
}

// put it all together x,y,z
rotate([180, 0, 0]){
    translate([50, 0, -12]) { // offset model to start on 0, 0, 0
        difference() {
            rotate([180, 180, 270]) { // Flipping the entire object along the X axis
                union() {
                    // y, x, z
                    translate([0, 0, 0]) { 
                        mainLid();
                        micBox();
                    }
                }
            }
            cutouts();
        }
    }
}
