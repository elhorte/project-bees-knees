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

NG_BoardShape = [
  [  0.0, 0.0 ],
  [  53.34, 0.0 ],
  [  53.34, 66.04 ],
  [  50.8, 66.04 ],
  [  48.26, 68.58 ],
  [  15.24, 68.58 ],
  [  12.7, 66.04 ],
  [  1.27, 66.04 ],
  [  0.0, 64.77 ]
  ];

//[position, dimensions, direction(which way would a cable attach), type(header, usb, etc.), color]
NG_Components = [
  [[1.27, 17.526, 0], [headerWidth, headerWidth * 10, headerHeight], [0, 0, 1], HEADER_F, "Black" ],
  [[1.27, 44.45, 0], [headerWidth, headerWidth * 8, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[49.53, 26.67, 0], [headerWidth, headerWidth * 8, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[49.53, 49.53, 0], [headerWidth, headerWidth * 6, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[9.34, -6.5, 0],[12, 16, 11],[0, -1, 0], USB, "LightGray" ],
  [[40.7, -1.8, 0], [9.0, 13.2, 10.9], [0, -1, 0], POWER, "Black" ]
  ];

//Duemilanove, Diecimila, NG and earlier
NG_Holes = [
  [  2.54, 15.24 ],
  [  17.78, 66.04 ],
  [  45.72, 66.04 ]
  ];

NG_Plots= 0;

default_NG_lid_screws="1234";
default_NG_lid_screws_outer="";

module NG_pcb( _pcbHeight= pcbHeight)
  {
  pcb( NG_BoardShape, NG_Components, NG_Holes, _pcbHeight);
  }

module NG_bumper( _pcbHeight= pcbHeight, _mountingHoles = false)
  {
  bumper( NG_BoardShape, NG_Components, NG_Holes, _pcbHeight, _mountingHoles);
  }

module NG_enclosure( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _heightExtension= 10, _cornerRadius= 3, _mountType= TAPHOLE, _lid_screws= default_NG_lid_screws, _lid_screws_outer=default_NG_lid_screws_outer)
  {
  enclosure( NG_BoardShape, NG_Components, NG_Holes, NG_Plots, _pcbHeight, _wall, _offset, _heightExtension, _cornerRadius, _mountType, _lid_screws, _lid_screws_outer);
  }

module NG_enclosure_lid( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _cornerRadius= 3, _lid_screws= default_NG_lid_screws, _lid_screws_outer=default_NG_lid_screws_outer)
  {
  enclosureLid( NG_BoardShape, NG_Components, _pcbHeight, _wall, _offset, _cornerRadius, _lid_screws, _lid_screws_outer);
  }

