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
                           
                                        

def features_blocks_distance_based(original_df, 
                                buffer_sizes=None,
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
        - df: dataframe with previously computed features at the building level
        - buffers_sizes: a list of buffer sizes to use, in meters e.g. [50,100,200]
        - booleans for all parameters: True -> computed, False: passed

    Returns:
        - full_df: a DataFrame of shape (n_features*buffer_size, len_df) with the 
          computed features

    Last update: 2/5/21. By Nikola.
    
    """

    df = original_df.reset_index(drop=True)
    
    # create block ids, by grouping similar groups of touched indexes
    df['BlockId'] = df.groupby(df['TouchesIndexes'].astype(str).map(hash), sort=False).ngroup()
    
    # create list of booleans whether building is in a block of not
    is_in_block = (df['BlockLength'] > 1)

    # get previously computed features at the building level for average features
    blocks_ft_values_av = get_block_ft_values(df,
                                 av_or_std='av',
                                 av_block_len=av_block_len,
                                 av_block_ft_area=av_block_ft_area,
                                 av_block_av_ft_area=av_block_av_ft_area,
                                 av_block_orient=av_block_orient)
    
    # get previously computed features at the building level for std features
    blocks_ft_values_std = get_block_ft_values(df,
                                 av_or_std='std',
                                 std_block_len=std_block_len,
                                 std_block_ft_area=std_block_ft_area,
                                 std_block_av_ft_area=std_block_av_ft_area,
                                 std_block_orient=std_block_orient)  
    

    result_list = []

    for buffer_size in buffer_sizes:
        
        print(buffer_size)

        # Create a gdf with a buffer per building as a single geometry column
        buffer = df.geometry.centroid.buffer(buffer_size).values
        buffer_gdf = gpd.GeoDataFrame(geometry=buffer)

        # Join each buffer with the buildings that intersect it, as a gdf
        # where each row is a pair buffer (index) and building (index_right)
        # there are multiple rows for one index
        joined_gdf = gpd.sjoin(buffer_gdf, df, how="left", op="intersects")
        
        # Remove rows of the building of interest for each buffer
        joined_gdf = joined_gdf[joined_gdf.index != joined_gdf.index_right]

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
        
        block_values = np.zeros((len(df), len(block_cols)))

        # For each buffer/building of interest (index), group all buffer-buildings pairs
        for idx, group in joined_gdf.groupby(joined_gdf.index):
            
            # Get the indexes corresponding to the buildings within the buffer
            indexes_bldgs_in_buff = group.index_right.values

            # Fetch buildings from main df that in the buffer (indexes_bldgs_in_buff)
            # and that are within blocks (from is_in_block boolean list)
            blocks_in_buff = df[df.index.isin(indexes_bldgs_in_buff) & is_in_block]
            
            # if no block, go to next row
            if len(blocks_in_buff) == 0:
                continue
            
            # Get indexes of one building per block (it has all the info about block already)
            block_indexes = np.unique(blocks_in_buff['BlockId'])
            
            # Compute block features
            if n_blocks:
                within_buffer = len(block_indexes)
                
            if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:
                avg_features = blocks_ft_values_av[:, block_indexes].mean(axis=1).tolist()
                
            if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:       
                std_features = blocks_ft_values_std[:, block_indexes].std(axis=1, ddof=1).tolist()
            
            # Assemble per row
            row_values = []
            
            if n_blocks:
                row_values.append(within_buffer)
            
            if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:
                row_values += avg_features
                
            if av_block_len or av_block_ft_area or av_block_av_ft_area or av_block_orient:  
                row_values += std_features
            
            block_values[idx] = row_values

        # Assemble per buffer size    
        tmp_df = pd.DataFrame(block_values, columns=block_cols, index=df.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df.set_index(original_df.index)