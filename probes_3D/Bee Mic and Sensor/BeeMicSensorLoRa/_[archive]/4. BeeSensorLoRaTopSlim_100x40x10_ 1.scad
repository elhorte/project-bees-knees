

module roundedBox(height, width, length, wall_thickness, corner_radius, remove_bottom) {
    difference() {
        // Outer shape
        hull() {
            for (x = [0, length - corner_radius * 2])
                for (y = [0, width - corner_radius * 2])
                    for (z = [0, height - corner_radius * 2])
                        translate([x + corner_radius, y + corner_radius, z + corner_radius])
                            sphere(corner_radius);
        }

        // Inner shape (offset by wall thickness)
        translate([wall_thickness, wall_thickness, wall_thickness])
        hull() {
            for (x = [0, length - wall_thickness * 2 - corner_radius * 2])
                for (y = [0, width - wall_thickness * 2 - corner_radius * 2])
                    for (z = [0, height - wall_thickness * 2 - corner_radius * 2])
                        translate([x + corner_radius, y + corner_radius, z + corner_radius])
                            sphere(corner_radius);
        }

        // Remove bottom if required
        if (remove_bottom) {
            translate([-1, -1, -1])
            cube([length + 2, width + 2, wall_thickness]);
        }
    }
}

// First box without bottom
roundedBox(12, 40, 60, 1, 1, true);

translate([70, 0, 0]) // Move the second box to avoid overlap
// Second box without bottom
roundedBox(4, 40, 40, 1, 1, true);
