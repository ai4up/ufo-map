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

    Last update: 01.29.21 By: Felix W.

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



def get_column_names(buffer_size,
                     num_bld=True,
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
        - buffer size
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - cols: the properly named list of columns for
    `features_building_distance_based`, given the buffer size and
    features passed through this function. 

    Last update: 2/3/21. By Nikola.

    """

    #Prepare the properly named list of columns, given the buffer size.
    count_cols = []
    if num_bld:
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
                             av_or_std = None,
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




def features_buildings_distance_based(original_df, 
                                     buffer_sizes=None,
                                     num_bld=True,
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

    Args:
        - df: dataframe with previously computed features at the building level
        - buffers sizes: a list of buffer sizes to use, in meters
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - full_df: a DataFrame of shape (n_features*buffer_size, len_df) with the 
          computed features

    Last update: 2/3/21. By Nikola.
    
    """
    
    df = original_df.reset_index(drop=True)
    
    # get previously computed features at the building level for average features
    buildings_ft_values_av = get_buildings_ft_values(av_or_std='av',
                                 av_bld_area=av_bld_area,
                                 av_elongation=av_elongation,
                                 av_convexity=av_convexity,
                                 av_orientation=av_orientation)
    
    # get previously computed features at the building level for std features
    buildings_ft_values_std = get_buildings_ft_values(av_or_std='std',
                                 std_bld_area=std_bld_area,
                                 std_elongation=std_elongation,
                                 std_convexity=std_convexity,
                                 std_orientation=std_orientation)
    result_list = []

    for buffer_size in buffer_sizes:

        # Get buffer into gdf
        buffer = df.geometry.centroid.buffer(buffer_size).values
        buffer_gdf = gpd.GeoDataFrame(geometry=buffer)

        # Retrieve buildings intersecting buffer
        joined_gdf = gpd.sjoin(buffer_gdf, df, how="left", op="intersects")
        
        # ???
        joined_gdf = joined_gdf[joined_gdf.index != joined_gdf.index_right]

        # Prepare the correct arrays for fast update of values (faster than pd.Series)
        cols = get_column_names(buffer_size,                     
                                 num_bld=num_bld,
                                 total_bld_area=total_bld_area,
                                 av_bld_area=av_bld_area,
                                 std_bld_area=std_bld_area, 
                                 av_elongation=av_elongation,
                                 std_elongation=std_elongation,
                                 av_convexity=av_convexity,
                                 std_convexity=std_convexity,
                                 av_orientation=av_orientation,
                                 std_orientation=std_orientation)
        
        values = np.zeros((len(df), len(cols)))

        # For each building, compute its building group of aggregations
        for idx, group in joined_gdf.groupby(joined_gdf.index):

            # Get the indexes corresponding to the buildings within the buffer
            indexes = group.index_right.values

            if num_bld or av_bld_area or std_bld_area:
                # Compute area covered by buildings
                total_area = 0
                for j in indexes:
                    geom = df.loc[j].geometry
                    total_area += geom.area if geom.within(buffer[idx]) else geom.intersection(buffer[idx]).area

            # Compute the other building features. Be careful with the order of the columns
            if num_bld:
                within_buffer = len(indexes)
                
            if av_bld_area or av_elongation or av_convexity or av_orientation:
                
                avg_features = buildings_ft_values_av[:, indexes].mean(axis=1).tolist()
                
            if std_bld_area or std_elongation or std_convexity or std_orientation:
                
                std_features = buildings_ft_values_std[:, indexes].std(axis=1, ddof=1).tolist()
            
            # Assemble for a row
            row_values = []
            
            if num_bld:
                row_values.append(within_buffer)
                
            if total_bld_area:
                row_values.append(total_area)
            
            if av_bld_area or av_elongation or av_convexity or av_orientation:   
                row_values += avg_features
                
            if std_bld_area or std_elongation or std_convexity or std_orientation:
                row_values += std_features
            
            values[idx] = row_values

        # Assemble for a buffer size
        tmp_df = pd.DataFrame(values, columns=cols, index=df.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df.set_index(original_df.index)
