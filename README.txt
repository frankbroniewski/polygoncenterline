PolygonCenterline
=================
Calculate a center line for a given polygon. The purpose is to get a line for 
labeling polygons along the center line. This is mainly for nice cartographic
labeling purposes.


ATTENTION please!
=================
The script is still a bit exerimental. It works with a single polygon in a single 
layer in a metric CRS. I still need to do more input checks before calling 
this stable ... but the excitemnet took me over ;-)


Usage
=====
Download the script and use the "Add Script to Toolbox" menu from the processing 
toobox.

Once added, start the script found under Scripts->Cartography->Calculate a polygon
centerline.

The script demands for a polygon - obviously - and a point distance value. This
value is used in one of the first steps of the center line determination process.
It creates a set of points at the given distance around the outline of the
polygon. I advise to use polygons in a projected CRS where you can use metric
values as the input.

If everything goes well you get a nice and smooth center line fit for labeling.


QGIS Requirements
=================
The script needs QGIS 3.0 or higher in order to work. It solely relies on
tools provided by QGIS.


Idea
====
I got the idea to make a processing script from this tweet:
https://twitter.com/veltman/status/973570650429206528

ESRI has one for tons of money in Production Mapping extension, so we need one
for free #OpenSource