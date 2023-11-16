//Customizable Jack Screw to adjust height of Corners on MPCNC
//Remixed from: https://www.thingiverse.com/thing:953976
//Remix by: David Bunch     6/23/2017
//Print Time 100mm Tot_Ht: 5:01:42 at 60%infill 1.5oz
//
//Source for Threads from: http://dkprojects.net/openscad-threads/
//In the threads.scad file I changed the segments function to:
//Rough: (about 4mm segments)
//function segments (diameter) = (round(((diameter * 3.14) / 4) / 3)*4);
//Final: (about 1mm segments)
//function segments (diameter) = (round(((diameter * 3.14) / 4) / 1)*4);
//otherwise the segments for the threads will be around 2mm in length
//
//include <threadsRough.scad>
include <threads.scad>
Clearance = 0.4;                     //How much clearance to add to Thread OD for internal Threads
Thread_Pit = 4;                     //Pitch of threads
Thread_Angle = 40;                  //Angle of Threads, Standard of 30 did not print well for me
Bot_Threads_ON = 1;                 //0 = No threads at bottom, just cylinder
Bot_OD = 30.9;                      //Diameter of bottom Cylinder if threads are not used
                                    //Previous design used this diameter
Thread_Ht = 15;                     //Height of Threads

Tot_Ht = 40;                       //Total Height of Jack Screw 

OD = 31.9;                          //Outside diameter of Threads

EMT_OD = 18.5;                      //Hole thru center to insert optional 1/2" EMT pipe
Eject_Hole_OD = 5.5;                  //Diameter of hole in bottom to easily remove EMT
Base_Ht = 1;                        //Base Height to rest 1/2" EMT pipe on

Nut_Trans_Ht = 3;                   //Transition height from round to 6 sided Nut
Nut_Ht = 3.5;                         //Height of Hex Nut
Nut_Ht2 = Nut_Ht / 2;
Nut_Trans_OD = OD - 3;              //28.9mm
Nut_Z_Ht = Nut_Trans_Ht + Nut_Ht2;  //Center line height of Adjustment Nut

//This is the horizontal hex hole in middle of adjustment Nut
Hex_Hor_Hole_ON = 1;                //0 = No Hole, 1 = Add Hole
Hex_Hor_OD = 3.0;                   //Horizontal Hex dimension across Flats
Hex_Hor_Rad = Hex_Hor_OD / 2;
Rad_Hor = Hex_Hor_Rad / cos(30);    //Real Radius of Horizontal Hex Hole
OD_Hor = Rad_Hor * 2 + .5;          //Real Diameter of Horizontal Hex Hole

//Jack Screw Adjustment Nut Size
JackScrew_OD = 32;              //32mm Horizontal Distance across  Flats
JS_Rad = JackScrew_OD / 2;
Rad_JS = JS_Rad / cos(30);    //Real Radius of Horizontal Hex Hole
OD_JS = Rad_JS * 2;          //Real Diameter of Horizontal Hex Hole

Eject_X_Offset = (EMT_OD / 2) - (Eject_Hole_OD / 2);
Bot_OD_Res = round(((Bot_OD * 3.14) / 4) / 1) * 4;

echo(OD_Hor = OD_Hor);
echo(Tot_Ht = Tot_Ht);
echo(OD_JS = OD_JS);

module TurnNut()
{
    translate([0,0,-Nut_Z_Ht])
    difference()
    {
        union()
        {
//Transition from round to the 6 sided Nut
            hull()
            {
                cylinder(d=Nut_Trans_OD,h=.001,$fn=144);
                translate([0,0,Nut_Trans_Ht - .001])
                cylinder(d=OD_JS,h=.001,$fn=6);
            }
//Draw 6 Sided Nut comes out close to 32mm across flats (36.95mm would have made it 32mm)
            translate([0,0,Nut_Trans_Ht])
            cylinder(d=OD_JS,h=Nut_Ht,$fn=6);
//Transition from 6 sided Nut to round
            translate([0,0,Nut_Trans_Ht + Nut_Ht])
            hull()
            {
                cylinder(d=OD_JS,h=.001,$fn=6);
                translate([0,0,Nut_Trans_Ht - .001])
                cylinder(d=Nut_Trans_OD,h=.001,$fn=144);
            }
        }
    }
}

module DrawJackScrew()
{
    difference()
    {
        union()
        {
//Draw the  bottom Left hand threads (mirrored) if wanted
            if (Bot_Threads_ON == 1)
            {
                mirror([1,0,0])
                metric_thread (diameter=OD, pitch=Thread_Pit, length=Thread_Ht, internal=false, angle = Thread_Angle, n_starts=1);
                translate([0,0,Thread_Ht])
                cylinder(d=Nut_Trans_OD,h=Tot_Ht - (Thread_Ht * 2),$fn=96);
            } else
            {
                cylinder(d=Bot_OD,h=Tot_Ht/2,$fn=Bot_OD_Res);
//Adjust transition height by 3mm if no threads at bottom
                translate([0,0,Thread_Ht+3])
                cylinder(d=Nut_Trans_OD,h=Tot_Ht - (Thread_Ht * 2) - 3,$fn=96);
                translate([0,0,Thread_Ht])
                cylinder(d1=OD-6,d2=Nut_Trans_OD,h=3,$fn=96);
            }
//Draw Right hand threads at the top
            translate([0,0,Tot_Ht])
            rotate([180,0,0])
            metric_thread (diameter=OD, pitch=Thread_Pit, length=Thread_Ht, internal=false, angle = Thread_Angle, n_starts=1);
            translate([0,0,Tot_Ht / 2])
            TurnNut();      //Draw the Jack Screw tighting Nut
        }
        if (Hex_Hor_Hole_ON == 1)
        {
            translate([0,0,Tot_Ht / 2])
            rotate([90,0,0])
            rotate([0,0,30])
            cylinder(d=OD_Hor,h=OD + 2,center=true,$fn=6);
        }
        translate([Eject_X_Offset,0,-1])
        cylinder(d=Eject_Hole_OD,h= Base_Ht + 2,$fn=24);    //Access hole to eject EMT
        translate([0,0,Base_Ht])
        cylinder(d=EMT_OD,h=Tot_Ht + 2,$fn=84);           //Cut Hole for optional 1/2" EMT to Fit In
        translate([0,0,Tot_Ht - 2])
        cylinder(d1=EMT_OD,d2=EMT_OD + 4,h=2.01,$fn=84);  //Bevel the top opening for EMT

//        translate([-100,0,-1])
//        cube([200,100,200]);           //Cut Half Section
    }
}
module DrawBotReversed()
{
    difference()
    {
        cylinder(d=38.5,h=15,$fn=60);
            translate([0,0,-1])
            mirror([1,0,0])     //Mirror for Left Hand Threads
            metric_thread (diameter=OD + Clearance, pitch=Thread_Pit, length=Thread_Ht+5, internal=false, angle = 40, thread_size = Thread_Pit, n_starts=1);
    }
}
module DrawTop()
{
    difference()
    {
        cylinder(d=38.5,h=15,$fn=60);
            translate([0,0,-1])
            metric_thread (diameter=OD + Clearance, pitch=Thread_Pit, length=Thread_Ht+5, internal=false, angle = 40, thread_size = Thread_Pit, n_starts=1);
    }
}
translate([-38.5/2-3,0,0])
DrawBotReversed();
//DrawJackScrew();
translate([38.5/2+3,0,0])
DrawTop();