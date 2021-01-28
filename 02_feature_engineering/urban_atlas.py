"""
Created on Tue Mar 24 15:37:57 2020

@author: miln
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.ops import cascaded_union
import math
import random
from collections import Counter


def features_urban_atlas(
        df_buildings,
        df_urban_atlas,
        buffer_sizes=None,
        subset_mode=False,
        subset=None,
        osm_mode=False
    ):
    """
    Returns a DataFrame with features about the land use classes surrounding
    each building within given distances (circular buffers).

    Feature land use building:
    ------------------------
    - building_in_lu_agricultural
    - building_in_lu_industrial_commercial
    - building_in_lu_natural_semi_natural
    - building_in_lu_railways
    - building_in_lu_urban_fabric
    - building_in_lu_urban_green
    - building_in_lu_wastelands

    Feature land use area within buffer:
    ---------------------------------
    - lu_agricultural_within_buffer
    - lu_industrial_commercial_within_buffer
    - lu_natural_semi_natural_within_buffer
    - lu_railways_within_buffer
    - lu_roads_within_buffer
    - lu_urban_fabric_within_buffer
    - lu_urban_green_within_buffer
    - lu_wastelands_within_buffer
    - lu_water_within_buffer
    """

   # Create df with only buildings in the buffer
    df_without_buffer = df_buildings[df_buildings['buffer']==False]

    # If OSM, also remove buildings with no heights
    if osm_mode:

            df_without_buffer = df_without_buffer[df_without_buffer['has_height']==True]

    # make sure to start with the largest buffer
    buffer_sizes.sort(reverse=True)

    # subset mode
    if subset_mode:
        end = subset
    else:
        end = len(df_without_buffer)

    # create spatial index for the land use classes
    ua_spatial_index = df_urban_atlas.sindex

    # Create empty result DataFrame
    df_results = pd.DataFrame()


    ## CREATE DICT TO STORE RESULTS

    # building_in ft dict
    building_in_fts = {'building_in_lu_agricultural': [None] * len(df_without_buffer),
    'building_in_lu_industrial_commercial': [None] * len(df_without_buffer),
    'building_in_lu_natural_semi_natural': [None] * len(df_without_buffer),
    'building_in_lu_railways': [None] * len(df_without_buffer),
    'building_in_lu_urban_fabric': [None] * len(df_without_buffer),
    'building_in_lu_urban_green': [None] * len(df_without_buffer),
    'building_in_lu_wastelands': [None] * len(df_without_buffer)}

    # mapping ft to lu class for one-hot encoding (building in)
    dict_ua_to_ft = {'building_in_lu_agricultural': 'Agricultural',
             'building_in_lu_industrial_commercial': 'Industrial, commercial area',
             'building_in_lu_natural_semi_natural': 'Natural and semi-natural',
             'building_in_lu_railways': 'Railways',
             'building_in_lu_urban_fabric': 'Urban fabric',
             'building_in_lu_urban_green': 'Urban green',
             'building_in_lu_wastelands': 'Wastelands and co'
             }

    # mapping lu class to ft (within buffer)
    lu_classes_mapping = {'Agricultural': 'lu_agricultural_within_buffer',
        'Industrial, commercial area':'lu_industrial_commercial_within_buffer',
        'Natural and semi-natural':'lu_natural_semi_natural_within_buffer',
        'Railways':'lu_railways_within_buffer',
        'Roads':'lu_roads_within_buffer',
        'Urban fabric':'lu_urban_fabric_within_buffer',
        'Urban green':'lu_urban_green_within_buffer',
        'Wastelands and co':'lu_wastelands_within_buffer',
        'Water':'lu_water_within_buffer'
        }

    # list fts (within buffer)
    lu_within_buffer_fts_list = ['lu_agricultural_within_buffer',
        'lu_industrial_commercial_within_buffer',
        'lu_natural_semi_natural_within_buffer',
        'lu_railways_within_buffer',
        'lu_roads_within_buffer',
        'lu_urban_fabric_within_buffer',
        'lu_urban_green_within_buffer',
        'lu_wastelands_within_buffer',
        'lu_water_within_buffer']


    # lu_within buffer ft dict
    lu_within_buffer_fts = {}

    # create levels
    for buf_size in buffer_sizes:

        # first level: buffer size
        lu_within_buffer_fts[buf_size] = {}

        # second level: feature name
        for feature in lu_within_buffer_fts_list:

            lu_within_buffer_fts[buf_size][feature] = [None] * len(df_without_buffer)


    ## RETRIEVE LAND USE OF BUILDING

    print('Retrieve within which land use the building is located...')

    for index, row in df_without_buffer.loc[0:end].iterrows():

        # retrieve intersection building lu polygons
        possible_matches_index = list(ua_spatial_index.intersection(row.geometry.bounds))
        possible_matches = df_urban_atlas.loc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(row.geometry)]

        # compute intersection area between building and polygons
        precise_matches.loc[:, 'intersection'] = precise_matches.geometry.intersection(row.geometry).area

        # retrieve the largest intersection
        precise_matches = precise_matches.loc[precise_matches['intersection'].idxmax()]

        # one-hot encoding
        for ft in dict_ua_to_ft.keys():

            # if the the building is within a given class give 1
            if precise_matches['ft_typology'] == dict_ua_to_ft[ft]:
                building_in_fts[ft][index] = 1

            # and give 0 to all the others
            else:

                building_in_fts[ft][index] = 0


    ## RETRIEVE LAND USES IN BUFFER

    print('Retrieve land uses in buffer...')

    for index, row in df_without_buffer.loc[0:end].iterrows():

        # Start with largest buffer size !!
        for buf_index, buf_size in enumerate(buffer_sizes):

            ## retrieve lu polygons that intersect the buffer

            # draw x-meter *circular* buffers (use centroid for circular, real geom for orginal shape)
            buffer = row.geometry.centroid.buffer(buf_size)

            if buf_index == 0:

                # Intersection spatial index and bounding box of the building i
                possible_matches_index = list(ua_spatial_index.intersection(buffer.bounds))

                # Retrieve possible matches
                possible_matches = df_urban_atlas.loc[possible_matches_index]

            # Identify precise matches that intersect
            precise_matches = possible_matches[possible_matches.intersects(buffer)]


            ## retrieve the intersection polygons
            for index2, _ in precise_matches.iterrows():

                # retrieve the polygon and write in wkt (otherwise empty polygons generate errors)
                precise_matches.loc[index2, 'intersection'] = precise_matches.loc[index2, 'geometry'].intersection(buffer).wkt

            # remove empty polygons (which have not matched)
            precise_matches = precise_matches[precise_matches['intersection'] != 'POLYGON EMPTY' ]

            # load geometries from wkt
            precise_matches.loc[:, 'intersection'] = precise_matches['intersection'].apply(wkt.loads)

            # change geometry column
            precise_matches = precise_matches.set_geometry('intersection')

            ## compute areas

            # add area to each polygon
            precise_matches['area'] = precise_matches['intersection'].area

            # sum by class in serie
            areas = precise_matches.groupby('ft_typology')['area'].sum()

            # check which classes are not in the buffer
            add_index = list(set(lu_classes_mapping.keys()).difference(areas.index))

            # these will all get 0 as value
            add = pd.Series([0] * len(add_index), index = add_index)

            # add them to serie
            areas = areas.append(add)

            ## save into lists
            for lu in lu_classes_mapping.keys():

                lu_within_buffer_fts[buf_size][lu_classes_mapping[lu]][index] = areas[lu]


    # add buffer based features
    for buf_size in buffer_sizes:

        for ft in lu_within_buffer_fts[buf_size].keys():

            df_results.insert(loc=0, column='{}_{}'.format(ft, buf_size), value=lu_within_buffer_fts[buf_size][ft])

    # add building in features
    for ft in building_in_fts.keys():

        df_results.insert(loc=0, column='{}'.format(ft), value=building_in_fts[ft])

    df_results = df_results.fillna(0)

    return df_results


def urban_atlas_name_cleaning(s):
    s = s.strip().lower()
    s = s.replace('and co', '').replace(',', '').replace(' and', '').replace('commercial area', 'commercial')
    s = s.strip().replace(' ', '_').replace('-', '_')
    return 'lu_' + s


def find_urban_atlas_for_geometry(df_buildings, df_urban_atlas):
    """
    Process intersections between Urban Atlas features and buildings or their buffer

    We can discard checking 'lu_roads' if we assume all geometries are covering all the space:
    a geometry that does not fit in the other UA geoms is in 'lu_roadsx'. We do so because
    roads are too complex shapes and it is too computationally expensive to check intersections.
    Another way to do would be to split them just as 'st_dubdivide' does it in postgresql.
    """
    ua = df_urban_atlas[df_urban_atlas.ft_typology != 'lu_roads']
    overlap_df = gpd.sjoin(df_buildings, ua, how='left', op='intersects').reset_index()

    overlap_df['intersection_area'] = overlap_df.apply(lambda row: row.geometry.intersection(ua.loc[row.index_right].geometry).area, axis=1)
    max_inter_indexes = []

    for _, group in overlap_df.groupby(overlap_df['index']):

        idx = group['intersection_area'].idxmax()
        max_inter_indexes.append(idx)

        ft_typo_total_area = group.groupby('ft_typology')['intersection_area'].sum()
        overlap_df.loc[idx, ft_typo_total_area.index] = ft_typo_total_area.values

        # As we ignore interesction with roads, we assume the non-intersected area is road
        geom_area = group.geometry.values[0].area
        total_ua_area = ft_typo_total_area.values.sum()
        overlap_df.loc[idx, 'lu_roads'] = geom_area - total_ua_area

        if geom_area - total_ua_area > group.intersection_area.max():
            overlap_df.loc[idx, 'ft_typology_area'] = 'lu_roads'

    overlap_df = overlap_df.loc[max_inter_indexes].set_index('index')
    cols = [c for c in overlap_df.columns if 'lu_' in c]
    return overlap_df[cols]


def features_urban_atlas_v2(
        df_buildings,
        df_urban_atlas,
        buffer_sizes=None
    ):
    """
    Returns a DataFrame with features about the land use classes surrounding
    each building within given distances (circular buffers).

    Feature land use building:
    ------------------------
    - building_in_lu_agricultural
    - building_in_lu_industrial_commercial
    - building_in_lu_natural_semi_natural
    - building_in_lu_railways
    - building_in_lu_urban_fabric
    - building_in_lu_urban_green
    - building_in_lu_wastelands

    Feature land use area within buffer:
    ---------------------------------
    - lu_agricultural_within_buffer
    - lu_industrial_commercial_within_buffer
    - lu_natural_semi_natural_within_buffer
    - lu_railways_within_buffer
    - lu_roads_within_buffer
    - lu_urban_fabric_within_buffer
    - lu_urban_green_within_buffer
    - lu_wastelands_within_buffer
    - lu_water_within_buffer
    """

    ua = df_urban_atlas.copy()
    ua['ft_typology'] = ua['ft_typology'].map(urban_atlas_name_cleaning)

    subset = df_buildings.copy()
    for col in ua.ft_typology.unique():
        subset[col] = 0.0

    dataframes = []

    # find UA for buildings
    print("Computing building UA topology")
    res_df = find_urban_atlas_for_geometry(subset, ua)
    res_df = res_df.rename(columns={c: 'building_in_' + c for c in res_df.columns})

    # one-hot-encoding instead of intersection area
    cmax = res_df.idxmax(axis=1)
    res_df.apply(lambda x: x.name == cmax, axis=0).astype(int)
    dataframes.append(res_df)

    # find UA for buildings buffers
    for buffer_size in buffer_sizes:
        print(f"Computing building UA topology within {buffer_size}")
        subset.geometry = subset.geometry.centroid.buffer(buffer_size)

        res_df = find_urban_atlas_for_geometry(subset, ua)
        res_df = res_df.rename(columns={c: f'{c}_{buffer_size}' for c in res_df.columns})
        dataframes.append(res_df)

    full_df = pd.concat(dataframes, axis=1)