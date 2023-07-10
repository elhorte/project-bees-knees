$fn=50; // Sets the number of fragments for rounded shapes. Increase for better resolution.
BOX_W = 8.0; // Box Width
BOX_L = 30;// Box Length
BOX_H = 10.0; // Box Height

module rectangle(width, height, length) {
    cube([width, length, height], center=true);
}

// Call the module to create four rectangular objects, each 10mm apart.
for (i=[0:3]) {
    translate([i*(BOX_W+10), 0, 0]) {
        rectangle(BOX_W, BOX_H, BOX_L);
    }
}
