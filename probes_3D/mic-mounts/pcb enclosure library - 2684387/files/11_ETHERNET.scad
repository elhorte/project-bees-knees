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
include <03_UNO.scad>

ETHERNET_BoardShape= NG_BoardShape;

//[position, dimensions, direction(which way would a cable attach), type(header, usb, etc.), color]
ETHERNET_Components = [
  [[1.27, 17.526, 0], [headerWidth, headerWidth * 10, headerHeight], [0, 0, 1], HEADER_F, "Black" ],
  [[1.27, 44.45, 0], [headerWidth, headerWidth * 8, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[49.53, 26.67, 0], [headerWidth, headerWidth * 8, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[49.53, 49.53, 0], [headerWidth, headerWidth * 6, headerHeight ], [0, 0, 1], HEADER_F, "Black" ],
  [[7.20, -4.4, 0],[16, 22, 13],[0, -1, 0], RJ45, "Green" ],
  [[40.7, -1.8, 0], [9.0, 13.2, 10.9], [0, -1, 0], POWER, "Black" ]
  ];

ETHERNET_Holes= UNO_Holes;

ETHERNET_Plots=0;

default_ETHERNET_lid_screws="1234";
default_ETHERNET_lid_screws_outer="";

module ETHERNET_pcb( _pcbHeight= pcbHeight)
  {
  pcb( ETHERNET_BoardShape, ETHERNET_Components, ETHERNET_Holes, _pcbHeight);
  }

module ETHERNET_bumper( _pcbHeight= pcbHeight, _mountingHoles = false)
  {
  bumper( ETHERNET_BoardShape, ETHERNET_Components, ETHERNET_Holes, _pcbHeight, _mountingHoles);
  }

module ETHERNET_enclosure( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _heightExtension= 10, _cornerRadius= 3, _mountType= TAPHOLE, _lid_screws= default_ETHERNET_lid_screws, _lid_screws_outer=default_ETHERNET_lid_screws_outer)
  {
  enclosure( ETHERNET_BoardShape, ETHERNET_Components, ETHERNET_Holes, ETHERNET_Plots, _pcbHeight, _wall, _offset, _heightExtension, _cornerRadius, _mountType, _lid_screws, _lid_screws_outer);
  }

module ETHERNET_enclosure_lid( _pcbHeight= pcbHeight, _wall= 3, _offset= 3, _cornerRadius= 3, _lid_screws= default_ETHERNET_lid_screws, _lid_screws_outer=default_ETHERNET_lid_screws_outer)
  {
  enclosureLid( ETHERNET_BoardShape, ETHERNET_Components, _pcbHeight, _wall, _offset, _cornerRadius, _lid_screws, _lid_screws_outer);
  }

