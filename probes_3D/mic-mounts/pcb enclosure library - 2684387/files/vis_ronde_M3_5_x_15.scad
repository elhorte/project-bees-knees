include <M_global.scad>
// Copyright (c) 2017 Jean SUZINEAU
// GNU Lesser General Public License v3

//vis_ronde_M3_5_x_15
//diamètre extérieur mesuré 3.5 mm, âme 2.6 mm
vis_ronde_M3_5_x_15_d=3.5; vis_ronde_M3_5_x_15_r=vis_ronde_M3_5_x_15_d/2;
vis_ronde_M3_5_x_15_h=15;
vis_ronde_M3_5_x_15_Pointe_h=1;
vis_ronde_M3_5_x_15_Tete_h=2.4;
vis_ronde_M3_5_x_15_Tete_d=6.8+Reduction_diametre;vis_ronde_M3_5_x_15_Tete_r=vis_ronde_M3_5_x_15_Tete_d/2;
vis_ronde_M3_5_x_15_Tete_rx=vis_ronde_M3_5_x_15_Tete_r/sqrt(2);
vis_ronde_M3_5_x_15_Tete_ry=vis_ronde_M3_5_x_15_Tete_rx;
module vis_ronde_M3_5_x_15(_debord_tete=0)
  {
  hull()
    {
    cylinder(r=0.1, h=0.1  ,$fn=50);
    tz(vis_ronde_M3_5_x_15_Pointe_h+0.01)cylinder(r=vis_ronde_M3_5_x_15_r, h=0.1  ,$fn=50);
    }
  tz(vis_ronde_M3_5_x_15_Pointe_h)cylinder(r=vis_ronde_M3_5_x_15_r, h=vis_ronde_M3_5_x_15_h-vis_ronde_M3_5_x_15_Pointe_h+0.02  ,$fn=50);
  tz(vis_ronde_M3_5_x_15_h)
    {
    cylinder(r=vis_ronde_M3_5_x_15_Tete_r, h=vis_ronde_M3_5_x_15_Tete_h  ,$fn=50);
    tz(vis_ronde_M3_5_x_15_Tete_h-0.01)cylinder(r=vis_ronde_M3_5_x_15_Tete_r, h=_debord_tete  ,$fn=50);
    }
  }

module vis_ronde_M3_5_x_15_tube()
  {
  cylinder(r=vis_ronde_M3_5_x_15_Tete_r+0.01, h=vis_ronde_M3_5_x_15_h, $fn=50);
  }

module vis_ronde_M3_5_x_15_logement()
  {
  difference()
   {
   vis_ronde_M3_5_x_15_tube();
   vis_ronde_M3_5_x_15();
   }
  }
//vis_ronde_M3_5_x_15();
//vis_ronde_M3_5_x_15_logement();
