

module hollowBoxWithRoundedCorners(height, width, length, wall_thickness, corner_radius, x_offset=0, y_offset=0) {
    translate([x_offset, y_offset, 0])
    difference() {
        // Outer rounded box
        hull() {
            for (x = [0, length - corner_radius * 2])
                for (y = [0, width - corner_radius * 2])
                    for (z = [0, height - corner_radius * 2])
                        translate([x + corner_radius, y + corner_radius, z + corner_radius])
                            sphere(corner_radius);
        }

        // Inner cavity to make the box hollow
        translate([wall_thickness, wall_thickness, wall_thickness])
        hull() {
            for (x = [0, length - wall_thickness * 2 - corner_radius * 2])
                for (y = [0, width - wall_thickness * 2 - corner_radius * 2])
                    for (z = [0, height - wall_thickness * 2 - corner_radius * 2])
                        translate([x + corner_radius, y + corner_radius, z + corner_radius])
                            sphere(corner_radius);
        }

        // Removing the bottom
        translate([0, 0, 1])
        cube([length, width, wall_thickness]);
    }
}

module intersectionVolume(height1, width1, length1, x_offset1, y_offset1, height2, width2, length2, x_offset2, y_offset2) {
    intersection() {
        translate([x_offset1, y_offset1, 0])
        cube([length1, width1, height1]);

        translate([x_offset2, y_offset2, 0])
        cube([length2, width2, height2]);
    }
}

// Define the positions of the boxes
x_offset1 = 0;
y_offset1 = 0;
x_offset2 = 59;
y_offset2 = 0;

// First box without bottom
hollowBoxWithRoundedCorners(12, 40, 60, 1, 1, x_offset1, y_offset1);

// Second box without bottom
hollowBoxWithRoundedCorners(4, 40, 40, 1, 1, x_offset2, y_offset2);

// Remove the intersection
difference() {
    union() {
        hollowBoxWithRoundedCorners(12, 40, 60, 1, 1, x_offset1, y_offset1);
        hollowBoxWithRoundedCorners(4, 40, 40, 1, 1, x_offset2, y_offset2);
    }
    intersectionVolume(12, 40, 60, x_offset1, y_offset1, 4, 40, 40, x_offset2, y_offset2);
}
