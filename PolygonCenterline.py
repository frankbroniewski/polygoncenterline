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

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication

from qgis.core import (QgsApplication,
                       QgsFeature,
                       QgsWkbTypes,
                       QgsProcessing,
                       QgsExpression,
                       QgsFeatureRequest,
                       QgsFeatureSink,
                       QgsVectorLayer,
                       QgsProcessingFeedback,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingOutputVectorLayer,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorDestination)

import processing


class PolygonCenterline(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    SMOOTH = 'SMOOTH'
    OUTPUT = 'OUTPUT'

    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QCoreApplication.translate("Processing", text)

    def createInstance(self):
        return type(self)()

    def icon(self):
        return QgsApplication.getThemeIcon("algorithms/mAlgorithmDelaunay.svg")

    def helpString(self):
        # h = 
        return self.tr("""Calculate a polygon centerline for pretty cartographic labeling of polygon features.

INPUT: a single polygon feature, no Multipolygon allowed here"""
        )

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
        return self.helpString()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Vector Polygon Layer"),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SMOOTH,
                self.tr('Smooth line?'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Center line')
            )
        )


    def processAlgorithm(self, parameters, context, feedback):

        source = self.parameterAsSource(parameters, self.INPUT, context)
        self.validate_input(source, parameters, context, feedback)

        feedback.pushInfo('Creating polygon center lines for %s polygons'
                          % source.featureCount())
        features = source.getFeatures()
        crs = source.sourceCrs()

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            # QgsWkbTypes.Point,
            QgsWkbTypes.LineString,
            crs
        )

        for count, feature in enumerate(features, start=1):
            feedback.pushInfo('Working on feature %s' % count)

            network = self.calc_network(feature, crs, context,
                                        feedback)
            end_points = self.calc_end_points(network, context, feedback)
            centerline = self.calc_centerline(network, end_points, context, 
                                              feedback)

            # we need the centerline only for its geometry
            # & copy the attributes over from the current feature
            for cf in centerline.getFeatures():
                f = QgsFeature()
                f.setGeometry(cf.geometry())
                f.setAttributes(feature.attributes())
                sink.addFeature(f)

        # return if no smoothing should be applied
        if not parameters['SMOOTH']:
            return {self.OUTPUT: dest_id}

        #  native:simplifygeometries
        params = {
            'INPUT': dest_id,
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
        smooth.setName('Center line')
        context.temporaryLayerStore().addMapLayer(smooth)

        return {self.OUTPUT: smooth.id()}


    def calc_network(self, polygon, crs, context, feedback):
        """calculate voronoi network for given polygon retrieving the
            'inner' network"""

        # we calculate the distance value for qgis:pointsalonglines with a 
        # percentage instead of a fixed value; less input and better 
        # adaptibility with varying polygon sizes. A value of 0.03% seems good
        perimeter = polygon.geometry().length()
        distance = perimeter * 0.025

        # we're creating a temp layer here for the feature so it's usable in 
        # processing
        lyr = self.layer_from_feature(polygon, crs)
        prov = lyr.dataProvider()

        if not lyr.isValid():
            msg = 'Cannot prepare network: Unable to create layer from feature'
            raise QgsProcessingException(msg)

        (success, _) = prov.addFeatures([polygon])
        if not success:
            msg = 'Cannot prepare network: Cannot add feature to temporary layer'
            raise QgsProcessingException(msg)

        # 1 qgis:pointsalonglines
        # take input and create points around geometry
        params = {
            'INPUT': lyr, 
            'DISTANCE': distance,
            'START_OFFSET': 0,
            'END_OFFSET': 0,
            'OUTPUT': 'memory:'
        }
        points = self._run_process('qgis:pointsalonglines', params, context,
                                   feedback)

        # 2 qgis:voronoipolygons
        # create voronoi from step 1 points
        params = {
            'INPUT': points,
            'BUFFER': 0,
            'OUTPUT': 'memory:'
        }
        voronoi = self._run_process('qgis:voronoipolygons', params, context, 
                                    feedback)

        # 3 native:clip
        # clip voronoi from step 2 to input polygon
        params = {
            'INPUT': voronoi,
            'OVERLAY': lyr,
            'OUTPUT': 'memory:'
        }
        clipped = self._run_process('native:clip', params, context, feedback)

        # 4 qgis:polygonstolines
        # turn voronoi polygon into lines
        params = {
            'INPUT': clipped,
            'OUTPUT': 'memory:'
        }
        polygon_lines = self._run_process('qgis:polygonstolines', params,
                                          context, feedback)

        # 5 native:explodelines
        # voronoi network line cleanup
        params = {
            'INPUT': polygon_lines,
            'OUTPUT': 'memory:'
        }
        exploded = self._run_process('native:explodelines', params, context,
                                    feedback)

        # 6 qgis:deleteduplicategeometries
        # voronoi network line cleanup
        params = {
            'INPUT': exploded,
            'OUTPUT': 'memory:'
        }
        cleaned_voronoi = self._run_process('qgis:deleteduplicategeometries',
                                            params, context, feedback)

        # 7 native:dissolve
        # dissolve voronoi polygon into one single polygon
        # create outline from voronoi (remove outer boundary from network)
        params = {
            'INPUT': clipped,
            'FIELD': None,
            'OUTPUT': 'memory:'
        }
        dissolved = self._run_process('native:dissolve', params, context,
                                      feedback)

        # 8 qgis:polygonstolines
        # create outline from voronoi (remove outer boundary from network)
        params = {
            'INPUT': dissolved,
            'OUTPUT': 'memory:'
        }
        outline = self._run_process('qgis:polygonstolines', params, context,
                                    feedback)

        # 9 native:selectbylocation
        # select outline from network and remove it
        params = {
            'INPUT': cleaned_voronoi,
            'PREDICATE': 0,
            'INTERSECT': outline,
            'METHOD': 0
        }
        network = self._run_process('native:selectbylocation', params,
                                    context, feedback)

        # 10 native:dropgeometries (selected)
        # delete selection (outline)
        network.startEditing()
        network.deleteSelectedFeatures()
        network.commitChanges()

        return network


    def calc_end_points(self, network, context, feedback):
        """Calculate network end points for routing"""
        # 11 native:extractvertices
        # get vertices from network -> find end point nodes
        params = {
            'INPUT': network,
            'OUTPUT': 'memory:'
        }
        vertices = self._run_process('native:extractvertices', params,
                                     context, feedback)

        # 12 add our own id field for count summary
        # native:addautoincrementalfield
        params = {
            'INPUT': vertices,
            'FIELD_NAME': 'vid',
            'START': 1,
            'OUTPUT': 'memory:'
        }
        id_vertices = self._run_process('native:addautoincrementalfield', params,
                                        context, feedback)

        # calculate summary how many features intersect at each place
        # we want features with only 1 count -> these are end points
        # the end points are used for the routing algorithm
        # 13 qgis:joinbylocationsummary
        params = {
            'INPUT': id_vertices,
            'JOIN': id_vertices,
            'PREDICATE': 0,
            'SUMMARIES': 0,
            'DISCARD_NONMATCHING': True,
            'OUTPUT': 'memory:'
        }
        joined = self._run_process('qgis:joinbylocationsummary', params,
                                   context, feedback)

        # 14 select where distance_count = 1
        # qgis:selectbyattribute
        params = {
            'INPUT': joined,
            'FIELD': 'vid_count',
            'OPERATOR': 2,
            'VALUE': '1',
            'METHOD': 0
        }
        end_points = self._run_process('qgis:selectbyattribute', params, context,
                                       feedback)
        end_points.startEditing()
        end_points.deleteSelectedFeatures()
        end_points.commitChanges()

        return end_points


    def calc_centerline(self, network, end_points, context, feedback):
        """returns the centerline from a network calculated by end points"""

        center_line = None
        max_cost = 0

        features = end_points.getFeatures()
        for point in features:
            # start point
            sp =  '%s,%s' % (
                point.geometry().asPoint().x(),
                point.geometry().asPoint().y()
            )
            params = {
                'INPUT': network,
                'START_POINT': sp,
                'END_POINTS': end_points,
                'STRATEGY': 0,
                'DEFAULT_DIRECTION': 2,
                'DEFAULT_SPEED': 5,
                'TOLERANCE': 1,
                'OUTPUT': 'memory:'
            }
            route = self._run_process('qgis:shortestpathpointtolayer', params, 
                                      context, feedback)
            cost, most_expensive_route = self.cost_route(route, feedback)

            if center_line is None:
                center_line = self.duplicate_layer(most_expensive_route, feedback)
                max_cost = cost
            elif max_cost < cost:
                center_line = self.duplicate_layer(most_expensive_route, feedback)
                max_cost = cost
        
        return center_line


    def _run_process(self, name, params, context, feedback):
        """wrapper: run a QGIS processing framework process"""

        if feedback.isCanceled():
            exit()
        
        my_feedback = QgsProcessingFeedback()
        proc = processing.run(name, params, context=context,
                              feedback=my_feedback)
        return proc['OUTPUT']


    def validate_input(self, lyr, parameters, context, feedback):
        """Validate the input layer against several requirements"""
        
        if lyr is None:
            raise QgsProcessingException(self.invalidSourceError(parameters,
                                         self.INPUT))

        if lyr.featureCount() == 0:
            raise QgsProcessingException('Input layer has no features')

        if lyr.sourceCrs().isGeographic():
            msg = 'No geographic CRS for input layer allowed'
            raise QgsProcessingException(msg)

        if lyr.wkbType() == QgsWkbTypes.MultiPolygon:
            msg = 'No multipart feature allowed'
            raise QgsProcessingException(msg)


    def create_layer_string(self, geometry_type, fields, crs):
        """create a memory layer creation string from the given parameters"""

        # fields
        field_str = '&'.join([
            'field=%s:%s' % (f.name(), f.typeName())
            for f in fields
        ])

        # layer's geometryType() might return Line as geometry type
        # which is unsuitable for layer creation
        gtype = QgsWkbTypes.geometryDisplayString(geometry_type)
        if gtype.startswith('Line'):
            gtype = 'Linestring'

        return '{type}?crs={id}&{field_str}&index=yes'.format(
            type=gtype,
            id=crs.authid(),
            field_str=field_str
        )


    def duplicate_layer(self, layer, feedback):
        """create a copy/duplicate of the layer"""

        # lyr_str = self.create_layer_string(geometry_type, fields, crs)
        duplicate = QgsVectorLayer(layer.source(), 'Duplicate', 'memory')

        if not duplicate.isValid():
            feedback.pushDebugInfo(lyr_str)
            raise QgsProcessingException('Cannot duplicate layer')

        features = layer.getFeatures()
        prov = duplicate.dataProvider().addFeatures([f for f in features])

        if duplicate.featureCount() == 0:
            raise QgsProcessingException('No features in duplicate')

        return duplicate


    def layer_from_feature(self, feature, crs):
        """create a new layer based on the feature's properties and put the 
            feature in it"""

        geometry_type = feature.geometry().type()
        fields = feature.fields()

        lyr_str = self.create_layer_string(geometry_type, fields, crs)

        lyr = QgsVectorLayer(lyr_str, 'Layer from feature', 'memory')

        if not lyr.isValid():
            raise QgsProcessingException('Cannot create layer from feature')

        return lyr


    def cost_route(self, route, feedback):
        """Extract the route with the highest cost from network point to layer"""

        longest_route = QgsVectorLayer(route.source(), 'Longest route', 'memory')

        # better work on a duplicate here to not mess things up with selections
        dupl = self.duplicate_layer(route, feedback)
        dupl.removeSelection()

        # need the field's index for retrieval, not the name
        field_map = dupl.dataProvider().fieldNameMap()
        maximum = dupl.maximumValue(field_map['cost'])

        request = QgsFeatureRequest(QgsExpression("cost=%s" % maximum))
        longest_route.startEditing()
        for feature in dupl.getFeatures(request):
            longest_route.addFeature(feature)
        longest_route.commitChanges()

        return (maximum, longest_route)