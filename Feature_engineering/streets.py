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


def features_streets(
        df_buildings,
        df_streets,
        df_intersections,
        buffer_sizes,
        subset_mode=False,
        subset=None,
        osm_mode=False
    ):
    """
    Returns a DataFrame with features about the streets and intersections surrounding
    each building within given distances (circular buffers).

    Features closest intersection:
    ----------------------------
    - distance_to_closest_intersection

    Features closest street:
    --------------
    - distance_to_closest_road
    - street_length_closest_road
    - street_width_av_closest_road
    - street_width_std_closest_road
    - street_openness_closest_road
    - (street_linearity_closest_road)

    - street_closeness_global_closest_road
    - street_betweeness_global_closest_road
    - street_betweeness_500_closest_road

    Features intersections buffer:
    ----------------------
    - intersection_count_within_buffer

    Features streets buffer:
    -----------------------
    - street_length_total_within_buffer
    - street_length_av_within_buffer
    - street_length_std_within_buffer
    - street_length_total_inter_buffer

    - (street_orientation_std_inter_buffer)
    - (street_linearity_av_inter_buffer)
    - (street_linearity_std_inter_buffer)
    - street_width_av_inter_buffer
    - street_width_std_inter_buffer

    - street_betweeness_global_max_inter_buffer
    - street_betweeness_global_av_inter_buffer
    - street_betweeness_500_max_inter_buffer
    - street_betweeness_500_av_inter_buffer
    """

    # Create empty result DataFrame
    df_results = pd.DataFrame()

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

    # create spatial indexes
    str_spatial_index = df_streets.sindex
    int_spatial_index = df_intersections.sindex

    ## CREATE DICT TO STORE RESULTS

    features_dict_closest = {}

    features_dict_buffer = {}

    list_closest = ['distance_to_closest_intersection','distance_to_closest_road','street_length_closest_road',
        'street_width_av_closest_road','street_width_std_closest_road','street_openness_closest_road',
        'street_closeness_global_closest_road','street_betweeness_global_closest_road','street_closeness_500_closest_road']

    list_within_buffer = ['intersection_count_within_buffer','street_length_total_within_buffer','street_length_av_within_buffer',
        'street_length_std_within_buffer','street_length_total_inter_buffer','street_width_av_inter_buffer',
        'street_width_std_inter_buffer','street_betweeness_global_max_inter_buffer','street_betweeness_global_av_inter_buffer',
        'street_closeness_500_max_inter_buffer','street_closeness_500_av_inter_buffer']

    ## Create a dictionary to store all the closest-object features
    for feature in list_closest:
        features_dict_closest[feature] = [None] * len(df_without_buffer)
        #features_dict_closest[feature] = pd.Series([None] * len(df_without_buffer), index=df_without_buffer.index)

    ## Create a dictionary to store all the within-buffer features
    # dict = {buf_size_1: {'ft_1': list, 'ft_2'...}, buf_size_2: {'ft_1': list, 'ft_2'...},..}
    for buf_size in buffer_sizes:

        # first level: buffer size
        features_dict_buffer[buf_size] = {}

        # second level: feature name
        for feature in list_within_buffer:
            features_dict_buffer[buf_size][feature] = [None] * len(df_without_buffer)

    ################
    ### FEATURES ###
    ################

    #for index, row in df_without_buffer.loc[0:end].iterrows():
    subset_df = df_without_buffer.iloc[0:end]
    for index, geom in zip(subset_df.index, subset_df.geometry):

        #### CLOSEST OBJECTS #####
        ### CLOSEST INTERSECTION

        # empty list of matches indexes
        possible_matches_index = []

        # start with small buffer
        buffer_size = 100
        buffered_geom = geom.centroid.buffer(buffer_size)

        # retrieve matched index
        possible_matches_index = list(int_spatial_index.intersection(buffered_geom.bounds))
        possible_matches = df_intersections.loc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(buffered_geom)]

        # until one index gets retrieved
        while len(precise_matches) == 0:

            buffer_size += 100
            buffered_geom = geom.centroid.buffer(buffer_size)

            # retrieve indexes
            possible_matches_index = list(int_spatial_index.intersection(buffered_geom.bounds))
            possible_matches = df_intersections.loc[possible_matches_index]
            precise_matches = possible_matches[possible_matches.intersects(buffered_geom)]

        # retrieve rows and sort by distance to get the closest
        precise_matches['distance'] = precise_matches['geometry'].distance(geom)
        precise_matches = precise_matches.sort_values(by=['distance'])
        closest_int = precise_matches.iloc[0]

        ## retrieve features
        features_dict_closest['distance_to_closest_intersection'][index] = closest_int.distance

        ### CLOSEST STREET
        ## retrieve closest street to the building
        ## we use the same buffer_size and buffer geom as found for intersections

         # retrieve matched index
        possible_matches_index = list(str_spatial_index.intersection(buffered_geom.bounds))
        possible_matches = df_streets.loc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(buffered_geom)]

        # until one index gets retrieved
        while len(precise_matches) == 0:

            buffer_size += 100
            buffered_geom = geom.centroid.buffer(buffer_size)

            # retrieve indexes
            possible_matches_index = list(str_spatial_index.intersection(buffered_geom.bounds))
            possible_matches = df_streets.loc[possible_matches_index]
            precise_matches = possible_matches[possible_matches.intersects(buffered_geom)]

        # retrieve rows and sort by disrtance to get the closest
        precise_matches['distance'] = precise_matches['geometry'].distance(geom)
        precise_matches = precise_matches.sort_values(by=['distance'])
        closest_str = precise_matches.iloc[0]

        ## retrieve features
        features_dict_closest['distance_to_closest_road'][index] = closest_str.distance
        features_dict_closest['street_length_closest_road'][index] = closest_str.length
        features_dict_closest['street_width_av_closest_road'][index] = closest_str.width
        features_dict_closest['street_width_std_closest_road'][index] = closest_str.width_deviation
        features_dict_closest['street_openness_closest_road'][index] = closest_str.openness
        features_dict_closest['street_betweeness_global_closest_road'][index] = closest_str.betweenness_metric_e
        features_dict_closest['street_closeness_global_closest_road'][index] = closest_str.closeness_global
        features_dict_closest['street_closeness_500_closest_road'][index] = closest_str.closeness500

        #### WITHIN-BUFFER FEATURES ####

        ## RETURN OBJECTS WITHIN BUFFERS

        # Start with largest buffer size
        for buffer_index, buffer_size in enumerate(buffer_sizes):

            # draw x-meter *circular* buffers (use centroid for circular, real geom for orginal shape)
            buffered_geom = geom.centroid.buffer(buffer_size)

            if buffer_index == 0:

                ## Possible intersections

                # Intersection spatial index and bounding box of the building i
                possible_matches_index = list(int_spatial_index.intersection(buffered_geom.bounds))
                possible_matches_int = df_intersections.loc[possible_matches_index]

                ## Possible streets

                # Intersection spatial index and bounding box of the building i
                possible_matches_index = list(str_spatial_index.intersection(buffered_geom.bounds))
                possible_matches_str = df_streets.loc[possible_matches_index]

            ## Identify precise matches that intersect
            precise_matches_int = possible_matches_int[possible_matches_int.intersects(buffered_geom)]

            precise_matches_str_inter = possible_matches_str[possible_matches_str.intersects(buffered_geom)]
            precise_matches_str_within = possible_matches_str[possible_matches_str.within(buffered_geom)]

            ## Compute features
            features_dict_buffer[buffer_size]['intersection_count_within_buffer'][index] = len(precise_matches_int)

            features_dict_buffer[buffer_size]['street_length_total_within_buffer'][index] = precise_matches_str_within.length.sum()
            features_dict_buffer[buffer_size]['street_length_av_within_buffer'][index] = precise_matches_str_within.length.mean()
            features_dict_buffer[buffer_size]['street_length_std_within_buffer'][index] = precise_matches_str_within.length.std()

            features_dict_buffer[buffer_size]['street_length_total_inter_buffer'][index] = precise_matches_str_inter.length.sum()

            features_dict_buffer[buffer_size]['street_width_av_inter_buffer'][index] = precise_matches_str_inter.width.mean()
            features_dict_buffer[buffer_size]['street_width_std_inter_buffer'][index] = precise_matches_str_inter.width.std()

            features_dict_buffer[buffer_size]['street_betweeness_global_max_inter_buffer'][index] = precise_matches_str_inter.betweenness_metric_e.max()
            features_dict_buffer[buffer_size]['street_betweeness_global_av_inter_buffer'][index] = precise_matches_str_inter.betweenness_metric_e.mean()
            features_dict_buffer[buffer_size]['street_closeness_500_max_inter_buffer'][index] = precise_matches_str_inter.closeness500.max()
            features_dict_buffer[buffer_size]['street_closeness_500_av_inter_buffer'][index] = precise_matches_str_inter.closeness500.mean()

    # store within-buffer features in df
    for buffer_size in buffer_sizes:
            for feature in list_within_buffer:
                df_results.insert(loc=0, column='{}_{}'.format(feature, buffer_size), value=features_dict_buffer[buffer_size][feature])

    # store closest features in df
    for feature in list_closest:
                df_results.insert(loc=0, column='{}'.format(feature), value=features_dict_closest[feature])

    df_results = df_results.fillna(0)

    return df_results


