""" Building features module

This module includes all functions to calculate building features.

At the moment it contains the following main functions:

- features_building_level
- features_buildings_distance_based

and the following helping functions:

- get_column_names
- get_buildings_ft_values

@authors: Nikola, Felix W

"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.ops import cascaded_union
from shapely.geometry import Polygon
import math
import random
from collections import Counter
import psutil

from ufo_map.Utils.momepy_functions import momepy_LongestAxisLength, momepy_Elongation, momepy_Convexeity, momepy_Orientation, momepy_Corners
from ufo_map.Utils.helpers_ft_eng import get_indexes_right_bbox,get_indexes_right_round_buffer


def get_column_names(buffer_size,
                     n_bld=True,
                     total_bld_area=True,
                     av_bld_area=True,
                     std_bld_area=True, 
                     av_elongation=True,
                     std_elongation=True,
                     av_convexity=True,
                     std_convexity=True,
                     av_orientation=True,
                     std_orientation=True):
    """Returns a list of columns for features to be computed.

    Used in `features_building_distance_based`.

    Args: 
        - buffer_size: a buffer size to use, in meters, passed in the other function e.g. 500
        - booleans for all parameters: True -> computed, False: passed
          These args set to false so that only av or std fts can be activated 
          with half of the args.

    Returns:
        - cols: the properly named list of columns for
    `features_building_distance_based`, given the buffer size and
    features passed through this function. 

    Last update: 2/3/21. By Nikola.

    """

    #Prepare the properly named list of columns, given the buffer size.
    count_cols = []
    if n_bld:
        count_cols.append(f'buildings_within_buffer_{buffer_size}')
    if total_bld_area:
        count_cols.append(f'total_ft_area_within_buffer_{buffer_size}')    
    
    avg_cols = []
    if av_bld_area:
        avg_cols.append(f'av_footprint_area_within_buffer_{buffer_size}')
    if av_elongation:
        avg_cols.append(f'av_elongation_within_buffer_{buffer_size}')
    if av_convexity:
        avg_cols.append(f'av_convexity_within_buffer_{buffer_size}')
    if av_orientation:
        avg_cols.append(f'av_orientation_within_buffer_{buffer_size}')

    std_cols = []
    if std_bld_area:
        std_cols.append(f'std_footprint_area_within_buffer_{buffer_size}')
    if std_elongation:
        std_cols.append(f'std_elongation_within_buffer_{buffer_size}')
    if std_convexity:
        std_cols.append(f'std_convexity_within_buffer_{buffer_size}')
    if std_orientation:
        std_cols.append(f'std_orientation_within_buffer_{buffer_size}')  
        
    cols = count_cols + avg_cols + std_cols


    return cols


def get_buildings_ft_values(df,
                             av_or_std=None,
                             av_bld_area=False,
                             std_bld_area=False, 
                             av_elongation=False,
                             std_elongation=False,
                             av_convexity=False,
                             std_convexity=False,
                             av_orientation=False,
                             std_orientation=False

                            ):
    '''Returns the values of relevant features previously computed, as a numpy
    array for fast access and fast vectorized aggregation.

    Used in `features_building_distance_based`.

    Args: 
        - df: dataframe with previously computed features at the building level
        - av_or_std: chose if getting features for compute averages ('av') 
          or standard deviations ('std')
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - buildings_ft_values: a numpy array of shape (n_features, len_df).

    Last update: 2/3/21. By Nikola.

    '''

    # choose features to fetch from df depending on options activated
    fts_to_fetch = []
    
    if av_or_std == 'av':
        if  av_bld_area:
            fts_to_fetch.append('FootprintArea')
        if av_elongation:
            fts_to_fetch.append('Elongation')
        if av_convexity:
            fts_to_fetch.append('Convexity')
        if av_orientation:
            fts_to_fetch.append('Orientation')
    
    if av_or_std == 'std':
        if std_bld_area:
            fts_to_fetch.append('FootprintArea')
        if std_elongation:
            fts_to_fetch.append('Elongation')
        if std_convexity:
            fts_to_fetch.append('Convexity')
        if std_orientation:
            fts_to_fetch.append('Orientation')
    
    # fetch them
    df_fts = df[fts_to_fetch]

    # save as numpy arrays
    # initialize from first column
    buildings_ft_values = np.array(df_fts.iloc[:,0].values)
    # add the others
    for ft in df_fts.columns.values[1:]:
        buildings_ft_values = np.vstack((buildings_ft_values,df_fts[ft].values))
        
    return buildings_ft_values




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

    Last update: 01.29.21 By: Felix W.

    TODO: check that this is running for large files on one CPU.

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

        # for every building in df turn polygon in linearring of exterior of shape and save in gdf_exterior
        gdf_exterior = gpd.GeoDataFrame(geometry=df.geometry.exterior)

        # Spatial join between gdf_extterior and df by intersecting linestrings from gdf_exterior with polygons from df
        # This will remove all rows from gdf_exterior that don't intersect polygons of df.
        # This will generate a new line for each intersection df(index) and df(index_right),
        # where we can have several df(index_right) for one df(index)
        joined_gdf = gpd.sjoin(gdf_exterior, df, how="left")
        # as gdf_exterior will intersect with df for the same building, this line removes will those buildings.
        # Afterwards, joined_gdf will only contain buildings that intersect with other buildings, so we can count them and calculate SharedWallLength.
        joined_gdf = joined_gdf[joined_gdf.index != joined_gdf.index_right]

        def get_inter_length(row):
            # returns length of intersection between building pairs in joined_gdf
            # by using geometry from df(index_right)
            return row.geometry.intersection(df.loc[row.index_right].geometry).length

        # returns length of intersection between building pairs in joined_gdf
        # by using geometry from df(index_right)
        joined_gdf['shared_length'] = joined_gdf.apply(get_inter_length, axis=1)
        # Group by index from joined_gdf (aggregate all building pairs for one building) and sum up shared length and count
        total_shared = joined_gdf.groupby(joined_gdf.index)['shared_length'].sum()
        total_count = joined_gdf.groupby(joined_gdf.index)['shared_length'].count()
        
        # Initialise final columns with 0
        df_results['CountTouches'] = 0
        df_results['SharedWallLength'] = 0
        # add counts and shared length values to the  buildings that touch other buildings by matching the index
        df_results.loc[total_count.index, 'CountTouches'] = total_count
        df_results.loc[total_shared.index, 'SharedWallLength'] = total_shared

    return df_results




def get_ranges(N, nb):
    step = N / nb
    return [range(round(step*i), round(step*(i+1))) for i in range(nb)]


def compute_building_area_in_buffer_round(idx,group,building_gdf,buffer):
    total_area = 0
    for j in group:
        geom = building_gdf.loc[j].geometry
        total_area += geom.area if geom.within(buffer[idx]) else geom.intersection(buffer[idx]).area
    return(total_area)



def compute_building_area_in_bbox(idx,group,geometries_gdf_building,indexes_right_small,bbox_geom):
    total_area = 0
    for j in group:
        geom = geometries_gdf_building[j]
        if j in indexes_right_small[idx]:
            total_area += geom.area
        else:
            total_area += geom.area if geom.within(bbox_geom[idx]) else geom.intersection(bbox_geom[idx]).area
    return(total_area)


def features_buildings_distance_based(gdf, 
                                     building_gdf,
                                     buffer_sizes=None,
                                     buffer_type = 'bbox',
                                     n_bld=True,
                                     total_bld_area=True,
                                     av_bld_area=True,
                                     std_bld_area=True, 
                                     av_elongation=True,
                                     std_elongation=True,
                                     av_convexity=True,
                                     std_convexity=True,
                                     av_orientation=True,
                                     std_orientation=True):
    """Returns a DataFrame with features about the buildings surrounding each geometry
    of interest within given distances (circular buffers). 
    
    The geometry of interest can a point or a polygon (e.g. a building).

    By default computes all features.

    Args:
        - gdf = geodataframe for which one wants to compute the features
        - building_gdf: dataframe with previously computed features at the building level
        - buffers_sizes: a list of buffer sizes to use, in meters e.g. [50,100,200]
        - buffer_type: either 'round' or squared 'bbox' 
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - full_df: a DataFrame of shape (n_features*buffer_size, len_df) with the 
          computed features

    Last update: 4/23/21. By Nikola.
    
    """
    
    # gdf = gdf.reset_index(drop=True)
    # building_gdf = building_gdf.reset_index(drop=True)
    
    # get previously computed features at the building level for average features
    buildings_ft_values_av = get_buildings_ft_values(building_gdf,
                                 av_or_std='av',
                                 av_bld_area=av_bld_area,
                                 av_elongation=av_elongation,
                                 av_convexity=av_convexity,
                                 av_orientation=av_orientation)
    
    # get previously computed features at the building level for std features
    buildings_ft_values_std = get_buildings_ft_values(building_gdf,
                                 av_or_std='std',
                                 std_bld_area=std_bld_area,
                                 std_elongation=std_elongation,
                                 std_convexity=std_convexity,
                                 std_orientation=std_orientation)
    result_list = []


    for buffer_size in buffer_sizes:

        print(buffer_size)

        geometries = list(gdf.geometry)
        geometries_gdf_inter = list(building_gdf.geometry)
        gdf_inter_sindex = building_gdf.sindex

        # get the indexes of buildings within buffers
        if buffer_type == 'bbox':

            indexes_right,indexes_right_small,bbox_geom = get_indexes_right_bbox(geometries,
                                                            gdf_inter_sindex,
                                                            buffer_size,
                                                            small_mode=True,
                                                            longuest_axes=gdf.LongestAxisLength)

        else:
            buffer,joined_gdf = get_indexes_right_round_buffer(gdf,building_gdf,buffer_size)


        # Prepare the correct arrays for fast update of values (faster than pd.Series)
        cols = get_column_names(buffer_size,                     
                                 n_bld=n_bld,
                                 total_bld_area=total_bld_area,
                                 av_bld_area=av_bld_area,
                                 std_bld_area=std_bld_area, 
                                 av_elongation=av_elongation,
                                 std_elongation=std_elongation,
                                 av_convexity=av_convexity,
                                 std_convexity=std_convexity,
                                 av_orientation=av_orientation,
                                 std_orientation=std_orientation)
        
        values = np.zeros((len(gdf), len(cols)))

        # For each buffer/building of interest (index), group all buffer-buildings pairs
        if buffer_type == 'bbox': groups = enumerate(indexes_right)
        else: groups = joined_gdf.groupby(joined_gdf.index)
        
        # for each building <> buildings within a buffer around it
        for idx, group in groups:
    

            # Get the building indexes (index_right) corresponding to the buildings within the buffer
            if buffer_type == 'round': group = group.index_right.values

            # For points that have buildings in buffer assign values, for points that don't assign 0s
            if not np.isnan(group).any():

                row_values = []

                if n_bld: row_values.append(len(group))

                if total_bld_area:

                    if buffer_type == 'bbox':
                        total_area = compute_building_area_in_bbox(idx,group,geometries_gdf_inter, \
                            indexes_right_small,bbox_geom)

                    else:
                        total_area = compute_building_area_in_buffer_round(idx,group,building_gdf,buffer)

                    row_values.append(total_area)


                if av_bld_area or av_elongation or av_convexity or av_orientation:
                    row_values += buildings_ft_values_av[:, group].mean(axis=1).tolist()
                    
                if std_bld_area or std_elongation or std_convexity or std_orientation:
                    row_values += buildings_ft_values_std[:, group].std(axis=1, ddof=1).tolist()
                
            else:
                len_array= sum([n_bld,total_bld_area,av_bld_area,std_bld_area,av_elongation,std_elongation,av_convexity,std_convexity,av_orientation,std_orientation])
                row_values = [0]*len_array  
            
            values[idx] = row_values

        # Assemble for a buffer size
        tmp_df = pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df
