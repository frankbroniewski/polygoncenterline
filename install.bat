@ECHO OFF
SET CWD=%CD%
SET SCRIPT=PolygonCenterline.py
SET PROFILE=%userprofile%\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts\

IF EXIST %PROFILE%\%SCRIPT%  (
    del %PROFILE%\%SCRIPT%
)

copy "%CD%\%SCRIPT%" "%PROFILE%\%SCRIPT%"