def features_streets_based_block(
        df_buildings,
        df_streets_based_block,
        buffer_sizes=None,
        subset_mode=False,
        subset=None,
        osm_mode=False
    ):
    """
    Returns a DataFrame with features about the street-based block where the building
    falls and the blocks intersecting buffers.

    Feature own block:
    ----------------
    - street_based_block_area
    - street_based_block_phi
    - street_based_block_corners

    Features intersection with buffer:
    ---------------------
    - street_based_block_number_inter_buffer
    - street_based_block_av_area_inter_buffer
    - street_based_block_std_area_inter_buffer
    - street_based_block_av_phi_inter_buffer
    - street_based_block_std_phi_inter_buffer
    - street_based_block_std_orientation_inter_buffer
    """

    # Create empty result DataFrame
    df_results = pd.DataFrame()

   # Create df with only buildings in the buffer
    df_without_buffer = df_buildings[df_buildings['buffer']==False]

    # If OSM, also remove buildings with no heights
    if osm_mode == True:

            df_without_buffer = df_without_buffer[df_without_buffer['has_height']==True]

    # make sure to start with the largest buffer
    buffer_sizes.sort(reverse=True)

    # subset mode
    if subset_mode == True:

        end = subset

    else:
        end = len(df_without_buffer)

    # create spatial indexes
    block_spatial_index = df_streets_based_block.sindex

    ## CREATE DICT TO STORE RESULTS

    dict_own_block = {}

    dict_inter_buffer = {}

    list_own_block = ['street_based_block_area','street_based_block_phi','street_based_block_corners']

    list_inter_buffer = ['street_based_block_number_inter_buffer','street_based_block_av_area_inter_buffer','street_based_block_std_area_inter_buffer',
    'street_based_block_av_phi_inter_buffer','street_based_block_std_phi_inter_buffer','street_based_block_std_orientation_inter_buffer']


    ## Create a dictionary to store all the closest-object features
    for feature in list_own_block:

        dict_own_block[feature] = [None] * len(df_without_buffer)

    ## Create a dictionary to store all the within-buffer features
    # dict = {buf_size_1: {'ft_1': list, 'ft_2'...}, buf_size_2: {'ft_1': list, 'ft_2'...},..}
    for buf_size in buffer_sizes:

        # first level: buffer size
        dict_inter_buffer[buf_size] = {}

        # second level: feature name
        for feature in list_inter_buffer:

            dict_inter_buffer[buf_size][feature] = [None] * len(df_without_buffer)

    ################
    ### FEATURES ###
    ################

    for index,row in df_without_buffer.loc[0:end].iterrows():

    ## OWN BLOCK

        try:

            possible_matches_index = list(block_spatial_index.intersection(row.geometry.bounds))
            possible_matches = df_streets_based_block.loc[possible_matches_index]
            precise_match = possible_matches[possible_matches.contains(row.geometry)]

            if len(precise_match)>1:

                print('Multiple blockkks!')

            else:
                dict_own_block['street_based_block_area'][index] = precise_match.iloc[0].area
                dict_own_block['street_based_block_phi'][index] = precise_match.iloc[0].Phi
                dict_own_block['street_based_block_corners'][index] = precise_match.iloc[0].Corners

        except:
            print('Building {} does not fall within an existing block.'.format(index))

            dict_own_block['street_based_block_area'][index] = 0
            dict_own_block['street_based_block_phi'][index] = 0
            dict_own_block['street_based_block_corners'][index] = 0

    ## FEATURES WITHIN BUFFER

        # Start with largest buffer size
        for buf_index, buf_size in enumerate(buffer_sizes):

            # draw x-meter *circular* buffers (use centroid for circular, real geom for orginal shape)
            buffer = row.geometry.centroid.buffer(buf_size)

            if buf_index == 0:

                # Intersection spatial index and bounding box of the building i
                possible_matches_index = list(block_spatial_index.intersection(buffer.bounds))
                # Retrieve possible matches
                possible_matches = df_streets_based_block.loc[possible_matches_index]

            ## Identify precise matches that intersect
            precise_matches = possible_matches[possible_matches.intersects(buffer)]

            ## Compute features
            dict_inter_buffer[buf_size]['street_based_block_number_inter_buffer'][index] = len(precise_matches)
            dict_inter_buffer[buf_size]['street_based_block_av_area_inter_buffer'][index] = precise_matches.area.mean()
            dict_inter_buffer[buf_size]['street_based_block_std_area_inter_buffer'][index] = precise_matches.area.std()
            dict_inter_buffer[buf_size]['street_based_block_av_phi_inter_buffer'][index] = precise_matches.Phi.mean()
            dict_inter_buffer[buf_size]['street_based_block_std_phi_inter_buffer'][index] = precise_matches.Phi.std()
            dict_inter_buffer[buf_size]['street_based_block_std_orientation_inter_buffer'][index] = precise_matches.streets_based_block_orientation.std()


    # store within-buffer features in df
    for buf_size in buffer_sizes:

            for feature in list_inter_buffer:

                df_results.insert(loc=0, column='{}_{}'.format(feature,buf_size), value=dict_inter_buffer[buf_size][feature])

    # store closest features in df
    for feature in list_own_block:

                df_results.insert(loc=0, column='{}'.format(feature), value=dict_own_block[feature])

    df_results = df_results.fillna(0)


    return(df_results)