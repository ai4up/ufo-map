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
from Utils.momepy_functions import momepy_Perimeter, momepy_LongestAxisLength, momepy_Elongation, momepy_Convexeity, momepy_Orientation, momepy_Corners



def features_block_level(df, bloc_features=True):
    """
    Returns a DataFrame with blocks of adjacent buildings and related features.

    Features can be enabled or disabled.

    Non-Feature:
    -----------
    - TouchesIndexes: List of the indexes of the buildings in block.

    Features:
    ---------
    - BlockLength
    - AvBlockFootprintArea
    - StBlockFootprintArea
    - BlockTotalFootprintArea
    - BlockPerimeter
    - BlockLongestAxisLength
    - BlockElongation
    - BlockConvexity
    - BlockOrientation
    - BlockCorners

    """
    # Create empty result DataFrame
    df_results = pd.DataFrame()

    # Create a spatial index
    df_spatial_index = df.sindex

    # Create empty list
    TouchesIndexes = []


    ## RETRIEVE BLOCKS
    print('Retrieve blocks')

    for index, row in df.iterrows():

        # Case 1: the block has already been done
        already_in = [TouchesIndex for TouchesIndex in TouchesIndexes if index in TouchesIndex]

        if already_in != []:

            TouchesIndexes.append(already_in[0])

        else:

            # check if detached building
            possible_touches_index = list(df_spatial_index.intersection(row.geometry.bounds))
            possible_touches = df.iloc[possible_touches_index]
            precise_touches = possible_touches[possible_touches.intersects(row.geometry)]

            # Case 2: it is a detached building
            if len(precise_touches)==1:
                TouchesIndexes.append([index])

            # Case 3: the block is yet to be done
            else:

                current_index = index

                # lists output
                # buildings that have already been visited
                visited = []
                # directions that need to be explored (direction = index of a touching building)
                dir_to_explore = []

                # initiliaze stop
                it_is_over = False

                while it_is_over != True:

                    # update index
                    current_building = df.loc[current_index]

                    # touch all buildings around current building
                    possible_touches_index = list(df_spatial_index.intersection(current_building.geometry.bounds))
                    possible_touches = df.iloc[possible_touches_index]
                    precise_touches = possible_touches[possible_touches.intersects(current_building.geometry)]

                    # add current building to the list of buildings already visited
                    visited.append(current_building.name)

                    # retrieve indices of buildings touching the current building
                    touches_index = precise_touches.index.to_list()

                    # retrieve the touching buildings that have been previously visited
                    outs_visited = [touch_index for touch_index in touches_index if touch_index in visited]

                    # retrieve the touching buildings that are already listed as direction to explore
                    outs_explore = [touch_index for touch_index in touches_index if touch_index in dir_to_explore]

                    # remove previously visited buildings from the index list
                    for out in range(len(outs_visited)):
                        touches_index.remove(outs_visited[out])

                    # remove already listed next buildings from the index list
                    for out in range(len(outs_explore)):
                        touches_index.remove(outs_explore[out])


                    # decide what is next
                    if len(touches_index) == 0:
                        try:
                            # update from last in memory
                            current_index = dir_to_explore[-1]
                            #
                            dir_to_explore = dir_to_explore[:-1]

                        except:
                            # there are no more building in the block
                            it_is_over = True

                    elif len(touches_index) == 1:
                        # update
                        current_index = touches_index[0]

                    else:
                        # update
                        current_index = touches_index[0]
                        # add to memory remaining building
                        dir_to_explore += touches_index[1:]

                TouchesIndexes.append(visited)


    df_results['TouchesIndexes'] = TouchesIndexes

    ## COMPUTE METRICS

    if bloc_features:

        BlockLength = [None] * len(df)
        AvBlockFootprintArea = [None] * len(df)
        StBlockFootprintArea = [None] * len(df)
        SingleBlockPoly = [None] * len(df)
        BlockTotalFootprintArea = [None] * len(df)

        ## Invidual buildings within block
        print('Manipulate blocks')

        for index, row in df_results.iterrows():

            # If detached house
            if row['TouchesIndexes'] == [index]:

                # Append house values:
                BlockLength[index] = 1
                AvBlockFootprintArea[index] = df.geometry[index].area
                StBlockFootprintArea[index] = 0
                SingleBlockPoly[index] = df.geometry[index]
                BlockTotalFootprintArea[index] = df.geometry[index].area

            else:

                ## block length
                BlockLength[index] = len(row['TouchesIndexes'])

                # retrieve block
                block = df[df.index.isin(row['TouchesIndexes'])]

                ## Compute distribution individual buildings
                AvBlockFootprintArea[index] = block.geometry.area.mean()
                StBlockFootprintArea[index] = block.geometry.area.std()

                # merge block into one polygon
                SingleBlockPoly[index] = cascaded_union(block.geometry)

                # Compute total area
                BlockTotalFootprintArea[index] = cascaded_union(block.geometry).area

        df_results['BlockLength'] = BlockLength

        print('Features distribution buildings within block...')

        df_results['AvBlockFootprintArea'] = AvBlockFootprintArea
        df_results['StdBlockFootprintArea'] = StBlockFootprintArea

        ## Whole Block

        print('Features for the whole block...')

        df_results['BlockTotalFootprintArea'] = BlockTotalFootprintArea

        # Momepy expects a GeoDataFrame
        SingleBlockPoly = gpd.GeoDataFrame(geometry=SingleBlockPoly)

        # Compute Momepy building-level features for the whole block
        df_results['BlockPerimeter'] = momepy_Perimeter(SingleBlockPoly).series
        df_results['BlockLongestAxisLength'] = momepy_LongestAxisLength(SingleBlockPoly).series
        df_results['BlockElongation'] = momepy_Elongation(SingleBlockPoly).series
        df_results['BlockConvexity'] = momepy_Convexeity(SingleBlockPoly).series
        df_results['BlockOrientation'] = momepy_Orientation(SingleBlockPoly).series
        try:
            df_results['BlockCorners'] = momepy_Corners(SingleBlockPoly).series
        except:
            "meh"

    df_results = df_results.fillna(0)

    return df_results


