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


def features_city_level(
        geom_boundary,
        df_buildings_w_building_features,
        df_intersections,
        df_streets,
        df_urban_atlas,
        df_streets_based_block,
        osm_mode=False
    ):
    """
    Returns a DataFrame with features at the city level.

    Important - the building df must contain already features for blocks, as they are needed in the computation

    Features boundaries:
    ------------------
    - area_city
    - phi_city

    Features buildings:
    ------------------
    - total_buildings_city
    - av_building_footprint_city
    - std_building_footprint_city
    - num_detached_buildings
    - block_2_to_5
    - block_6_to_10
    - block_11_to_20
    - block_20+

    Features intersections:
    ----------------------
    - total_intersection_city

    Features streets:
    ----------------
    - total_length_street_city
    - av_length_street_city

    Features blocks:
    ---------------
    - total_number_block_city
    - av_area_block_city
    - std_area_block_city

    Features Urban Atlas:
    --------------------
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
    df_without_buffer = df_buildings_w_building_features[df_buildings_w_building_features['buffer']==False]

    # If OSM, also remove buildings with no heights
    if osm_mode == True:

            df_without_buffer = df_without_buffer[df_without_buffer['has_height']==True]

    # Create empty result DataFrame
    df_results = pd.DataFrame()


    ### Features boundaries ###

    ## Area city
    area_city = geom_boundary.area
    df_results['area_city'] = [area_city] * len(df_without_buffer)

    ## Phi city

    if type(geom_boundary) == MultiPolygon:

        geom_boundary = max(geom_boundary, key=lambda a: a.area)

    # Draw exterior ring of the building
    exterior = geom_boundary.exterior

    # Compute max distance to a point
    max_dist = geom_boundary.centroid.hausdorff_distance(exterior)

    # Draw smallest circle around building
    min_circle = geom_boundary.centroid.buffer(max_dist)

    # Area of the circle
    circle_area = min_circle.area

    # Compute phi
    phi_city = geom_boundary.area/circle_area

    df_results['phi_city'] = [phi_city] * len(df_without_buffer)


    ### Features buildings ###

    ## total_buildings_city
    total_buildings_city = len(df_without_buffer)
    df_results['total_buildings_city'] = [total_buildings_city] * len(df_without_buffer)

    ## av_building_footprint_city
    av_building_footprint_city = df_without_buffer.geometry.area.mean()
    df_results['av_building_footprint_city'] = [av_building_footprint_city] * len(df_without_buffer)

    ## std_building_footprint_city
    std_building_footprint_city = df_without_buffer.geometry.area.std()
    df_results['std_building_footprint_city'] = [std_building_footprint_city] * len(df_without_buffer)

    ## blocks
    single_blocks = df_without_buffer.drop_duplicates(subset = 'TouchesIndexes')
    counts = dict(Counter(single_blocks.BlockLength))

    new_counts = {'1':0,'2-5':0,'6-10':0,'11-20':0,'20+':0}
    for key in counts.keys():
        if key == 1:
            new_counts['1'] += counts[key]
        if key in range(2,5):
            new_counts['2-5'] += counts[key]
        if key in range(6,10):
            new_counts['6-10'] += counts[key]
        if key in range(11,20):
            new_counts['11-20'] += counts[key]
        if key > 20:
            new_counts['20+'] += counts[key]

    df_results['num_detached_buildings'] = new_counts['1']
    df_results['block_2_to_5'] = new_counts['2-5']
    df_results['block_6_to_10'] = new_counts['6-10']
    df_results['block_11_to_20'] = new_counts['11-20']
    df_results['block_20+'] = new_counts['20+']


    ### Features intersections ###

    #total_intersection_city
    total_intersection_city = len(df_intersections)
    df_results['total_intersection_city'] = [total_intersection_city] * len(df_without_buffer)


    ### Features streets ###

    # total_length_street_city
    total_length_street_city = df_streets.geometry.length.sum()
    df_results['total_length_street_city'] = [total_length_street_city] * len(df_without_buffer)

    # av_length_street_city
    av_length_street_city = df_streets.geometry.length.mean()
    df_results['av_length_street_city'] = [av_length_street_city] * len(df_without_buffer)

    ### Features street-based blocks ###

    # total_number_block_city
    total_number_block_city = len(df_streets_based_block)
    df_results['total_number_block_city'] = [total_number_block_city] * len(df_without_buffer)

    # av_area_block_city
    av_area_block_city = df_streets_based_block.geometry.area.mean()
    df_results['av_area_block_city'] = [av_area_block_city] * len(df_without_buffer)

    # std_area_block_city
    std_area_block_city = df_streets_based_block.geometry.area.std()
    df_results['std_area_block_city'] = [std_area_block_city] * len(df_without_buffer)


    ### Features urban atlas ###

    # lu_agricultural_within_buffer
    lu_agricultural_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Agricultural'].geometry.area.sum()
    df_results['lu_agricultural_within_buffer'] = [lu_agricultural_within_buffer] * len(df_without_buffer)

    # lu_industrial_commercial_within_buffer
    lu_industrial_commercial_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Industrial, commercial area'].geometry.area.sum()
    df_results['lu_industrial_commercial_within_buffer'] = [lu_industrial_commercial_within_buffer] * len(df_without_buffer)

    # lu_natural_semi_natural_within_buffer
    lu_natural_semi_natural_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Natural and semi-natural'].geometry.area.sum()
    df_results['lu_natural_semi_natural_within_buffer'] = [lu_natural_semi_natural_within_buffer] * len(df_without_buffer)

    # lu_railways_within_buffer
    lu_railways_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Railways'].geometry.area.sum()
    df_results['lu_railways_within_buffer'] = [lu_railways_within_buffer] * len(df_without_buffer)

    # lu_roads_within_buffer
    lu_roads_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Roads'].geometry.area.sum()
    df_results['lu_roads_within_buffer'] = [lu_roads_within_buffer] * len(df_without_buffer)

    # lu_urban_fabric_within_buffer
    lu_urban_fabric_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Urban fabric'].geometry.area.sum()
    df_results['lu_urban_fabric_within_buffer'] = [lu_urban_fabric_within_buffer] * len(df_without_buffer)

    # lu_urban_green_within_buffer
    lu_urban_green_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Urban green'].geometry.area.sum()
    df_results['lu_urban_green_within_buffer'] = [lu_urban_green_within_buffer] * len(df_without_buffer)

    # lu_wastelands_within_buffer
    lu_wastelands_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Wastelands and co'].geometry.area.sum()
    df_results['lu_wastelands_within_buffer'] = [lu_wastelands_within_buffer] * len(df_without_buffer)

    # lu_water_within_buffer
    lu_water_within_buffer = df_urban_atlas[df_urban_atlas['ft_typology'] == 'Water'].geometry.area.sum()
    df_results['lu_water_within_buffer'] = [lu_water_within_buffer] * len(df_without_buffer)

    return(df_results)





