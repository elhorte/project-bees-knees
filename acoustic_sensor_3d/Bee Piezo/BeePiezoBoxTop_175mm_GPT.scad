$fn=50;

// Lid exterior dimensions
LID_W = 32; // Lid Width, the width of the box plus twice the wall thickness
LID_L = 179; // Lid Length, the length of the box plus twice the wall thickness
LID_H = 2; // Lid Height

// Runners dimensions
RUNNER_W = 2; // Runner Width
RUNNER_L = LID_L - 4; // Runner Length, slightly less than lid length to avoid overhang
RUNNER_H = 2; // Runner Height, same as wall thickness

// Wall thickness
WALL_THICKNESS = 2;

union() {
    // Create the lid
    translate([0, 0, RUNNER_H/2])
        cube([LID_W, LID_L, LID_H], center=true);

    // Add runners under the lid
    translate([-LID_W/2 + RUNNER_W/2 + WALL_THICKNESS, 0, -RUNNER_H/2])
        cube([RUNNER_W, RUNNER_L, RUNNER_H], center=true);

    translate([LID_W/2 - RUNNER_W/2 - WALL_THICKNESS, 0, -RUNNER_H/2])
        #cube([RUNNER_W, RUNNER_L, RUNNER_H], center=true);
}