def features_buildings_distance_based(
        df,
        buffer_sizes=None,
        subset_mode = False,
        subset = None,
        block_based=True,
        osm_mode = False
    ):
    """
    Returns a DataFrame with features about the buildings and blocks surrounding each building
    within given distances (circular buffers).

    Block-based features can be disabled.

    As this function is computationally expensive, it should be run on small datasets. One can
    use the subset_mode to compute only part of the dataset.

    Building-based features:
    ----------------------
    - buildings_within_buffer
    - total_ft_area_within_buffer
    - av_footprint_area_within_buffer
    - std_footprint_area_within_buffer
    - av_elongation_within_buffer
    - std_elongation_within_buffer
    - av_convexity_within_buffer
    - std_convexity_within_buffer
    - av_orientation_within_buffer
    - std_orientation_within_buffer

    Block-based features:
    -------------------
    - blocks_within_buffer
    - av_block_length_within_buffer
    - std_block_length_within_buffer
    - av_block_footprint_area_within_buffer
    - std_block_footprint_area_within_buffer
    - av_block_av_footprint_area_within_buffer
    - av_block_orientation_within_buffer
    - std_block_orientation_within_buffer
    """

   # Create df with only buildings in the buffer
    df_without_buffer = df[df['buffer']==False]

    # If OSM, also remove buildings with no heights
    if osm_mode:

            df_without_buffer = df_without_buffer[df_without_buffer['has_height']==True]

   # Create a spatial index
    df_spatial_index = df.sindex

    # make sure to start with the largest buffer
    buffer_sizes.sort(reverse=True)

    if subset_mode:

        end = subset

    else:
        end = len(df_without_buffer)


    ## CREATE LISTS/DFs TO STORE RESULTS

    # Create empty result DataFrame
    df_results = pd.DataFrame()

    # List the names of all features
    features_dict = {}

    feature_list = ['buildings_within_buffer','total_ft_area_within_buffer',
    'av_footprint_area_within_buffer','std_footprint_area_within_buffer',
    'av_elongation_within_buffer','std_elongation_within_buffer',
    'av_convexity_within_buffer','std_convexity_within_buffer',
    'av_orientation_within_buffer','std_orientation_within_buffer']

    if block_based:

        feature_block_list = ['blocks_within_buffer',
        'av_block_length_within_buffer', 'std_block_length_within_buffer',
        'av_block_footprint_area_within_buffer', 'std_block_footprint_area_within_buffer',
        'av_block_av_footprint_area_within_buffer',
        'av_block_orientation_within_buffer', 'std_block_orientation_within_buffer']

        feature_list = feature_list + feature_block_list


    ## Create a dictionary to store all the features
    # dict = {buf_size_1: {'ft_1': list, 'ft_2'...}, buf_size_2: {'ft_1': list, 'ft_2'...},..}
    for buf_size in buffer_sizes:

        # first level: buffer size
        features_dict[buf_size] = {}

        # second level: feature name
        for feature in feature_list:

            features_dict[buf_size][feature] = [None] * len(df_without_buffer)


    ## RETRIEVE BUILDINGS IN BUFFER

    for index, row in df_without_buffer.loc[0:end].iterrows():

        # Start with largest buffer size !!
        for buf_index, buf_size in enumerate(buffer_sizes):

            # draw x-meter *circular* buffers (use centroid for circular, real geom for orginal shape)
            buffer = row.geometry.centroid.buffer(buf_size)

            if buf_index == 0:

                # Intersection spatial index and bounding box of the building i
                possible_matches_index = list(df_spatial_index.intersection(buffer.bounds))

                # Retrieve possible matches
                possible_matches = df.loc[possible_matches_index]

            # Identify precise matches that intersect
            precise_matches = possible_matches[possible_matches.intersects(buffer)]


            ## COUNT
            # Remove building i from count
            features_dict[buf_size]['buildings_within_buffer'][index] = len(precise_matches)-1


            ## GEOMETRY-BASED FEATURES

            # if there are no other buildings in the buffer
            if len(precise_matches) < 2:

                features_dict[buf_size]['av_footprint_area_within_buffer'][index] = 0
                features_dict[buf_size]['std_footprint_area_within_buffer'][index] = 0
                features_dict[buf_size]['av_elongation_within_buffer'][index] = 0
                features_dict[buf_size]['std_elongation_within_buffer'][index] = 0
                features_dict[buf_size]['av_convexity_within_buffer'][index] = 0
                features_dict[buf_size]['std_convexity_within_buffer'][index] = 0
                features_dict[buf_size]['av_orientation_within_buffer'][index] = 0
                features_dict[buf_size]['std_orientation_within_buffer'][index] = 0
                features_dict[buf_size]['total_ft_area_within_buffer'][index] = 0
                ft_area_around_index = 0


            else:

                # remove the building i
                try:
                    precise_matches = precise_matches.drop(index)

                    ## Average footprint area
                    features_dict[buf_size]['av_footprint_area_within_buffer'][index] = precise_matches.geometry.area.mean()

                    ## Standard deviation footprint area
                    features_dict[buf_size]['std_footprint_area_within_buffer'][index] = precise_matches.geometry.area.std()

                    ## Average and standard deviation of elongation of buildings within buffer
                    elongation = momepy_Elongation(precise_matches).series
                    features_dict[buf_size]['av_elongation_within_buffer'][index] = elongation.mean()
                    features_dict[buf_size]['std_elongation_within_buffer'][index] = elongation.std()

                    ## Average and standard deviation of convexity of buildings within buffer
                    convexity = momepy_Convexeity(precise_matches).series
                    features_dict[buf_size]['av_convexity_within_buffer'][index] = convexity.mean()
                    features_dict[buf_size]['std_convexity_within_buffer'][index] = convexity.std()

                    ## Average and standard deviation of orientation of buildings within buffer
                    orientation = momepy_Orientation(precise_matches).series
                    features_dict[buf_size]['av_orientation_within_buffer'][index] = orientation.mean()
                    features_dict[buf_size]['std_orientation_within_buffer'][index] = orientation.std()


                except:
                    # if the building does not fall in a buffer around it's centroid
                    print('Building {} must be a castle or something.'.format(index))

                    features_dict[buf_size]['av_footprint_area_within_buffer'][index] = 0
                    features_dict[buf_size]['std_footprint_area_within_buffer'][index] = 0
                    features_dict[buf_size]['av_elongation_within_buffer'][index] = 0
                    features_dict[buf_size]['std_elongation_within_buffer'][index] = 0
                    features_dict[buf_size]['av_convexity_within_buffer'][index] = 0
                    features_dict[buf_size]['std_convexity_within_buffer'][index] = 0
                    features_dict[buf_size]['av_orientation_within_buffer'][index] = 0
                    features_dict[buf_size]['std_orientation_within_buffer'][index] = 0

                ## Total footprint area within buffer
                # Initialize counter for building i
                ft_area_around_index = []

                # Remove the building i
                for j in precise_matches.index:

                    # the building is fully within in the buffer
                    if precise_matches.geometry[j].within(buffer):

                        # Add the total area
                        ft_area_around_index.append(precise_matches.geometry[j].area)

                    else:

                        # Add only area within the buffer
                        ft_area_around_index.append(precise_matches.geometry[j].intersection(buffer).area)

                # Store
                features_dict[buf_size]['total_ft_area_within_buffer'][index] = sum(ft_area_around_index)


                ## BLOCK-BASED FEATURES

                if block_based:

                    ## Blocks in buffer

                    # list of blocks
                    block_indices_list_around_index = []

                    # list of individual features
                    block_length_around_index = []
                    block_footprint_area_around_index = []
                    block_av_footprint_area_around_index = []
                    block_orientation_around_index = []

                    # iterate through the matches to retrieve the block info
                    for precise_matche_index in precise_matches.index:

                        # if the block (list of indices) is not already in the list of block within buffer
                        if df.loc[precise_matche_index]['TouchesIndexes'] not in block_indices_list_around_index:

                            # if the list is longer than 1 (this is a block)
                            if len(df.loc[precise_matche_index]['TouchesIndexes']) > 1:

                                # Append the info from the blocks
                                # list
                                block_indices_list_around_index.append(df.loc[precise_matche_index]['TouchesIndexes'])

                                # list of individual features
                                block_length_around_index.append(df.loc[precise_matche_index]['BlockLength'])
                                block_footprint_area_around_index.append(df.loc[precise_matche_index]['BlockTotalFootprintArea'])
                                block_av_footprint_area_around_index.append(df.loc[precise_matche_index]['AvBlockFootprintArea'])
                                block_orientation_around_index.append(df.loc[precise_matche_index]['BlockOrientation'])


                    # if no blocks found, store 0s
                    if len(block_indices_list_around_index) == 0:

                        features_dict[buf_size]['blocks_within_buffer'][index] = 0
                        features_dict[buf_size]['av_block_length_within_buffer'][index] = 0
                        features_dict[buf_size]['std_block_length_within_buffer'][index] = 0
                        features_dict[buf_size]['av_block_footprint_area_within_buffer'][index] = 0
                        features_dict[buf_size]['std_block_footprint_area_within_buffer'][index] = 0
                        features_dict[buf_size]['av_block_av_footprint_area_within_buffer'][index] = 0
                        features_dict[buf_size]['av_block_orientation_within_buffer'][index] = 0
                        features_dict[buf_size]['std_block_orientation_within_buffer'][index] = 0


                    # else compute statistics
                    else:

                        ## Number of blocks within buffer
                        features_dict[buf_size]['blocks_within_buffer'][index] = len(block_indices_list_around_index)

                        ## Average block length within buffer
                        features_dict[buf_size]['av_block_length_within_buffer'][index] = pd.Series(block_length_around_index).mean()

                        ## Standard deviation block length within buffer
                        features_dict[buf_size]['std_block_length_within_buffer'][index] = pd.Series(block_length_around_index).std()

                        ## Average block total footprint area within buffer
                        features_dict[buf_size]['av_block_footprint_area_within_buffer'][index] = pd.Series(block_footprint_area_around_index).mean()

                        ## Standard deviation block total footprint area within buffer
                        features_dict[buf_size]['std_block_footprint_area_within_buffer'][index] = pd.Series(block_footprint_area_around_index).std()

                        ## Average average building footprint in blocks within buffer
                        features_dict[buf_size]['av_block_av_footprint_area_within_buffer'][index] = pd.Series(block_av_footprint_area_around_index).mean()

                        ## Average block orientation within buffer
                        features_dict[buf_size]['av_block_orientation_within_buffer'][index] = pd.Series(block_orientation_around_index).mean()

                        ## Standard deviation block orientation within buffer
                        features_dict[buf_size]['std_block_orientation_within_buffer'][index] = pd.Series(block_orientation_around_index).std()


    for buf_size in buffer_sizes:

        for feature in feature_list:

            df_results.insert(loc=0, column='{}_{}'.format(feature,buf_size), value=features_dict[buf_size][feature])

    df_results = df_results.fillna(0)

    return df_results


