//Remix of Lock-CornerC to make internal threaded for use with Turnbuckle Adjuster
//Remixed by: David Bunch   6/23/2017
//
//include <threadsRough.scad>
include <threads.scad>
//
Clearance = 0.4;    //How much clearance to add to Thread OD for internal Threads
OD = 31.9;
Mirror_LockC = 0;   //0 = No, 1= Mirror
                    //This part needs to be mirrored before cutting threads in it.

Base_Ht = 1;        //Base Height to rest 1/2" EMT pipe on
Pit = 4;            //Pitch

Thread_Ht = 34.5 + 6;
Ht = 27.0;          //Original Flex foot is 40mm high
Base_Ht = 7;
//
Bot_Hole_OD = 4.05;
Side_Hole_Ht = 17;
Side_Hole_OD = 4.05;
Side_Head_OD = 8;
Side_Nut_OD = 9.5;
module TopChamf()
{
    translate([0,0,0])
    rotate([0,0,50.09])
    rotate_extrude(angle = 259.81,convexity = 10, $fn = 64)
    translate([20.25, 0, 0])
    circle(r = 3.125, $fn = 4);
    for (m = [0,1])
    {
        mirror([0,m,0])
        translate([12.9,-15.49,0])
        rotate([0,0,40.03])
        rotate([0,90,0])
        cylinder(d=6.25,h=20,$fn=4);
    }
    translate([24.87,0,0])
    rotate([90,0,0])
    cylinder(d=6.25,h=20,center=true,$fn=4);
}
module BotChamf()
{
    rotate([0,0,50.09])
    rotate_extrude(angle = 259.81,convexity = 10, $fn = 64)
    translate([20.25, 0, 0])
    circle(r = .6, $fn = 4);
    for (m = [0,1])
    {
        mirror([0,m,0])
        translate([12.9,-15.49,0])
        rotate([0,0,40.03])
        rotate([0,90,0])
        cylinder(d=1.2,h=20,$fn=4);
    }
    translate([24.87,0,0])
    rotate([90,0,0])
    cylinder(d=1.2,h=20,center=true,$fn=4);
    hull()
    {
        translate([11.92,0,-.001])
        cylinder(d1=2.5,d2=1.5,h=.601,$fn=12);
        translate([11.92+25,0,-.001])
        cylinder(d1=2.5,d2=1.5,h=.601,$fn=12);
    }
}
module Side_Holes()
{
    translate([19.4,0,Side_Hole_Ht])
    rotate([90,0,0])
    cylinder(d=Side_Hole_OD,h=50,center=true,$fn=24);       //Drill all the Way thur

    translate([19.4,7,Side_Hole_Ht])
    rotate([-90,0,0])
    rotate([0,0,30])
    cylinder(d=Side_Head_OD,h=10,$fn=40);         //Countersink for Screw head

    translate([19.4,-7,Side_Hole_Ht])
    rotate([90,0,0])
    rotate([0,0,30])
    cylinder(d=Side_Nut_OD,h=10,$fn=6);         //Countersink for Nut
}
module Clamp()
{
    linear_extrude(height = Ht, center = false, convexity = 10)polygon(points = 
    [[12.99,-15.53],[24.86,-5.56],[24.86,5.56],[12.99,15.53]]);
}
module DrawFinal()
{
    difference()
    {
        mirror([Mirror_LockC,0,0])
        union()
        {
            cylinder(d=40.5,h=Ht,$fn=64);
            Clamp();;
        }
        mirror([Mirror_LockC,0,0])
        {
            translate([0,0,-1])
            cylinder(d=Bot_Hole_OD,h=Ht+2,$fn=24);
            translate([11.92,-.75,-1])
            cube([14,1.5,Ht+2]);
            translate([11.92,0,-1])
            cylinder(d=1.5,h=Ht+2,$fn=12);
            BotChamf();
            translate([0,0,Ht])
            TopChamf();
            Side_Holes();
        }

        translate([0,0,Base_Ht])
        metric_thread (diameter=OD + Clearance, pitch=Pit, length=Thread_Ht, internal=false, angle = 40, thread_size = Pit,n_starts=1);
    }
}
DrawFinal();