$fn=50;
BOX_W = 38; // Box Width
BOX_L = 86;// Box Length
BOX_H = 1.0; // Box Height
//SCREW_SIZE = .5; // Screw size in mm
CORNER_RADIUS = 1.0; // Radius of corners
WALL = 1.0;// Wall Thickness

KEEL_WIDTH=9.0;
KEEL_HEIGHT=9.0;
KEEL_LENGTH=100;

VENT_OFFSET = 2.5;
VENT_L = 16.5;
VENT_R = -18.5;
 
difference() {
    // main box shape
    union() {
        linear_extrude( BOX_H )
        difference(){
            offset(r=CORNER_RADIUS) square( [BOX_W, BOX_L], center=true );
            offset( r= CORNER_RADIUS - WALL ) square( [BOX_W-WALL, BOX_L-WALL],  center=true );
        };
        coordinates = [ [0,0],[0,BOX_L],[BOX_W,BOX_L],[BOX_W,0] ];
        translate ( [-BOX_W/2, -BOX_L/2] )
        hull()
        for (i = coordinates)
          translate(i) sphere(CORNER_RADIUS);
    
        // lid rail
        translate([BOX_W/-2+WALL,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);
        // lid rail
        translate([BOX_W/2-WALL*1.8,BOX_L/-2+0.9,WALL]) cube([WALL,BOX_L-(WALL*2)+0.3,3]);

        // mic channel cover
        // x, y, z
        translate([0,-44.0,WALL-0.7])
        rotate([90,0,0])
        linear_extrude(20.0) square([6.1,1.5], center=true);

        // mic mounting studs
        difference() {
            translate([0, KEEL_LENGTH, 0.0])
            //rotate([0, 0, 0])
            union() {
                // mounting stud for sensor
                // x, z, y
                translate([-4.5, -133, 0]) cylinder(h=7, d=2.5); 
                translate([4.5, -133, 0]) cylinder(h=7, d=2.5); 
            }
        }
                
        // sensor mounting studs
        difference() {
            translate([0, KEEL_LENGTH, 0.0])
            //rotate([0, 0, 0])
            union() {
                // mounting stud for sensor
                // x, z, y
                translate([-10, -105, 0]) cylinder(h=7, d=1.8); 
                translate([0, -75, 0]) cylinder(h=7, d=1.8); 
                translate([10, -105, 0]) cylinder(h=7, d=1.8); 
                
                // internal cable guide
                translate([-12, -65, 0]) cylinder(h=7, d=2.5);
                translate([12, -65, 0]) cylinder(h=7, d=2.5);
                
                translate([-6, -59, 0]) cylinder(h=7, d=2.5);
                translate([6, -59, 0]) cylinder(h=7, d=2.5);            
           }
        }
    }
    
    difference(){
        //center cutout - vent in base of box
        // x, y, z
        translate([-1.25,-2.5, -4])
        rotate([90,0,90])
        //y, z, x
        #cube([25, 6, 2]);
        // ref cutout in keel
        //y, z, x
        //cube([1.5, 12, 25]);
    }
}
