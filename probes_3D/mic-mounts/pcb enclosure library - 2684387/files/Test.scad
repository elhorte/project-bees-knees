// Copyright (c) 2017 Jean SUZINEAU
// GNU Lesser General Public License v3

include <00_NG.scad>
include <01_DIECIMILA.scad>
include <02_DUEMILANOVE.scad>
include <03_UNO.scad>
include <04_LEONARDO.scad>
include <05_MEGA.scad>
include <06_MEGA2560.scad>
include <07_DUE.scad>
include <08_YUN.scad>          //not implemented
include <09_INTELGALILEO.scad> //not implemented
include <10_TRE.scad>          //not implemented
include <11_ETHERNET.scad>

//NG_pcb();
//DIECIMILA_pcb();
//DUEMILANOVE_pcb();
//UNO_pcb();
//LEONARDO_pcb();
//MEGA_pcb();
//MEGA2560_pcb();
//DUE_pcb();
//YUN_pcb();          //not implemented
//INTELGALILEO_pcb(); //not implemented
//TRE_pcb();          //not implemented
//ETHERNET_pcb();
//NG_bumper();
//DIECIMILA_bumper();
//DUEMILANOVE_bumper();
//UNO_bumper();
//LEONARDO_bumper();
//MEGA_bumper();
//MEGA2560_bumper();
//DUE_bumper();
//YUN_bumper();            //not implemented
//INTELGALILEO_bumper();   //not implemented
//TRE_bumper();            //not implemented
//ETHERNET_bumper();
//NG_enclosure();
//DIECIMILA_enclosure();
//DUEMILANOVE_enclosure();
//UNO_enclosure();
//LEONARDO_enclosure();
//MEGA_enclosure();
//MEGA2560_enclosure();
//DUE_enclosure();
//YUN_enclosure();             //not implemented
//INTELGALILEO_enclosure();    //not implemented
//TRE_enclosure();             //not implemented
//ETHERNET_enclosure();
//NG_enclosure_lid();
//DIECIMILA_enclosure_lid();
//DUEMILANOVE_enclosure_lid();
//UNO_enclosure_lid();
//LEONARDO_enclosure_lid();
//MEGA_enclosure_lid();
//MEGA2560_enclosure_lid();
//DUE_enclosure_lid();
//YUN_enclosure_lid();             //not implemented
//INTELGALILEO_enclosure_lid();    //not implemented
//TRE_enclosure_lid();             //not implemented
//ETHERNET_enclosure_lid();


//tx(-160)          NG_pcb(); tx(-80)          NG_bumper();          NG_enclosure();tz(3+5)          NG_pcb();tx(80)          NG_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("          NG                                 ");
//tx(-160)   DIECIMILA_pcb(); tx(-80)   DIECIMILA_bumper();   DIECIMILA_enclosure();tz(3+5)   DIECIMILA_pcb();tx(80)   DIECIMILA_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("   DIECIMILA                                 ");
//tx(-160) DUEMILANOVE_pcb(); tx(-80) DUEMILANOVE_bumper(); DUEMILANOVE_enclosure();tz(3+5) DUEMILANOVE_pcb();tx(80) DUEMILANOVE_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text(" DUEMILANOVE                                 ");
//tx(-160)         UNO_pcb(); tx(-80)         UNO_bumper();         UNO_enclosure();tz(3+5)         UNO_pcb();tx(80)         UNO_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("         UNO                                 ");
//tx(-160)    LEONARDO_pcb(); tx(-80)    LEONARDO_bumper();    LEONARDO_enclosure();tz(3+5)    LEONARDO_pcb();tx(80)    LEONARDO_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("    LEONARDO                                 ");
//tx(-160)        MEGA_pcb(); tx(-80)        MEGA_bumper();        MEGA_enclosure();tz(3+5)        MEGA_pcb();tx(80)        MEGA_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("        MEGA                                 ");
//tx(-160)    MEGA2560_pcb(); tx(-80)    MEGA2560_bumper();    MEGA2560_enclosure();tz(3+5)    MEGA2560_pcb();tx(80)    MEGA2560_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("    MEGA2560                                 ");
//tx(-160)         DUE_pcb(); tx(-80)         DUE_bumper();         DUE_enclosure();tz(3+5)         DUE_pcb();tx(80)         DUE_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("         DUE                                 ");
//tx(-160)         YUN_pcb(); tx(-80)         YUN_bumper();         YUN_enclosure();tz(3+5)         YUN_pcb();tx(80)         YUN_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("         YUN                  not implemented");
//tx(-160)INTELGALILEO_pcb(); tx(-80)INTELGALILEO_bumper();INTELGALILEO_enclosure();tz(3+5)INTELGALILEO_pcb();tx(80)INTELGALILEO_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("INTELGALILEO                  not implemented");
//tx(-160)         TRE_pcb(); tx(-80)         TRE_bumper();         TRE_enclosure();tz(3+5)         TRE_pcb();tx(80)         TRE_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("TRE                           not implemented");
//tx(-160)    ETHERNET_pcb(); tx(-80)    ETHERNET_bumper();    ETHERNET_enclosure();tz(3+5)    ETHERNET_pcb();tx(80)    ETHERNET_enclosure_lid();tx(-120)ty(-40)color([1,0,1,0])text("ETHERNET                                     ");

NG_enclosure(_lid_screws="234", _lid_screws_outer="34");tz(3+5)NG_pcb(); tx(80)NG_enclosure_lid(_lid_screws="234", _lid_screws_outer="34");