def get_column_names(buffer_size, block_based):
    """
    Returns the properly named list of columns for
    `features_building_distance_based_v2`, given the buffer size.
    """

    count_cols = [
        f'buildings_within_buffer_{buffer_size}',
        f'total_ft_area_within_buffer_{buffer_size}']
    avg_cols = [
        f'av_footprint_area_within_buffer_{buffer_size}',
        f'av_elongation_within_buffer_{buffer_size}',
        f'av_convexity_within_buffer_{buffer_size}',
        f'av_orientation_within_buffer_{buffer_size}']
    std_cols = [
        f'std_footprint_area_within_buffer_{buffer_size}',
        f'std_elongation_within_buffer_{buffer_size}',
        f'std_convexity_within_buffer_{buffer_size}',
        f'std_orientation_within_buffer_{buffer_size}']
    cols = count_cols + avg_cols + std_cols
    block_cols = []

    if block_based:
        block_count_cols = [
            f'blocks_within_buffer_{buffer_size}']
        block_avg_cols = [
            f'av_block_length_within_buffer_{buffer_size}',
            f'av_block_footprint_area_within_buffer_{buffer_size}',
            f'av_block_av_footprint_area_within_buffer_{buffer_size}',
            f'av_block_orientation_within_buffer_{buffer_size}']
        block_std_cols = [
            f'std_block_length_within_buffer_{buffer_size}',
            f'std_block_footprint_area_within_buffer_{buffer_size}',
            f'std_block_av_footprint_area_within_buffer_{buffer_size}',
            f'std_block_orientation_within_buffer_{buffer_size}']
        block_cols = block_count_cols + block_avg_cols + block_std_cols

    return cols, block_cols


