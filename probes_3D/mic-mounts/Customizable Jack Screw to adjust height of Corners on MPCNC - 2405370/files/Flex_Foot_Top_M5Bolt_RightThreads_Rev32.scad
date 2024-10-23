//Parametric Top Flex Foot for Mostly Printed CNC Machine
//Changed to add screw threads for Jack Screw
//Remix of https://www.thingiverse.com/thing:1401177
//Which is a remix of: http://www.thingiverse.com/thing:1100825
//Remixed 6/25/2017     By: David Bunch
//Print Time: 2:58:39 at 60%infill 1.03oz
//
//Rev32 : Added Clearance Variable
//
//-----------------------------------------
//include <threadsRough.scad>
include <threads.scad>
//
Clearance = 0.4;    //How much clearance to add to Thread OD for internal Threads
OD = 31.9;
Base_Ht = 1;        //Base Height to rest 1/2" EMT pipe on
Pit = 4;            //Pitch
Thread_Ht = 40.5;
//-----------------------------------------
Len = 53;           //Base Length
Wid = Len;          //Base Width
Cyl_ID = 28.5;      //Diameter of EMT pipe
                    //Standard version was 23.5mm
                    //23.7mm works better for me if not drilled all the way through
                    //28.74 inner Thread Diameter
                    //IE version was 25mm
Cyl_OD = 40.5;      //Outside Diameter of EMT connection
                    //Standard Version was 35.5mm
                    //IE version was 37mm
                    //+4 gives 4mm around OD of Jack Screw
Cyl_Ht = 40;        //Overall Height
Weld_OD = 4;        //Diameter of Weld around Cylinder
W_Thk = 5;          //Thickness of 4 Support Walls
Small_Hole = 4.0;   //Diameter of Bolt Hole
Nut_OD = 9.5;       //Diameter of Hex Nut used
Ht = 5.5;           //Base Height
Chamfer_EMT = 1;    //1= Chamfer the EMT opening, 0 = no chamfer

EMT_Base = 1;       //Set to -1 if you want hollow all the way through
                    //Otherwise set to Ht
//Vertical Hole and outside Rounding variables
Len_Half = Len / 2;
Vert_Hole_Offset = 17.5;    //X & Y Offset from Center of Vertical Holes
M5_OD = 6.0;                //Diameter of Bolt for Vertical Holes
M5Head_OD = Nut_OD;         //Diameter of Bolt Head for Vertical Holes
M5Head_Ht = 2.5;            //Original Recess
M5Nut_OD = 9.75;
M5_Res = 32;
Bolt_Len = 70;
Rnd_Rad = Len_Half - Vert_Hole_Offset;            //18mm OD round on corners
Rnd_OD = Rnd_Rad * 2;

Len2 = Len / 2;
Cyl_Rad = Cyl_OD / 2;
Weld_Rad = Weld_OD / 2;
CutCube_Len = Cyl_Rad + Weld_Rad;
Nut_Rad = Nut_OD / 2;
W_Thk2 = W_Thk / 2;
W45_Thk = W_Thk - 2;
W45_Thk2 = W45_Thk / 2;
X2 = sqrt((Cyl_Rad * Cyl_Rad) - (W45_Thk2 * W45_Thk2))+1;
X1 = X2 - 3;
NutX_Offset = X1 + 2.8;       //gives 3mm clearance of hole

Len2x = Len * Len;
Sq_Wid = sqrt(Len2x + Len2x);

Sq_Wid2 = Sq_Wid / 2;

NutZ_Height = Cyl_Ht - Nut_Rad - Weld_Rad;

echo(OD = OD);
echo(Vert_Hole_Offset = Vert_Hole_Offset);
echo(Sq_Wid = Sq_Wid);
echo("**Sq_Wid2 = ",Sq_Wid2);
echo(Ht = Ht);
echo(Rnd_OD = Rnd_OD);
echo(Cyl_Res = Cyl_Res);
echo(Cyl_Rad = Cyl_Rad);
echo(W45_Thk2 = W45_Thk2);

//Makes each segment about .7mm and even number of segments
Cyl_Res = (round(((Cyl_ID * 3.14)/4)/1)*4);       //Resolution of Vertical Cylinder
Rnd_Res = (round(((Rnd_OD * 3.14)/4)/1)*4);
$fn=24;
module VerticalHoles()
{
    translate([Vert_Hole_Offset,Vert_Hole_Offset,0])
    {
        translate([0,0,-1])
        cylinder(d=M5_OD,h=Ht+2,$fn=M5_Res);
        translate([0,0,Ht-M5Head_Ht])
        rotate([0,0,15])
        cylinder(d=M5Nut_OD,h=M5Head_Ht+1,$fn=6);
        ChamCorner();
    }
}
module Vertical4Holes()
{
    VerticalHoles();

    mirror([1,0,0])
    VerticalHoles();

    mirror([0,1,0])
    VerticalHoles();

