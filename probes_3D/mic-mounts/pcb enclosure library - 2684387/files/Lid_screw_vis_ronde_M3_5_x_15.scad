include <vis_ronde_M3_5_x_15.scad>
// Copyright (c) 2017 Jean SUZINEAU
// GNU Lesser General Public License v3

//threaded part of the screw
Lid_screw_d= vis_ronde_M3_5_x_15_d;//diameter
Lid_screw_r= vis_ronde_M3_5_x_15_r;//radius
Lid_screw_h= vis_ronde_M3_5_x_15_h;//height

//screw head
Lid_screw_head_d=vis_ronde_M3_5_x_15_Tete_d;
Lid_screw_head_r=vis_ronde_M3_5_x_15_Tete_r;

//screw housing
Lid_screw_housing_d=Lid_screw_head_d;
Lid_screw_housing_r=Lid_screw_head_r;
Lid_screw_housing_h=Lid_screw_h;

module Lid_screw        (){vis_ronde_M3_5_x_15         ();*vis_ronde_M3_5_x_15();} //you can change * to % here to show the screws
module Lid_screw_tube   (){vis_ronde_M3_5_x_15_tube    ();}
module Lid_screw_housing(){vis_ronde_M3_5_x_15_logement();}

