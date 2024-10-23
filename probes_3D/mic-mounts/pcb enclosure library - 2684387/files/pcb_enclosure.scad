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
//
include <pins.scad>
include <M_global.scad>
include <Lid_screw.scad>

/********************************** MEASUREMENTS **********************************/
pcbHeight = 1.7;
headerWidth = 2.54;
headerHeight = 9;
//mountingHoleRadius = 3.2 / 2;
mountingHoleRadius = (3-1/*adjust*/)/2; // 3 x 14 wood screw countersunk head
PlotDiameter=5;
PlotRadius=PlotDiameter/2;
PlotHeight=4;

//Mounting holes for bumper
//bumper_woodscrewHeadRad = 4.6228;  //Number 8 wood screw head radius
//bumper_woodscrewThreadRad = 2.1336;    //Number 8 wood screw thread radius
//bumper_woodscrewHeadHeight = 2.8448;  //Number 8 wood screw head height
bumper_woodscrewHeadRad    = 6/2;               // 3 x 14 wood screw countersunk head , head radius
bumper_woodscrewThreadRad  = (3-1/*adjust*/)/2; // 3 x 14 wood screw countersunk head , thread radius
bumper_woodscrewHeadHeight = 2;                 // 3 x 14 wood screw countersunk head , head height

//Setting for enclosure mounting holes (Not Arduino mounting)
NOMOUNTINGHOLES = 0;
INTERIORMOUNTINGHOLES = 1;
EXTERIORMOUNTINGHOLES = 2;

//Lid and lid screws
Epaisseur_couvercle=3;
default_pcb_lid_screws="1234";
default_pcb_lid_screws_outer="1234";

//Modules
module pcb( _boardShape, _components, _boardHoles, _pcbHeight= pcbHeight)
  {
  //The PCB with holes
  difference()
    {
    color("SteelBlue") 
      boardShape( _boardShape, _components, _pcbHeight);
    translate([0,0,-_pcbHeight * 0.5])
      holePlacement( _boardHoles)
        color("SteelBlue")
          cylinder(r = mountingHoleRadius, h = _pcbHeight * 2, $fn=32);
    }
  //Add all components to board
  components( _components, component = ALL , _pcbHeight= pcbHeight);
}

//Creates a bumper style enclosure that fits tightly around the edge of the PCB.
module bumper( _boardShape, _components, _boardHoles, _pcbHeight= pcbHeight, _mountingHoles = false)
  {
  bumperBaseHeight = 2;
  bumperHeight = bumperBaseHeight + _pcbHeight + 0.5;
  dimensions = boardDimensions( _boardShape, _components, _pcbHeight);

  difference()
    {
    union()
      {
      //Outer rim of bumper
      difference()
        {
        boardShape( _boardShape, _components, bumperHeight, _offset=1.4);
        translate([0,0,-0.1])
          boardShape( _boardShape, _components, bumperHeight + 0.2);
        }

      //Base of bumper  
      difference()
        {
        boardShape( _boardShape, _components, bumperBaseHeight, _offset=1);
        translate([0,0, -0.1])
          boardShape(_boardShape, _components, bumperHeight + 0.2, _offset=-2);
        }

      //Board mounting holes
      holePlacement( _boardHoles)
        cylinder(r = mountingHoleRadius + 1.5, h = bumperBaseHeight, $fn = 32);

      //Bumper mounting holes (exterior)
      if( _mountingHoles )
        {
        difference()
          {
          hull()
            {
            translate([-6, (dimensions[1] - 6) / 2, 0])
              cylinder( r = 6, h = pcbHeight + 2, $fn = 32 );
            translate([ -0.5, dimensions[0] / 2 - 9, 0]) 
              cube([0.5, 12, bumperHeight]);
            }
          translate([-6, (dimensions[0] - 6) / 2, 0])
            mountingHole(holeDepth = bumperHeight);
          }
        difference()
          {
          hull()
            {
            translate([dimensions[0] + 6, (dimensions[1] - 6) / 2,0])
              cylinder( r = 6, h = pcbHeight + 2, $fn = 32 );
            translate([ dimensions[0], dimensions[1] / 2 - 9, 0]) 
              cube([0.5, 12, bumperHeight]);
            }
          translate([dimensions[0] + 6, (dimensions[1] - 6) / 2,0])
            mountingHole(holeDepth = bumperHeight);
          }
        }
      }
    translate([0,0,-0.5])
      holePlacement( _boardHoles)
        cylinder(r = mountingHoleRadius, h = bumperHeight, $fn = 32);
    translate([0, 0, bumperBaseHeight])
      {
      components(_components, component = ALL, _offset = 1, _pcbHeight= _pcbHeight);
      }
    translate([4,(dimensions[1] - dimensions[1] * 0.4)/2,-1])
      cube([dimensions[0] -8,dimensions[1] * 0.4,bumperBaseHeight + 2]);
    }
  }

