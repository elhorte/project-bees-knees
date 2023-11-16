include <M_global.scad>
// Copyright (c) 2017 Jean SUZINEAU
// GNU Lesser General Public License v3

//vis_M3_5_x_16
//diamètre extérieur mesuré 3.8 mm, âme 2.2 mm
vis_M3_5_x_16_d=3.6; vis_M3_5_x_16_r=vis_M3_5_x_16_d/2;
vis_M3_5_x_16_h=16;
vis_M3_5_x_16_Pointe_h=2;
vis_M3_5_x_16_Tete_h=3.5;
vis_M3_5_x_16_Tete_d=7.5+Reduction_diametre;vis_M3_5_x_16_Tete_r=vis_M3_5_x_16_Tete_d/2;
vis_M3_5_x_16_Tete_rx=vis_M3_5_x_16_Tete_r/sqrt(2);
vis_M3_5_x_16_Tete_ry=vis_M3_5_x_16_Tete_rx;
module vis_M3_5_x_16(_debord_tete=0)
  {
  hull()
    {
    cylinder(r=0.1, h=0.1  ,$fn=50);
    tz(vis_M3_5_x_16_Pointe_h+0.01)cylinder(r=vis_M3_5_x_16_r, h=0.1  ,$fn=50);
    }
  tz(vis_M3_5_x_16_Pointe_h)cylinder(r=vis_M3_5_x_16_r, h=vis_M3_5_x_16_h-vis_M3_5_x_16_Pointe_h+0.02  ,$fn=50);
  tz(vis_M3_5_x_16_h-vis_M3_5_x_16_Tete_h)
    {
    hull()
      {
      cylinder(r=vis_M3_5_x_16_r, h=0.1  ,$fn=50);
      tz(vis_M3_5_x_16_Tete_h)cylinder(r=vis_M3_5_x_16_Tete_r, h=0.1  ,$fn=50);
      }
     tz(vis_M3_5_x_16_Tete_h-0.01)cylinder(r=vis_M3_5_x_16_Tete_r, h=_debord_tete  ,$fn=50);
    }
  }

module vis_M3_5_x_16_tube()
  {
  cylinder(r=vis_M3_5_x_16_Tete_r+0.01, h=vis_M3_5_x_16_h, $fn=50);
  }

module vis_M3_5_x_16_logement()
  {
  difference()
   {
   vis_M3_5_x_16_tube();
   vis_M3_5_x_16();
   }
  }
//vis_M3_5_x_16();
//vis_M3_5_x_16_logement();
