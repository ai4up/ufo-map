def old_rm_duplicates_osm_streets(df_streets):

    """
    Removes duplicated streets like two ways streets.

    Returns a cleaned GeoDataFrame with street linestrings.

    """
    # round length value to one decimal (1 cm) 
    df_streets = df_streets.round({'length': 2})
    # remove duplicates based on osmid + length
    df_streets = df_streets.drop_duplicates(['osmid','length'],keep= 'first').reset_index(drop=True)
    # spatial index
    streets_spatial_index = df_streets.sindex
    
    #list index to remove
    index_to_remove = []

    # retrieve with spatial index buffer following the street shape (intersects)
    for index,row in df_streets.iterrows():

        buffer = row.geometry.buffer(1)

        possible_matches_index = list(streets_spatial_index.intersection(buffer.bounds))
        possible_matches = df_streets.loc[possible_matches_index] 
        precise_matches = possible_matches[possible_matches.intersects(buffer)]

        # filter by length
        precise_matches = precise_matches[precise_matches.length > 0.95 * precise_matches.loc[index].length]
        try:
            precise_matches = precise_matches[precise_matches.length < 1.05 * precise_matches.loc[index].length]
        except:
            print('index {} being weird'.format(index))
            continue

        # refine by overlap
        for index2,row2 in precise_matches.drop(index).iterrows():

            overlap = precise_matches.loc[index].geometry.intersection(precise_matches.loc[index2].geometry).length

            if 0.95 * precise_matches.loc[index].length < overlap < 1.05 * precise_matches.loc[index].length:
                
                if index2 not in index_to_remove:
                    
                    index_to_remove.append(index)

            if 0.05 * precise_matches.loc[index].length < overlap < 0.95 * precise_matches.loc[index].length or overlap > 1.05 * precise_matches.loc[index].length:

                print('Street {} has a suspect overlap of {}%.'.format(index,overlap/precise_matches.loc[index].length))

    print('Streets removed:')
    print(index_to_remove)
    df_streets = df_streets.drop(index_to_remove)
                
    return(df_streets)



def old_block_street_based(df_streets, verbose = 'low'):
    """
    Create block polygons from the street networks.

    Returns a GeoDataFrame with block polygons.

    """

    # spatial index
    streets_spatial_index = df_streets.sindex

    # empty geoseries
    good_lines = gpd.GeoSeries()

    # list bad indexes
    bad_index = {}

    # retrieve with spatial index crossing streets
    for index,row in df_streets.iterrows():
        
        possible_matches_index = list(streets_spatial_index.intersection(row.geometry.bounds))
        possible_matches = df_streets.loc[possible_matches_index] 
        precise_matches = possible_matches[possible_matches.crosses(row.geometry)]

        # if no crossing, keep the geom with its index
        if precise_matches.empty:

            # append the geometry as it is 
            good_lines = good_lines.append(gpd.GeoSeries(row.geometry, index = [index]))

        # if there are crossing
        else:
            
            # retrieve index
            bad_index[index] = len(precise_matches)

            # if there is only one crossing, no problems
            if len(precise_matches) == 1:

                # split the line at the point of the only crossing road
                line_split = split(row.geometry, precise_matches.iloc[0].geometry)

                # for all splits
                for line_num_sp, line_sp in enumerate(line_split):

                    # add to the good line geoseries, changing the index    
                    good_lines = good_lines.append(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))

            # however, if *several* crossings
            if len(precise_matches) > 1:

                if verbose == 'high':
                    print('For street {}, there were {} crossings.'.format(index,len(precise_matches)))

                # get a temporary list for the splits
                good_lines_tmp = gpd.GeoSeries()

                # for all crossing lines
                for _, row_pm in precise_matches.iterrows():

                    # if it is the first cut...
                    if good_lines_tmp.empty:
                        
                        # split the original street
                        line_split = split(row.geometry, row_pm.geometry)
                        
                        #print(line_split)
                        #print(len(line_split))

                        # for all splits
                        for line_num_sp, line_sp in enumerate(line_split):
                            
                            #print(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))
                
                            # append split to the tmp split list, changing the index
                            good_lines_tmp = good_lines_tmp.append(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))
                
                    # if it is not the first cut
                    else:

                        #print(good_lines_tmp)
                        
                        # iterate over the cuts done already *by index*
                        for index_glt, line_glt in good_lines_tmp.items(): 
                            
                            #print(index_glt)

                            # there may be not crossing
                            try:

                                # split the split
                                line_split_glt = split(line_glt, row_pm.geometry)

                                # remove the previous split from the list
                                good_lines_tmp = good_lines_tmp.drop(index_glt)

                                # for all the new smaller splits
                                for line_num_sp_2, line_sp_2 in enumerate(line_split_glt):

                                    # append split to the tmp split list, changing the index *from the previous split*
                                    good_lines_tmp = good_lines_tmp.append(gpd.GeoSeries(line_sp_2, index = [index_glt * 10 + line_num_sp_2]))
                            
                            except:
                                pass

                if verbose == 'high':
                    print(list(good_lines_tmp.index))
                # add all the splits to the main list
                good_lines = good_lines.append(good_lines_tmp)

    print('Splitted:')
    print(bad_index)

    df_blocks = gpd.GeoDataFrame(geometry=list(polygonize(good_lines.geometry)))
    
    return(df_blocks)
