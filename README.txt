PolygonCenterline
=================
Calculate a center line for a given polygon layer. The purpose is to get a line
for labeling polygons along their center line. This is mainly for nice cartographic
labeling purposes.


Issues
======
The script is quite slow at the moment and the route finding process is not
optimal.
Report and search for more issues on the issue tracker:
https://github.com/frankbroniewski/polygoncenterline/issues


Usage
=====
Download the script and use the "Add Script to Toolbox" menu from the processing 
toobox.

Once added, start the script found under Scripts->Cartography->Calculate a polygon
centerline.

The script demands for a polygon layer. I advise to use polygons in a projected 
CRS.

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