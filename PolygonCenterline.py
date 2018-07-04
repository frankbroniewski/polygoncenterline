# -*- coding: utf-8 -*-

"""
***************************************************************************
    PolygonCenterline.py
    ---------------------
    Date                 : June 2018
    Copyright            : (C) 2018 by Frank Broniewski
    Email                : hallo at frankbroniewski dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Frank Broniewski'
__date__ = 'June 2018'
__copyright__ = '(C) 2018, Frank Broniewski'

__revision__  = '$Format:%H$'


from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsApplication,
                       QgsFeature,
                       QgsProcessing,
                       QgsExpression,
                       QgsFeatureRequest,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingOutputVectorLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorDestination)

import processing


class PolygonCenterline(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QCoreApplication.translate("Processing", text)

    def createInstance(self):
        return type(self)()

    def icon(self):
        return QgsApplication.getThemeIcon("algorithms/mAlgorithmDelaunay.svg")

    def svgIconPath(self):
        return QgsApplication.iconPath("algorithms/mAlgorithmDelaunay.svg")

    def group(self):
        return self.tr('Cartography')

    def groupId(self):
        return 'cartography'

    def name(self):
        return 'polygoncenterline'

    def displayName(self):
        return self.tr('Calculate a polygon centerline')

    def shortHelpString(self):
        return self.tr('Calculate a polygon centerline for pretty cartographic labeling of polygon features')

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Vector Polygon Layer"),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.DISTANCE,
                self.tr('Point distance value (for Voronoi creation)'),
                type=QgsProcessingParameterNumber.Double,
                minValue=10.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Center line')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        # 1 qgis:pointsalonglines
        params = {
            'INPUT': parameters[self.INPUT], 
            'DISTANCE': parameters[self.DISTANCE],
            'START_OFFSET': 0,
            'END_OFFSET': 0,
            'OUTPUT': 'memory:'
        }
        points = self._run_process('qgis:pointsalonglines', params, context,
                                   feedback)

        # 2 qgis:voronoipolygons
        params = {
            'INPUT': points,
            'BUFFER': 0,
            'OUTPUT': 'memory:'
        }
        voronoi = self._run_process('qgis:voronoipolygons', params, context, 
                                    feedback)

        # 3 native:clip
        params = {
            'INPUT': voronoi,
            'OVERLAY': parameters[self.INPUT],
            'OUTPUT': 'memory:'
        }
        clipped = self._run_process('native:clip', params, context, feedback)

        # 4 qgis:polygonstolines
        params = {
            'INPUT': clipped,
            'OUTPUT': 'memory:'
        }
        polygon_lines = self._run_process('qgis:polygonstolines', params,
                                          context, feedback)

        # 5 native:explodelines
        params = {
            'INPUT': polygon_lines,
            'OUTPUT': 'memory:'
        }
        exploded = self._run_process('native:explodelines', params, context,
                                     feedback)

        # 6 qgis:deleteduplicategeometries
        params = {
            'INPUT': exploded,
            'OUTPUT': 'memory:'
        }
        cleaned_voronoi = self._run_process('qgis:deleteduplicategeometries',
                                            params, context, feedback)

        # 7 native:dissolve
        params = {
            'INPUT': clipped,
            'FIELD': None,
            'OUTPUT': 'memory:'
        }
        dissolved = self._run_process('native:dissolve', params, context,
                                     feedback)

        # 8 qgis:polygonstolines
        params = {
            'INPUT': dissolved,
            'OUTPUT': 'memory:'
        }
        outline = self._run_process('qgis:polygonstolines', params, context,
                                    feedback)

        # 9 native:selectbylocation
        params = {
            'INPUT': cleaned_voronoi,
            'PREDICATE': 0,
            'INTERSECT': outline,
            'METHOD': 0
        }
        selection = self._run_process('native:selectbylocation', params,
                                      context, feedback)

        # 10 native:dropgeometries (selected)
        selection.startEditing()
        selection.deleteSelectedFeatures()
        selection.commitChanges()

        # native:extractvertices
        params = {
            'INPUT': selection,
            'OUTPUT': 'memory:'
        }
        vertices = self._run_process('native:extractvertices', params, context,
                                     feedback)

        # qgis:deleteduplicategeometries
        params = {
            'INPUT': vertices,
            'OUTPUT': 'memory:'
        }
        cleaned_vertices = self._run_process('qgis:deleteduplicategeometries',
                                             params, context, feedback)

        # native:addautoincrementalfield
        params = {
            'INPUT': cleaned_vertices,
            'FIELD_NAME': 'vid',
            'START': 1,
            'OUTPUT': 'memory:'
        }
        vid = self._run_process('native:addautoincrementalfield', params,
                                context, feedback)

        # qgis:distancematrix
        params = {
            'INPUT': vid,
            'INPUT_FIELD': 'vid',
            'TARGET': vid,
            'TARGET_FIELD': 'vid',
            'MATRIX_TYPE': 0,
            'NEAREST_POINTS': 0,
            'OUTPUT': 'memory:'
        }
        matrix = self._run_process('qgis:distancematrix', params, context,
                                   feedback)

        max_distance = 0
        max_feature = None
        for feature in matrix.getFeatures():
            if feature['Distance'] > max_distance:
                feedback.pushDebugInfo(
                    "tf %s, if %s, dis %s" %
                    (feature['TargetID'],
                     feature['InputID'],
                     feature['Distance'])
                )
                max_distance = feature['Distance']
                max_feature = QgsFeature(feature)

        if not max_feature:
            raise QgsExpression('Could not select maximum distance, aborting')

        target_expr = "vid=%s" % max_feature['TargetID']
        target_features = vid.getFeatures(
            QgsFeatureRequest(QgsExpression(target_expr))
        )
        target_feature = next(target_features)

        input_expr = "vid=%s" % max_feature['InputID']
        input_features = vid.getFeatures(
            QgsFeatureRequest(QgsExpression(input_expr))
        )
        input_feature = next(input_features)


        feedback.pushDebugInfo(
            "%s, %s" % (
                input_feature.geometry().asPoint().x(),
                input_feature.geometry().asPoint().y()
            )
        )
        feedback.pushDebugInfo(
            "%s, %s" % (
                target_feature.geometry().asPoint().x(),
                target_feature.geometry().asPoint().y()
            )
        )

        # qgis:shortestpathpointtopoint
        params = {
            'INPUT': selection,
            'START_POINT': input_feature.geometry().asPoint(),
            'END_POINT': target_feature.geometry().asPoint(),
            'STRATEGY': 0,
            'DEFAULT_DIRECTION': 2,
            'DEFAULT_SPEED': 5,
            'TOLERANCE': 1,
            'OUTPUT': 'memory:'
        }
        route = self._run_process('qgis:shortestpathpointtopoint', params,
                                   context, feedback)

        #  native:simplifygeometries
        params = {
            'INPUT': route,
            'METHOD': 0,
            'TOLERANCE': 5,
            'OUTPUT': 'memory:'
        }
        peucker = self._run_process('native:simplifygeometries', params,
                                    context, feedback)

        # native:smoothgeometry
        params = {
            'INPUT': peucker,
            'ITERATIONS': 10,
            'OFFSET': 0.25,
            'MAX_ANGLE': 180,
            'OUTPUT': parameters[self.OUTPUT]
        }
        smooth = self._run_process('native:smoothgeometry', params, context, 
                                   feedback)
        context.temporaryLayerStore().addMapLayer(smooth)

        return {self.OUTPUT: smooth.id()}
    

    def _run_process(self, name, params, context, feedback):
        proc = processing.run(name, params, context=context, feedback=feedback)
        return proc['OUTPUT']