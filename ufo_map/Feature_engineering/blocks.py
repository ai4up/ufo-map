""" Block features module

This module includes all functions to calculate block features.

At the moment it contains the following main functions:

- features_block_level
- features_block_distance_based

and the following helping functions:

- get_block_column_names
- get_block_ft_values

@authors: Nikola, Felix W

"""
# Imports
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely.ops import cascaded_union
# import psutil

from ufo_map.Utils.momepy_functions import momepy_Perimeter, momepy_Convexeity, momepy_Corners, \
                                           momepy_Elongation, momepy_LongestAxisLength, momepy_Orientation

from ufo_map.Utils.helpers_ft_eng import get_indexes_right_bbox,get_indexes_right_round_buffer



def get_building_indexes_in_block(index,df,df_spatial_index):
    '''
    Returns the indexes of buildings in a block.
    '''
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

        return(visited)


def features_block_level(df, bloc_features=True):
    """
    Returns a DataFrame with blocks of adjacent buildings and related features.
    Features can be enabled or disabled. 
    
    Calculates the following:
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
 
    Args:
        - df: dataframe with previously computed features at the building level
        - boolean to set feature calculation: True -> computed, False: passed

    Returns:
        - full_df: a DataFrame of shape (n_features*buffer_size, len_df) with the 
          computed features

    Last update: 2/12/21. By Felix.

    TODO: add option not compute some features.

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

        already_in = [TouchesIndex for TouchesIndex in TouchesIndexes if index in TouchesIndex]

        # Case 1: the block has already been done
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
                TouchesIndexes.append(get_building_indexes_in_block(index,df,df_spatial_index))

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
            print("meh")

    df_results = df_results.fillna(0)

    return df_results


def get_block_column_names(buffer_size,
                        n_blocks=True,
                        av_block_len=True,
                        std_block_len=True,
                        av_block_ft_area=True,
                        std_block_ft_area=True,
                        av_block_av_ft_area=True,
                        std_block_av_ft_area=True,
                        av_block_orient=True,
                        std_block_orient=True
                          ):
    """Returns a list of columns for features to be computed.

    Used in `features_blocks_distance_based`.

    Args: 
        - buffer_size: a buffer size to use, in meters, passed in the other function e.g. 500
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - cols: the properly named list of columns for
    `features_blocks_distance_based`, given the buffer size and
    features passed through this function. 

    Last update: 2/5/21. By Nikola.

    """
    block_cols = []

    block_count_cols = []
    if n_blocks:
        block_count_cols.append(f'blocks_within_buffer_{buffer_size}')
                           
    block_avg_cols = []
    if av_block_len:
        block_avg_cols.append(f'av_block_length_within_buffer_{buffer_size}')
    if av_block_ft_area:
        block_avg_cols.append(f'av_block_footprint_area_within_buffer_{buffer_size}')    
    if av_block_av_ft_area:
        block_avg_cols.append(f'av_block_av_footprint_area_within_buffer_{buffer_size}')          
    if av_block_orient:
        block_avg_cols.append(f'av_block_orientation_within_buffer_{buffer_size}')         
        
    block_std_cols = []
    if std_block_len:
        block_std_cols.append(f'std_block_length_within_buffer_{buffer_size}')      
    if std_block_ft_area:
        block_std_cols.append(f'std_block_footprint_area_within_buffer_{buffer_size}')  
    if std_block_av_ft_area:
        block_std_cols.append(f'std_block_av_footprint_area_within_buffer_{buffer_size}')               
    if std_block_orient:
        block_std_cols.append(f'std_block_orientation_within_buffer_{buffer_size}')               
            
    
    block_cols = block_count_cols + block_avg_cols + block_std_cols

    return block_cols

                           
                           
def get_block_ft_values(df,
                        av_or_std = None,
                        n_blocks=False,
                        av_block_len=False,
                        std_block_len=False,
                        av_block_ft_area=False,
                        std_block_ft_area=False,
                        av_block_av_ft_area=False,
                        std_block_av_ft_area=False,
                        av_block_orient=False,
                        std_block_orient=False
                            ):
    '''Returns the values of relevant block features previously computed, one
    per block, as a numpy array for fast access and fast vectorized aggregation.

    Used in `features_blocks_distance_based`.

    Args: 
        - df: dataframe with previously computed features at the building level
        - av_or_std: chose if getting features for compute averages ('av') 
          or standard deviations ('std')
        - booleans for all parameters: True -> computed, False: passed     
          These args set to false so that only av or std fts can be activated 
          with half of the args.

    Returns:
        - blocks_ft_values: a numpy array of shape
         (n_features, len(df.drop_duplicates((subset=['BlockId']))).

    Last update: 2/5/21. By Nikola.

    '''
    
    # create a df of unique blocks
    blocks_df = df.drop_duplicates(subset=['BlockId']).set_index('BlockId').sort_index()
    
    # choose features to fetch from df depending on options activated
    fts_to_fetch = []
    
    if av_or_std == 'av':
        if  av_block_len:
            fts_to_fetch.append('BlockLength')
        if av_block_ft_area:
            fts_to_fetch.append('BlockTotalFootprintArea')
        if av_block_av_ft_area:
            fts_to_fetch.append('AvBlockFootprintArea')
        if av_block_orient:
            fts_to_fetch.append('BlockOrientation')
    
    if av_or_std == 'std':
        if std_block_len:
            fts_to_fetch.append('BlockLength')
        if std_block_ft_area:
            fts_to_fetch.append('BlockTotalFootprintArea')
        if std_block_av_ft_area:
            fts_to_fetch.append('AvBlockFootprintArea')
        if std_block_orient:
            fts_to_fetch.append('BlockOrientation')
    
    # fetch them
    df_fts = blocks_df[fts_to_fetch]

    # save as numpy arrays
    # initialize from first column
    blocks_ft_values = np.array(df_fts.iloc[:,0].values)
    # add the others
    for ft in df_fts.columns.values[1:]:
        blocks_ft_values = np.vstack((blocks_ft_values,df_fts[ft].values))
        
    return blocks_ft_values
                           
                                        

def features_blocks_distance_based(gdf, 
                                building_gdf,
                                buffer_sizes=None,
                                buffer_type = 'bbox',
                                n_blocks=True,
                                av_block_len=True,
                                std_block_len=True,
                                av_block_ft_area=True,
                                std_block_ft_area=True,
                                av_block_av_ft_area=True,
                                std_block_av_ft_area=True,
                                av_block_orient=True,
                                std_block_orient=True
                                    ):
    """
    Returns a DataFrame with features about the blocks surrounding each geometry
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

    Last update: 2/5/21. By Nikola.
    
    """

    gdf = gdf.reset_index(drop=True)
    building_gdf = building_gdf.reset_index(drop=True)

    # create block ids, by grouping similar groups of touched indexes
    building_gdf['BlockId'] = building_gdf.groupby(building_gdf['TouchesIndexes'].astype(str).map(hash), sort=False).ngroup()
    
    # create list of booleans whether building is in a block of not
    is_in_block = (building_gdf['BlockLength'] > 1)

    # get previously computed features at the building level for average features
    blocks_ft_values_av = get_block_ft_values(building_gdf,
                                 av_or_std='av',
                                 av_block_len=av_block_len,
                                 av_block_ft_area=av_block_ft_area,
                                 av_block_av_ft_area=av_block_av_ft_area,
                                 av_block_orient=av_block_orient)
    
    # get previously computed features at the building level for std features
    blocks_ft_values_std = get_block_ft_values(building_gdf,
                                 av_or_std='std',
                                 std_block_len=std_block_len,
                                 std_block_ft_area=std_block_ft_area,
                                 std_block_av_ft_area=std_block_av_ft_area,
                                 std_block_orient=std_block_orient)  
    

    result_list = []

    for buffer_size in buffer_sizes:
        
        print(buffer_size)

        geometries = list(gdf.geometry)
        geometries_gdf_inter = list(building_gdf.geometry)
        gdf_inter_sindex = building_gdf.sindex

        # get the indexes of buildings within buffers
        if buffer_type == 'bbox':

            indexes_right,bbox_geom = get_indexes_right_bbox(geometries,gdf_inter_sindex,buffer_size)

        else:
            buffer,joined_gdf = get_indexes_right_round_buffer(gdf,building_gdf,buffer_size)



        # Prepare the correct arrays for fast update of values (faster than pd.Series)
        block_cols = get_block_column_names(buffer_size,
                                n_blocks=n_blocks,
                                av_block_len=av_block_len,
                                std_block_len=std_block_len,
                                av_block_ft_area=av_block_ft_area,
                                std_block_ft_area=std_block_ft_area,
                                av_block_av_ft_area=av_block_av_ft_area,
                                std_block_av_ft_area=std_block_av_ft_area,
                                av_block_orient=av_block_orient,
                                std_block_orient=std_block_orient)
        
        block_values = np.zeros((len(gdf), len(block_cols)))

        # For each buffer/building of interest (index), group all buffer-buildings pairs
        if buffer_type == 'bbox': groups = enumerate(indexes_right)
        else: groups = joined_gdf.groupby(joined_gdf.index)

        # for each building <> buildings within a buffer around it
        for idx, group in groups:

            # Get the building indexes (index_right) corresponding to the buildings within the buffer
            if buffer_type == 'round': group = group.index_right.values

            # For points that have buildings in buffer assign values, for points that don't assign 0s
            if not np.isnan(group).any():      
                # Fetch buildings from main df that in the buffer (indexes_bldgs_in_buff)
                # and that are within blocks (from is_in_block boolean list)
                index_bldg_in_buff_and_block = is_in_block.loc[group] 
                index_bldg_in_buff_and_block = index_bldg_in_buff_and_block[index_bldg_in_buff_and_block==True]
                blocks_in_buff = building_gdf.loc[index_bldg_in_buff_and_block.index]

                # if no block, go to next row
                if len(blocks_in_buff) == 0:
                    continue
                
                # Get indexes of one building per block (it has all the info about block already)
                block_indexes = np.unique(blocks_in_buff['BlockId'])

                # Assemble per row
                row_values = []
                
                # Compute block features
                if n_blocks:
                    row_values.append(len(block_indexes)) 
                    
                if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:
                    row_values += blocks_ft_values_av[:, block_indexes].mean(axis=1).tolist()
                    
                if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:       
                    row_values += blocks_ft_values_std[:, block_indexes].std(axis=1, ddof=1).tolist()
            
            else:
                len_array= sum([n_blocks,av_block_len,std_block_len,av_block_ft_area,std_block_ft_area,\
                    av_block_av_ft_area,std_block_av_ft_area,av_block_orient,std_block_orient])
                row_values = [0]*len_array

            block_values[idx] = row_values

        # Assemble per buffer size    
        tmp_df = pd.DataFrame(block_values, columns=block_cols, index=gdf.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df