    mirror([1,1,0])
    VerticalHoles();
}
module ChamCorner()
{
    translate([0,0,-1])
    difference()
    {
        cube([Len/2,Len/2,Ht+2]);
        translate([0,0,-1])
        cylinder(d=Rnd_OD,h=Ht+4,$fn=Rnd_Res);
        translate([-Len_Half,-Len,-1])
        cube([Len,Len,Ht+4]);
        translate([-Len,-Len_Half,-1])
        cube([Len,Len,Ht+4]);
    }
}
module SideNut()
{
    translate([-NutX_Offset,1.5,NutZ_Height])
    rotate([-90,0,0])
    difference()
    {
        hull()
        {
            rotate([0,0,30])
            cylinder(d=Nut_OD,h=6,$fn=6);
            translate([2,0,0])
            rotate([0,0,30])
            cylinder(d=Nut_OD,h=6,$fn=6);
            translate([2,8,2.5])
            rotate([0,0,30])
            cylinder(d=5,h=1,$fn=6);
        }
        cylinder(d=Small_Hole,h=50,center=true,$fn=24);
    }
}
module NutCut()
{
    translate([-NutX_Offset,1.5+6,NutZ_Height])
    rotate([-90,0,0])
    rotate([0,0,30])
    cylinder(d=Nut_OD,h=8,$fn=6);
}
module ChamfCube()
{
    translate([-X8,-X8,-1])
    rotate([0,0,-45])
    translate([-15,-30,0])
    cube([30,30,20]);
}
module NutSideWeld()
{
    hull()
    {
        translate([0,0,Ht])
        linear_extrude(height = .1, center = false, convexity = 10)polygon(points = 
        [[25.5,2.5],[20.19,2.5],[19.18,-2.5],[25.5,-2.5],[26.5,-1.5],
        [26.5,1.5]]);
        translate([0,0,Cyl_Ht-Weld_Rad-6.5-.1])
        linear_extrude(height = .1, center = false, convexity = 10)polygon(points = 
        [[19.18,-2.5],[19.49,-1.5],[20.1,1.5],[20.19,2.5]]);
    }
}
module RtSideWeld()
{
    hull()
    {
        translate([0,0,Ht])
        linear_extrude(height = .1, center = false, convexity = 10)polygon(points = 
        [[25.5,2],[20.1,2],[20.1,-2],[25.5,-2],[26.5,-1],
        [26.5,1]]);
        translate([0,0,Cyl_Ht-Weld_Rad-6.5-.1])
        linear_extrude(height = .1, center = false, convexity = 10)polygon(points = 
        [[20.1,0.55],[20.1,-0.55],[20.24,-0.5],[20.24,0.5]]);
    }
}
module RtSideWeld4()
{
    RtSideWeld();
    rotate([0,0,90])
    RtSideWeld();
    rotate([0,0,-90])
    RtSideWeld();
    for (m = [0,1])
    {
        mirror([0,m,0])
        translate([0,4,0])
        rotate([0,0,180])
        NutSideWeld();
    }
}
module Base()
{
    difference()
    {
        translate([-Len / 2,-Wid / 2,0])
        cube([Len,Wid,Ht]);       //Draw Base
        translate([0,0,EMT_Base])
        cylinder(d=Cyl_ID,h=Ht+2,$fn=Cyl_Res);    //Cut out for Bolt Hole
    }
}
module PipeCyl()
{
    difference()
    {
        union()
        {
            cylinder(d=Cyl_OD,h=Cyl_Ht,$fn=Cyl_Res);
            translate([0,0,Ht])
            WeldChamf();
            RtSideWeld4();
        }
        translate([0,0,-1])
        cylinder(d=Cyl_ID,h=Cyl_Ht+2,$fn=Cyl_Res);
        if (Chamfer_EMT == 1)
        {
//Chamfer the Inside where EMT goes in
            translate([0,0,Cyl_Ht - Weld_Rad])
            cylinder(d1=Cyl_ID,d2=Cyl_ID+Weld_OD,h=Weld_Rad+.01,$fn=Cyl_Res);
            translate([0,0,Cyl_Ht])
            WeldChamf();    //Chamfer the Outside edge of Cylinder at Top
        }
    }
}
module WeldChamf()
{
    rotate_extrude(convexity = 10, $fn = 100)
    translate([Cyl_Rad, 0, 0])
    circle(r = Weld_Rad, $fn = 4);
}
module DrawUnion()
{
    union()
    {
        Base();
        PipeCyl();
        SideNut();
        mirror([0,1,0])
        SideNut();
    }
}
module DrawFinal()
{
    difference()
    {
        DrawUnion();
//Cut Normal Right Hand Threads
        translate([0,0,EMT_Base])
        metric_thread (diameter=OD + Clearance, pitch=Pit, length=Thread_Ht, internal=false, angle = 40, thread_size = Pit, n_starts=1);
        translate([-NutX_Offset,1.5,NutZ_Height])
        rotate([-90,0,0])
        cylinder(d=Small_Hole,h=50,center=true,$fn=24);     //Tightening Bolt Hole
        NutCut();
        mirror([0,1,0])
        NutCut();
        translate([-Sq_Wid2,-1.5,-1])
        cube([Sq_Wid2,3,Cyl_Ht+2]);     //Cut Tightening Slot
        translate([0,0,-1])
        cylinder(d=3,h=Cyl_Ht,$fn=16);
        Vertical4Holes();
        for (m = [0,1])
        {
            mirror([0,m,0])
            translate([-26.5,1.5,-1])
            cylinder(d=2,h=Ht + 2,$fn=4);
        }
//        translate([-100,-100,-1])
//        cube([200,100,200]);          //Section Cut
    }
}
DrawFinal();