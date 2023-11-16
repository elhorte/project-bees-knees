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

MEGA_BoardShape = [
  [  0.0, 0.0 ],
  [  53.34, 0.0 ],
  [  53.34, 99.06 ],
  [  52.07, 99.06 ],
  [  49.53, 101.6 ],
  [  15.24, 101.6 ],
  [  12.7, 99.06 ],
  [  2.54, 99.06 ],
  [  0.0, 96.52 ]
  ];

//[position, dimensions, direction(which way would a cable attach), type(header, usb, etc.), color]
MEGA_Components = [
  [[1.27, 22.86, 0], [headerWidth, headerWidth * 8, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[1.27, 44.45, 0], [headerWidth, headerWidth * 8, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[1.27, 67.31, 0], [headerWidth, headerWidth * 8, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[49.53, 31.75, 0], [headerWidth, headerWidth * 6, headerHeight ], [0, 0, 1], HEADER_F, "Black"],
  [[49.53, 49.53, 0], [headerWidth, headerWidth * 8, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[49.53, 72.39, 0], [headerWidth, headerWidth * 8, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[1.27, 92.71, 0], [headerWidth * 18, headerWidth * 2, headerHeight], [0, 0, 1], HEADER_F, "Black"],
  [[9.34, -6.5, 0],[12, 16, 11],[0, -1, 0], USB, "LightGray"],
  [[40.7, -1.8, 0], [9.0, 13.2, 10.9], [0, -1, 0], POWER, "Black" ]
  ];

// Original Mega holes
MEGA_Holes = [
  [  2.54, 15.24 ],
  [  50.8, 13.97 ],
  [  2.54, 90.17 ],
  [  50.8, 96.52 ]
  ];

MEGA_Plots=0;

default_MEGA_lid_screws="1234";
default_MEGA_lid_screws_outer="";

module MEGA_pcb( _pcbHeight= pcbHeight)
  {
  pcb( MEGA_BoardShape, MEGA_Components, MEGA_Holes, _pcbHeight);
  }

module MEGA_bumper( _pcbHeight= pcbHeight, _mountingHoles = false)
  {
  bumper( MEGA_BoardShape, MEGA_Components, MEGA_Holes, _pcbHeight, _mountingHoles);
  }

module MEGA_enclosure( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _heightExtension= 10, _cornerRadius= 3, _mountType= TAPHOLE, _lid_screws= default_MEGA_lid_screws, _lid_screws_outer=default_MEGA_lid_screws_outer)
  {
  enclosure( MEGA_BoardShape, MEGA_Components, MEGA_Holes, MEGA_Plots, _pcbHeight, _wall, _offset, _heightExtension, _cornerRadius, _mountType, _lid_screws, _lid_screws_outer);
  }

module MEGA_enclosure_lid( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _cornerRadius= 3, _lid_screws= default_MEGA_lid_screws, _lid_screws_outer=default_MEGA_lid_screws_outer)
  {
  enclosureLid( MEGA_BoardShape, MEGA_Components, _pcbHeight, _wall, _offset, _cornerRadius, _lid_screws, _lid_screws_outer);
  }