standOffHeight = 5;
function enclosure_height( _Board_Dimensions, _wall, _heightExtension) = _Board_Dimensions[2] + _wall + standOffHeight + _heightExtension;

//Create a board enclosure
module enclosure( _boardShape, _components, _boardHoles, _boardPlots,
                  _pcbHeight= pcbHeight,
                  _wall = 3,
                  _offset = 3,
                  _heightExtension = 10,
                  _cornerRadius = 3,
                  _mountType = TAPHOLE,
                  _lid_screws= default_pcb_lid_screws,
                  _lid_screws_outer= default_pcb_lid_screws_outer
                  )
  {
  dimensions= boardDimensions(_boardShape, _components, _pcbHeight);
  boardDim  = boardDimensions(_boardShape, _components, _pcbHeight);
  pcbDim    = pcbDimensions  (_boardShape, _pcbHeight);
  pcbPos    = pcbPosition    (_boardShape);

  enclosureWidth = pcbDim[0] + (_wall + _offset) * 2; enclosureWidth_2= enclosureWidth/2;
  enclosureDepth = pcbDim[1] + (_wall + _offset) * 2; enclosureDepth_2= enclosureDepth/2;
  //enclosureHeight = boardDim[2] + _wall + standOffHeight + _heightExtension;
  enclosureHeight = enclosure_height( boardDim, _wall, _heightExtension);

  pcbCenter=pcbPos+[pcbDim[0]/2, pcbDim[1]/2,0];
  Lid_screw_x= enclosureWidth_2-Lid_screw_head_r;
  Lid_screw_y= enclosureDepth_2-Lid_screw_head_r;
  Lid_screw_z= enclosureHeight-Lid_screw_h+Epaisseur_couvercle+0.01;
  Lid_screw_housing_x=Lid_screw_x;
  Lid_screw_housing_y=Lid_screw_y;
  Lid_screw_housing_z=enclosureHeight-Lid_screw_housing_h;

  difference()
    {
    union()
      {
      difference()
        {
        //Main box shape
        boundingBox(_boardShape, _components, _pcbHeight, _offset = _wall + _offset, height = enclosureHeight, _cornerRadius = _wall, include=PCB);

        translate([ 0, 0, _wall])
          {
          //Interior of box
          boundingBox(_boardShape, _components, _pcbHeight, _offset = _offset, height = enclosureHeight, _cornerRadius = _wall, include=PCB);

          //Punch outs for USB and POWER
          translate([0, 0, standOffHeight])
            {
            components( _components, _offset = 1, extension = _wall + _offset + 10, _pcbHeight= _pcbHeight);
            }
          }

        //Holes for lid clips
        /*
        translate([0,+enclosureDepth * 0.25, enclosureHeight])
          {
          tx(-_offset - boardDim[0]/2) rotate([0, 180,  90]) clipHole(clipHeight = 10, holeDepth = _wall + 0.2);
          tx(+_offset + boardDim[0]/2) rotate([0, 180, 270]) clipHole(clipHeight = 10, holeDepth = _wall + 0.2);
          }

        translate([0,-enclosureDepth * 0.25, enclosureHeight])
          {
          tx(-_offset - dimensions[0]/2) rotate([0, 180,  90]) clipHole(clipHeight = 10, holeDepth = _wall + 0.2);
          tx(+_offset + dimensions[0]/2) rotate([0, 180, 270]) clipHole(clipHeight = 10, holeDepth = _wall + 0.2);
          }
        */
        }
      translate([0, 0, _wall])
        {
        standoffs( _boardHoles, _boardPlots, height = standOffHeight, _mountType = _mountType);
        }
      translate(pcbCenter)
        {
        if (search(_lid_screws,"1"))tx(+(Lid_screw_housing_x+(search(_lid_screws_outer,"1")?_wall:0)))ty(+(Lid_screw_housing_y+(search(_lid_screws_outer,"1")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
        if (search(_lid_screws,"2"))tx(+(Lid_screw_housing_x+(search(_lid_screws_outer,"2")?_wall:0)))ty(-(Lid_screw_housing_y+(search(_lid_screws_outer,"2")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
        if (search(_lid_screws,"3"))tx(-(Lid_screw_housing_x+(search(_lid_screws_outer,"3")?_wall:0)))ty(-(Lid_screw_housing_y+(search(_lid_screws_outer,"3")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
        if (search(_lid_screws,"4"))tx(-(Lid_screw_housing_x+(search(_lid_screws_outer,"4")?_wall:0)))ty(+(Lid_screw_housing_y+(search(_lid_screws_outer,"4")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
        }
      }

    translate(pcbCenter)
      {
      if (search(_lid_screws,"1"))tx(+(Lid_screw_x+(search(_lid_screws_outer,"1")?_wall:0)))ty(+(Lid_screw_y+(search(_lid_screws_outer,"1")?_wall:0)))tz(Lid_screw_z)Lid_screw();
      if (search(_lid_screws,"2"))tx(+(Lid_screw_x+(search(_lid_screws_outer,"2")?_wall:0)))ty(-(Lid_screw_y+(search(_lid_screws_outer,"2")?_wall:0)))tz(Lid_screw_z)Lid_screw();
      if (search(_lid_screws,"3"))tx(-(Lid_screw_x+(search(_lid_screws_outer,"3")?_wall:0)))ty(-(Lid_screw_y+(search(_lid_screws_outer,"3")?_wall:0)))tz(Lid_screw_z)Lid_screw();
      if (search(_lid_screws,"4"))tx(-(Lid_screw_x+(search(_lid_screws_outer,"4")?_wall:0)))ty(+(Lid_screw_y+(search(_lid_screws_outer,"4")?_wall:0)))tz(Lid_screw_z)Lid_screw();
      }
    }
}

//Create a snap on lid for enclosure
//parameter ventHoles = false removed (not implemented in original library)
module enclosureLid( _boardShape, _components, _pcbHeight= pcbHeight, _wall = 3, _offset = 3, _cornerRadius = 3,
                     _lid_screws= "1234",
                     _lid_screws_outer= "1234")
  {
  dimensions= boardDimensions( _boardShape, _components, _pcbHeight);
  boardDim  = boardDimensions( _boardShape, _components, _pcbHeight);
  pcbDim    = pcbDimensions  ( _boardShape, _pcbHeight);
  pcbPos    = pcbPosition    ( _boardShape);

  enclosureWidth = pcbDim[0] + (_wall + _offset) * 2; enclosureWidth_2= enclosureWidth/2;
  enclosureDepth = pcbDim[1] + (_wall + _offset) * 2; enclosureDepth_2= enclosureDepth/2;

  pcbCenter=pcbPos+[pcbDim[0]/2, pcbDim[1]/2,0];
  Lid_screw_x= enclosureWidth_2-Lid_screw_head_r;
  Lid_screw_y= enclosureDepth_2-Lid_screw_head_r;
  Lid_screw_z= -Lid_screw_h+Epaisseur_couvercle+0.01;

  Lid_screw_housing_x=Lid_screw_x;
  Lid_screw_housing_y=Lid_screw_y;
  Lid_screw_housing_z=-Lid_screw_housing_h+Epaisseur_couvercle+0.01;

  difference()
    {
    union()
      {
      boundingBox(_boardShape, _components, _pcbHeight, _offset = _wall + _offset, height = _wall, _cornerRadius = _wall, include=PCB);

      translate([0, 0, -_wall * 0.5])
        boundingBox(_boardShape, _components, _pcbHeight, _offset = _offset - 0.5, height = _wall * 0.5, _cornerRadius = _wall, include=PCB);
    
      //Lid clips

      /*
      ty(+enclosureDepth * 0.25)
        {
        tx(-_offset - boardDim[0]/2) rotate([0, 180,  90]) clip(clipHeight = 10);
        tx(+_offset + boardDim[0]/2) rotate([0, 180, 270]) clip(clipHeight = 10);
        }
    
      ty(-enclosureDepth * 0.25)
        {
        tx(-_offset - dimensions[0]/2) rotate([0, 180,  90]) clip(clipHeight = 10);
        tx(+_offset + dimensions[0]/2) rotate([0, 180, 270]) clip(clipHeight = 10);
        }
      */
      difference( )
        {
        translate(pcbCenter)
          {
          if (search(_lid_screws,"1"))tx(+(Lid_screw_housing_x+(search(_lid_screws_outer,"1")?_wall:0)))ty(+(Lid_screw_housing_y+(search(_lid_screws_outer,"1")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
          if (search(_lid_screws,"2"))tx(+(Lid_screw_housing_x+(search(_lid_screws_outer,"2")?_wall:0)))ty(-(Lid_screw_housing_y+(search(_lid_screws_outer,"2")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
          if (search(_lid_screws,"3"))tx(-(Lid_screw_housing_x+(search(_lid_screws_outer,"3")?_wall:0)))ty(-(Lid_screw_housing_y+(search(_lid_screws_outer,"3")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
          if (search(_lid_screws,"4"))tx(-(Lid_screw_housing_x+(search(_lid_screws_outer,"4")?_wall:0)))ty(+(Lid_screw_housing_y+(search(_lid_screws_outer,"4")?_wall:0)))hull(){sphere(r=0.01);tz(Lid_screw_housing_z)Lid_screw_housing();};
          }
        tz(-Lid_screw_housing_h)boundingBox(_boardShape, _components, _pcbHeight, _offset = _wall + _offset+Lid_screw_housing_d, height = Lid_screw_housing_h, _cornerRadius = _wall, include=PCB);
        };
      }
    translate(pcbCenter)
      {
      if (search(_lid_screws,"1"))tx(+(Lid_screw_x+(search(_lid_screws_outer,"1")?_wall:0)))ty(+(Lid_screw_y+(search(_lid_screws_outer,"1")?_wall:0)))tz(Lid_screw_z+0.01)Lid_screw();
      if (search(_lid_screws,"2"))tx(+(Lid_screw_x+(search(_lid_screws_outer,"2")?_wall:0)))ty(-(Lid_screw_y+(search(_lid_screws_outer,"2")?_wall:0)))tz(Lid_screw_z+0.01)Lid_screw();
      if (search(_lid_screws,"3"))tx(-(Lid_screw_x+(search(_lid_screws_outer,"3")?_wall:0)))ty(-(Lid_screw_y+(search(_lid_screws_outer,"3")?_wall:0)))tz(Lid_screw_z+0.01)Lid_screw();
      if (search(_lid_screws,"4"))tx(-(Lid_screw_x+(search(_lid_screws_outer,"4")?_wall:0)))ty(+(Lid_screw_y+(search(_lid_screws_outer,"4")?_wall:0)))tz(Lid_screw_z+0.01)Lid_screw();
      }
    }
}

//Offset from board. Negative values are insets
module boardShape( _boardShape, _components, _pcbHeight=pcbHeight, _offset = 0)
  {
  dimensions = boardDimensions( _boardShape, _components, _pcbHeight);

  xScale = (dimensions[0] + _offset * 2) / dimensions[0];
  yScale = (dimensions[1] + _offset * 2) / dimensions[1];

  translate([-_offset, -_offset, 0])
    scale([xScale, yScale, 1.0])
      linear_extrude(height = _pcbHeight)
        polygon(points = _boardShape);
  }

//Create a bounding box around the board
//Offset - will increase the size of the box on each side,
//Height - overides the boardHeight and offset in the z direction

BOARD = 0;        //Includes all components and PCB
PCB = 1;          //Just the PCB
COMPONENTS = 2;   //Just the components

module boundingBox( _boardShape, _components, _pcbHeight=pcbHeight, _offset = 0, height = 0, _cornerRadius = 0, include = BOARD)
  {
  //What parts are included? Entire board, pcb or just components.
  pos
  =
   ([
          boardPosition( _boardShape, _components, _pcbHeight),
            pcbPosition( _boardShape),
     componentsPosition( _components, _pcbHeight)
   ])[include];
  dim
  =
   ([
          boardDimensions( _boardShape, _components, _pcbHeight),
            pcbDimensions( _boardShape, _pcbHeight),
     componentsDimensions( _components)
   ])[include];

  //Depending on if height is set position and dimensions will change
  position
  =
   [
   pos[0] - _offset,
   pos[1] - _offset,
   (height == 0 ? pos[2] - _offset : pos[2] )
   ];

  dimensions
  =
   [
   dim[0] + _offset * 2,
   dim[1] + _offset * 2,
   (height == 0 ? dim[2] + _offset * 2 : height)
   ];

  translate( position )
    {
    if( _cornerRadius == 0 )
      {
      cube( dimensions );
      }
    else
      {
      roundedCube( dimensions, _cornerRadius=_cornerRadius );
      }
    }
  }

//Creates standoffs for different boards
TAPHOLE = 0;
PIN = 1;

module standoffs( _boardHoles,
                  _boardPlots,
                  height = 10,
                  topRadius = mountingHoleRadius + 1,
                  bottomRadius =  mountingHoleRadius + 2,
                  holeRadius = mountingHoleRadius,
                  _mountType = TAPHOLE
                  )
  {

  holePlacement( _boardHoles)
    union()
      {
      difference()
        {
        cylinder(r1 = bottomRadius, r2 = topRadius, h = height, $fn=32);
        if( _mountType == TAPHOLE )
          {
          cylinder(r =  holeRadius, h = height * 4, center = true, $fn=32);
          }
        }
      if( _mountType == PIN )
        {
        translate([0, 0, height - 1])
        pintack( h=pcbHeight + 3, r = holeRadius, lh=3, lt=1, bh=1, br=topRadius );
        }
      }
  PlotPlacement( _boardPlots)
    cylinder(r = PlotRadius, h = height+PlotHeight, $fn = 32);
  }

//This is used for placing the mounting holes and for making standoffs
//child elements will be centered on that chosen boards mounting hole centers
module holePlacement( _boardHoles )
  {
  for(i = _boardHoles )
    {
    translate(i)
      children(0);
    }
  }

module PlotPlacement( _boardPlots)
  {
  Plots= _boardPlots;
  if( 0 < len(Plots))
    for(i = Plots )
      {
      translate(i)
        children(0);
      }
  }

//Places components on board
//  compenent - the data set with a particular component (like boardHeaders)
//  extend - the amount to extend the component in the direction of its socket
//  _offset - the amount to increase the components other two boundaries

//Component IDs
ALL = "";
HEADER_F = "HEADER_F";
HEADER_M = "HEADER_M";
USB = "USB";
POWER = "POWER";
RJ45 = "RJ45";
GROVE_CONNECTOR="GROVE_CONNECTOR";

module components( _components, component = ALL, extension = 0, _offset = 0 , _pcbHeight= pcbHeight)
  {
  translate([0, 0, _pcbHeight])
    {
    for( i = [0:len(_components) - 1] )
      {
      if( _components[i][3] == component || component == ALL)
        {
        //Calculates position + adjustment for offset and extention
        position
        =
            _components[i][0]
          - (([1,1,1] - _components[i][2]) * _offset)
          + [  min(_components[i][2][0],0), min(_components[i][2][1],0), min(_components[i][2][2],0) ]
            * extension;
        //Calculates the full box size including offset and extention
        dimensions
        =
            _components[i][1]
          + (
              (_components[i][2] * [1,1,1])
             * _components[i][2]
            ) * extension
          + ([1,1,1] - _components[i][2]) * _offset * 2;
        translate( position )
          color( _components[i][4] )
            cube( dimensions );
        }
      }
    }
  }

module roundedCube( dimensions = [10,10,10], _cornerRadius = 1, faces=32 ) {
  hull() cornerCylinders( dimensions = dimensions, _cornerRadius = _cornerRadius, faces=faces );
}

module cornerCylinders( dimensions = [10,10,10], _cornerRadius = 1, faces=32 ) {
  translate([ _cornerRadius, _cornerRadius, 0]) {
    cylinder( r = _cornerRadius, $fn = faces, h = dimensions[2] );
    translate([dimensions[0] - _cornerRadius * 2, 0, 0]) cylinder( r = _cornerRadius, $fn = faces, h = dimensions[2] );
    translate([0, dimensions[1] - _cornerRadius * 2, 0]) {
      cylinder( r = _cornerRadius, $fn = faces, h = dimensions[2] );
      translate([dimensions[0] - _cornerRadius * 2, 0, 0]) cylinder( r = _cornerRadius, $fn = faces, h = dimensions[2] );
    }
  }
}

//Create a clip that snapps into a clipHole
module clip(clipWidth = 5, clipDepth = 5, clipHeight = 5, lipDepth = 1.5, lipHeight = 3) {
  translate([-clipWidth/2,-(clipDepth-lipDepth),0]) rotate([90, 0, 90])
  linear_extrude(height = clipWidth, convexity = 10)
    polygon(  points=[  [0, 0], 
            [clipDepth - lipDepth, 0],
            [clipDepth - lipDepth, clipHeight - lipHeight],
            [clipDepth - 0.25, clipHeight - lipHeight],
            [clipDepth, clipHeight - lipHeight + 0.25],
            [clipDepth - lipDepth * 0.8, clipHeight],
            [(clipDepth - lipDepth) * 0.3, clipHeight] 
            ], 
        paths=[[0,1,2,3,4,5,6,7]]
      );
}

//Hole for clip
module clipHole(clipWidth = 5, clipDepth = 5, clipHeight = 5, lipDepth = 1.5, lipHeight = 3, holeDepth = 5) {
  offset = 0.1;
  translate([-clipWidth/2,-(clipDepth-lipDepth),0])
  translate([-offset, clipDepth - lipDepth-offset, clipHeight - lipHeight - offset])
    cube( [clipWidth + offset * 2, holeDepth, lipHeight + offset * 2] );
}

module mountingHole(screwHeadRad = bumper_woodscrewHeadRad, screwThreadRad = bumper_woodscrewThreadRad, screwHeadHeight = bumper_woodscrewHeadHeight, holeDepth = 10)
  {
  union()
    {
    translate([0, 0, -0.01])
      cylinder( r = screwThreadRad, h = 1.02, $fn = 32 );
    translate([0, 0, 1])
      cylinder( r1 = screwThreadRad, r2 = screwHeadRad, h = screwHeadHeight, $fn = 32 );
    translate([0, 0, screwHeadHeight - 0.01 + 1])
      cylinder( r = screwHeadRad, h = holeDepth - screwHeadHeight + 0.02, $fn = 32 );
    }
  }

/******************************** UTILITY FUNCTIONS *******************************/

//Return the length side of a square given its diagonal
function sides( diagonal ) = sqrt(diagonal * diagonal  / 2);

//Return the minimum values between two vectors of either length 2 or 3. 2D Vectors are treated as 3D vectors who final value is 0.
function minVec( vector1, vector2 ) =
  [min(vector1[0], vector2[0]), min(vector1[1], vector2[1]), min((vector1[2] == undef ? 0 : vector1[2]), (vector2[2] == undef ? 0 : vector2[2]) )];

//Return the maximum values between two vectors of either length 2 or 3. 2D Vectors are treated as 3D vectors who final value is 0.
function maxVec( vector1, vector2 ) =
  [max(vector1[0], vector2[0]), max(vector1[1], vector2[1]), max((vector1[2] == undef ? 0 : vector1[2]), (vector2[2] == undef ? 0 : vector2[2]) )];

//Determine the minimum point on a component in a list of components
function minCompPoint( list, index = 0, minimum = [10000000, 10000000, 10000000] ) = 
  index >= len(list) ? minimum : minCompPoint( list, index + 1, minVec( minimum, list[index][0] ));

//Determine the maximum point on a component in a list of components
function maxCompPoint( list, index = 0, maximum = [-10000000, -10000000, -10000000] ) = 
  index >= len(list) ? maximum : maxCompPoint( list, index + 1, maxVec( maximum, list[index][0] + list[index][1]));

//Determine the minimum point in a list of points
function minPoint( list, index = 0, minimum = [10000000, 10000000, 10000000] ) = 
  index >= len(list) ? minimum : minPoint( list, index + 1, minVec( minimum, list[index] ));

//Determine the maximum point in a list of points
function maxPoint( list, index = 0, maximum = [-10000000, -10000000, -10000000] ) = 
  index >= len(list) ? maximum : maxPoint( list, index + 1, maxVec( maximum, list[index] ));

//Returns the pcb position and dimensions
function pcbPosition  ( _boardShape                      ) = minPoint( _boardShape);
function pcbDimensions( _boardShape, _pcbHeight=pcbHeight) = maxPoint( _boardShape) - minPoint(_boardShape) + [0, 0, _pcbHeight];

//Returns the position of the box containing all components and its dimensions
function componentsPosition  ( _components, _pcbHeight=pcbHeight) = minCompPoint(_components) + [0, 0, _pcbHeight];
function componentsDimensions( _components                      ) = maxCompPoint(_components) - minCompPoint(_components);

//Returns the position and dimensions of the box containing the pcb board
function boardPosition( _boardShape, _components, _pcbHeight=pcbHeight)
=
 minCompPoint([
                [
                pcbPosition  (_boardShape),
                pcbDimensions(_boardShape, _pcbHeight)
                ],
                [
                componentsPosition  (_components, _pcbHeight),
                componentsDimensions(_components)
                ]
              ]);

function boardDimensions( _boardShape, _components, _pcbHeight=pcbHeight)
=
 maxCompPoint(
   [
     [
     pcbPosition  (_boardShape),
     pcbDimensions(_boardShape, _pcbHeight)
     ],
     [
     componentsPosition  (_components, _pcbHeight),
     componentsDimensions(_components)
     ]
   ])
 - minCompPoint(
   [
     [
     pcbPosition  (_boardShape),
     pcbDimensions(_boardShape)
     ],
     [
     componentsPosition  ( _components, _pcbHeight),
     componentsDimensions( _components)
     ]
   ]);


