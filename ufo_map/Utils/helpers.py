# -*- coding: utf-8 -*-
"""
Created on Tue Mar 24 09:52:35 2020

@author: miln
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt
from shapely.geometry import MultiPolygon


def import_csv_w_wkt_to_gdf(path,crs):
    '''
    Import a csv file with WKT geometry column into a GeoDataFrame

    Last modified: 12/09/2020. By: Nikola

    '''

    df = pd.read_csv(path)
    df.geometry = df.geometry.apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, 
                                geometry=df.geometry,
                                crs=crs)
    return(gdf)


def multipoly_to_largest_poly(mutlipoly):
    '''
    Turn a multipolygon into the largest largest available polygon.

    Last modified: 26/01/2021. By: Nikola

    '''
    largest_poly_index = np.argmax([poly.area for poly in mutlipoly])
    largest_poly = mutlipoly[largest_poly_index]

    return largest_poly 

def GDF_multipoly_to_largest_poly(gdf):
    '''
    Turn a multipolygon into the largest largest available polygon.

    Last modified: 27/01/2021. By: Nikola

    '''

    geom_list = [None] * len(gdf)

    for index,row in gdf.iterrows():

        if type(row.geometry) == MultiPolygon:
            geom_list[index] = multipoly_to_largest_poly(row.geometry)

        else:
            geom_list[index] = row.geometry
    
    return geom_list


def combined_multipoly_to_poly(gdf,
							buffer_size):
	'''
	'''
	index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

	if len(index_multi)>0:

		print('Initial multipolygons: {}'.format(len(index_multi)))

		print('Trying to remove multipolygons with a small buffer...')

		gdf.geometry = gdf.geometry.buffer(buffer_size)

		index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

		print('Remaining multipolygons: {}'.format(len(index_multi)))

		if len(index_multi)>0:

			print('Removing remaining multipolygons by keeping the largest polygon...')

			gdf.geometry = GDF_multipoly_to_largest_poly(gdf)

			index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

			print('Remaining multipolygons: {}'.format(len(index_multi)))

			return gdf

		else:

			return gdf

	else:

		print('No multipolygons.')

		return gdf




