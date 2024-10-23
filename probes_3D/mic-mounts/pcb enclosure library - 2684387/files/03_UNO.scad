// pcb enclosure library
// Copyright (c) 2017 Jean SUZINEAU

// This library is a refactoring from:
// OpenSCAD-Arduino-Mounting-Library / arduino.scad
// https://www.thingiverse.com/thing:64008
//
// Arduino connectors library
//
// Copyright (c) 2013 Kelly Egan
//
// The MIT License (MIT)
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software
// and associated documentation files (the "Software"), to deal in the Software without restriction,
// including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
// and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do
// so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all copies or substantial
// portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
// NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
// IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
// WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
// SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

include <pcb_enclosure.scad>
include <00_NG.scad>

UNO_BoardShape= NG_BoardShape;

UNO_Components= NG_Components;

//Uno, Leonardo, ETHERNET holes
UNO_Holes = [
  [  2.54, 15.24 ],
  [  17.78, 66.04 ],
  [  45.72, 66.04 ],
  [  50.8, 13.97 ]
  ];

// 0 Plots for Uno, Leonardo, ETHERNET
UNO_Plots= 0;

default_UNO_lid_screws="1234";
default_UNO_lid_screws_outer="";

module UNO_pcb( _pcbHeight= pcbHeight)
  {
  pcb( UNO_BoardShape, UNO_Components, UNO_Holes, _pcbHeight);
  }

module UNO_bumper( _pcbHeight= pcbHeight, _mountingHoles = false)
  {
  bumper( UNO_BoardShape, UNO_Components, UNO_Holes, _pcbHeight, _mountingHoles);
  }

module UNO_enclosure( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _heightExtension= 10, _cornerRadius= 3, _mountType= TAPHOLE, _lid_screws= default_UNO_lid_screws, _lid_screws_outer=default_UNO_lid_screws_outer, _lid_screws= default_NG_lid_screws, _lid_screws_outer=default_NG_lid_screws_outer)
  {
  enclosure( UNO_BoardShape, UNO_Components, UNO_Holes, UNO_Plots, _pcbHeight, _wall, _offset, _heightExtension, _cornerRadius, _mountType, _lid_screws, _lid_screws_outer);
  }

module UNO_enclosure_lid( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _cornerRadius= 3, _lid_screws= default_UNO_lid_screws, _lid_screws_outer=default_UNO_lid_screws_outer, _lid_screws= default_NG_lid_screws, _lid_screws_outer=default_NG_lid_screws_outer)
  {
  enclosureLid( UNO_BoardShape, UNO_Components, _pcbHeight, _wall, _offset, _cornerRadius, _lid_screws, _lid_screws_outer);
  }

