

module roundedBox(height, width, length, wall_thickness, corner_radius) {
    hull() {
        translate([corner_radius, corner_radius, corner_radius])
            sphere(corner_radius);
        translate([length - corner_radius, corner_radius, corner_radius])
            sphere(corner_radius);
        translate([corner_radius, width - corner_radius, corner_radius])
            sphere(corner_radius);
        translate([length - corner_radius, width - corner_radius, corner_radius])
            sphere(corner_radius);
        translate([corner_radius, corner_radius, height - corner_radius])
            sphere(corner_radius);
        translate([length - corner_radius, corner_radius, height - corner_radius])
            sphere(corner_radius);
        translate([corner_radius, width - corner_radius, height - corner_radius])
            sphere(corner_radius);
        translate([length - corner_radius, width - corner_radius, height - corner_radius])
            sphere(corner_radius);
    }
    
    translate([wall_thickness, wall_thickness, wall_thickness])
    hull() {
        translate([corner_radius, corner_radius, corner_radius])
            sphere(corner_radius);
        translate([length - wall_thickness*2 - corner_radius, corner_radius, corner_radius])
            sphere(corner_radius);
        translate([corner_radius, width - wall_thickness*2 - corner_radius, corner_radius])
            sphere(corner_radius);
        translate([length - wall_thickness*2 - corner_radius, width - wall_thickness*2 - corner_radius, corner_radius])
            sphere(corner_radius);
        translate([corner_radius, corner_radius, height - wall_thickness*2 - corner_radius])
            sphere(corner_radius);
        translate([length - wall_thickness*2 - corner_radius, corner_radius, height - wall_thickness*2 - corner_radius])
            sphere(corner_radius);
        translate([corner_radius, width - wall_thickness*2 - corner_radius, height - wall_thickness*2 - corner_radius])
            sphere(corner_radius);
        translate([length - wall_thickness*2 - corner_radius, width - wall_thickness*2 - corner_radius, height - wall_thickness*2 - corner_radius])
            sphere(corner_radius);
    }
}

difference() {
    roundedBox(12, 40, 60, 1, 1);
    translate([1, 1, 1])
    roundedBox(10, 38, 58, 1, 1);
}

translate([59, 0, 0]) // Move the second box to avoid overlap
difference() {
    roundedBox(4, 40, 40, 1, 1);
    translate([1, 1, 1])
    roundedBox(2, 38, 38, 1, 1);
}
