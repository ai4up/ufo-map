""" Module that calculates building level features. 

This module includes all functions to calculate building level features.
At the moment it contains the following functions:

- features_building_level

Created on Tue Mar 24 15:37:57 2020
@author: miln

Last update on Fri Jan 29 15:33:57 2020
@author: fewa
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.ops import cascaded_union
import math
import random
from collections import Counter
from ufo_map.Utils.momepy_functions import momepy_LongestAxisLength, momepy_Elongation, momepy_Convexeity, momepy_Orientation, momepy_Corners


def features_building_level(
        df,
        FootprintArea=True,
        Perimeter=True,
        Phi=True,
        LongestAxisLength=True,
        Elongation=True,
        Convexity=True,
        Orientation=True,
        Corners=True,
        Touches=True
    ):
    """Returns a DataFrame with building-level features.

    Calculates building features. Extensively uses Momepy: http://docs.momepy.org/en/stable/api.html
    All features computed by default.
   
    Args:
        df: dataframe with input building data (osm_id, height, geometry (given as POLYGONS - Multipolygons
            cause an error when calculating Phi and should therefore be converted beforehand))
        FootprintArea: True, if footprintarea of building should be calculated
        Perimeter: True, if Perimeter of building should be calculated
        Phi: True, if Phi of building should be calculated
        LongestAxisLength: True, if longest axis length of building should be calculated
        Elongation: True, if elongation of building should be calculated
        Convexity: True, if convexity of building should be calculated
        Orientation: True, if orientation of building should be calculated
        Corners: True, if corners of building should be calculated
        TouchesCount: True, if touches of building with other buildings should be counted

    Returns:
        df_results: a dataframe containing the input datafrme 'df' as well as an additional
                    column for each calculated building feature
    """

    # Create empty result DataFrame
    df_results = pd.DataFrame(index=df.index)


    if FootprintArea:

        print('FootprintArea...')

        df_results['FootprintArea'] = df.geometry.area


    if Perimeter:

        print('Perimeter...')

        df_results['Perimeter'] = df.geometry.length


    if Phi:

        print('Phi...')

        # Compute max distance to a point and create the circle from the geometry centroid
        max_dist = df.geometry.map(lambda g: g.centroid.hausdorff_distance(g.exterior))

        circle_area = df.geometry.centroid.buffer(max_dist).area

        df_results['Phi'] = df.geometry.area / circle_area


    if LongestAxisLength:

        print('LongestAxisLength...')

        df_results['LongestAxisLength'] = momepy_LongestAxisLength(df).series


    if Elongation:

        print('Elongation...')

        df_results['Elongation'] = momepy_Elongation(df).series


    if Convexity:

        print('Convexity...')

        df_results['Convexity'] = momepy_Convexeity(df).series


    if Orientation:

        print('Orientation...')

        df_results['Orientation'] = momepy_Orientation(df).series


    if Corners:

        print('Corners...')

        df_results['Corners'] = momepy_Corners(df).series


    if Touches:

        print('CountTouches and SharedWallLength')

        gdf_exterior = gpd.GeoDataFrame(geometry=df.geometry.exterior)

        # Spatial join
        joined_gdf = gpd.sjoin(gdf_exterior, df, how="left")
        joined_gdf = joined_gdf[joined_gdf.index != joined_gdf.index_right]

        def get_inter_length(row):
            return row.geometry.intersection(df.loc[row.index_right].geometry).length

        # Compute adjacent shared perimeter and count
        joined_gdf['shared_length'] = joined_gdf.apply(get_inter_length, axis=1)
        total_shared = joined_gdf.groupby(joined_gdf.index)['shared_length'].sum()
        total_count = joined_gdf.groupby(joined_gdf.index)['shared_length'].count()

        df_results['CountTouches'] = 0
        df_results['SharedWallLength'] = 0
        df_results.loc[total_count.index, 'CountTouches'] = total_count
        df_results.loc[total_shared.index, 'SharedWallLength'] = total_shared

    return df_results