def features_buildings_distance_based_v2(original_df, buffer_sizes=None, block_based=True):
    """
    Returns a DataFrame with features about the buildings and blocks surrounding each building
    within given distances (circular buffers).

    Block-based features can be disabled.

    As this function is computationally expensive, it should be run on small datasets. One can
    use the subset_mode to compute only part of the dataset.

    This function is a performance enhancement of the previous function

    Building-based features:
    ----------------------
    - buildings_within_buffer
    - total_ft_area_within_buffer
    - av_footprint_area_within_buffer
    - std_footprint_area_within_buffer
    - av_elongation_within_buffer
    - std_elongation_within_buffer
    - av_convexity_within_buffer
    - std_convexity_within_buffer
    - av_orientation_within_buffer
    - std_orientation_within_buffer

    Block-based features:
    -------------------
    - blocks_within_buffer
    - av_block_length_within_buffer
    - std_block_length_within_buffer
    - av_block_footprint_area_within_buffer
    - std_block_footprint_area_within_buffer
    - av_block_av_footprint_area_within_buffer
    - std_block_av_footprint_area_within_buffer
    - av_block_orientation_within_buffer
    - std_block_orientation_within_buffer
    """

    df = original_df.reset_index(drop=True)
    df['BlockId'] = df.groupby(df['TouchesIndexes'].astype(str).map(hash), sort=False).ngroup()

    # save as numpy arrays for fast access and fast vectorized aggregations
    buildings_ft_values = np.vstack((
        df.FootprintArea.values,
        df.Elongation.values,
        df.Convexity.values,
        df.Orientation.values,
    ))

    if block_based:
        blocks_df = df.drop_duplicates(subset=['BlockId']).set_index('BlockId').sort_index()
        is_in_block = (df['BlockLength'] > 1)

        blocks_ft_values = np.vstack((
            blocks_df.BlockLength,
            blocks_df.BlockTotalFootprintArea,
            blocks_df.AvBlockFootprintArea,
            blocks_df.BlockOrientation
        ))

    result_list = []

    for buffer_size in buffer_size:

        # For each buffer obtain the intersected buildings
        buffers = df.geometry.centroid.buffer(buffer_size).values
        buffers_gdf = gpd.GeoDataFrame(geometry=buffers)

        joined_gdf = gpd.sjoin(buffers_gdf, df, how="left", op="intersects")
        joined_gdf = joined_gdf[joined_gdf.index != joined_gdf.index_right]

        # Prepare the correct arrays for fast update of values (faster than pd.Series)
        cols, block_cols = get_column_names(buffer_size, block_based)
        values = np.zeros((len(df), len(cols)))
        block_values = np.zeros((len(df), len(block_cols)))

        # For each building, compute its building group of aggregations
        for idx, group in joined_gdf.groupby(joined_gdf.index):

            # Get the indexes corresponding to the buildings within the buffer
            indexes = group.index_right.values

            total_area = 0
            for j in indexes:
                geom = df.loc[j].geometry
                total_area += geom.area if geom.within(buffers[idx]) else geom.intersection(buffers[idx]).area

            # Compute building features. Be careful with the order of the columns
            within_buffer = len(indexes)
            avg_features = buildings_ft_values[:, indexes].mean(axis=1).tolist()
            std_features = buildings_ft_values[:, indexes].std(axis=1, ddof=1).tolist()
            values[idx] = [within_buffer, total_area] + avg_features + std_features

            if not block_based:
                continue

            # Get indexes corresponding to the blocks within the buffer, only once
            #block_indexes = df.loc[indexes].drop_duplicates(subset=['BlockId']).index.values
            subset = df[df.index.isin(indexes) & is_in_block]
            if len(subset) == 0:
                continue

            block_indexes = np.unique(subset['BlockId'])

            # Compute block features.
            within_buffer = len(block_indexes)
            avg_features = blocks_ft_values[:, block_indexes].mean(axis=1).tolist()
            std_features = blocks_ft_values[:, block_indexes].std(axis=1, ddof=1).tolist()
            block_values[idx] = [within_buffer] + avg_features + std_features

        tmp_df = pd.DataFrame(np.hstack((values, block_values)), columns=cols + block_cols, index=df.index).fillna(0)
        result_list.append(tmp_df)

    full_df = pd.concat(result_list, axis=1)

    return full_df.set_index(original_df.index)