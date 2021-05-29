
import geopandas as gpd
import momepy
from shapely.ops import polygonize, split


def rm_duplicates_osm_streets(streets):

    """
    Removes duplicated streets like two ways streets.

    Returns a cleaned GeoDataFrame with street linestrings.

    """
    start_len = len(streets)

    # remove streets that have the same length and osmid 
    streets = streets.round({'length': 0})
    streets = streets.drop_duplicates(['osmid','length'],keep= 'first').reset_index(drop=True)

    # get the remaining streets that are within a 1m buffer distance
    streets_spatial_index = streets.sindex
    buffer_gdf = gpd.GeoDataFrame(geometry=streets.geometry.buffer(1).values)
    joined_gdf = gpd.sjoin(buffer_gdf, streets, how="left", op="contains")
    
    # keep only one
    joined_gdf = joined_gdf.loc[joined_gdf[joined_gdf.index != joined_gdf.index_right].index]
    joined_gdf = joined_gdf.drop_duplicates(['index_right','length'],keep= 'first')
    joined_gdf = joined_gdf[~joined_gdf.index.duplicated(keep='first')]
    streets = streets.drop(joined_gdf.index).reset_index(drop=True)
    end_len = (len(streets))
    print(f'New number of street: {end_len} (removed {start_len-end_len})')
    
    return(streets)



def network_to_street_gdf(streets,buildings):
    ''' Create final street gdf (linestrings) with street duplicates removed
    and as an option street/building interaction characteristics from Momepy.

    TODO: validate!    
    '''
    
    # Averaging the two closeness from nodes to edges 
    momepy.mean_nodes(streets, 'closeness500')
    momepy.mean_nodes(streets, 'closeness_global')

    # edges to gdf
    streets = momepy.nx_to_gdf(streets, points=False)
    streets.drop(columns='mm_len')
    
    streets = rm_duplicates_osm_streets(streets)
    
    if city_buildings != None:
        street_profile = momepy_StreetProfile(streets, buildings)
        edges['width'] = street_profile.w
        edges['width_deviation'] = street_profile.wd
        edges['openness'] = street_profile.o
    
    return(streets)




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


            # if *several* crossings
            if len(precise_matches) > 1:

                # get a temporary list for the splits
                good_lines_tmp = gpd.GeoSeries()

                # for all crossing lines
                for _, row_pm in precise_matches.iterrows():
                    # if it is the first cut...
                    if good_lines_tmp.empty:         
                        # split the original street
                        line_split = split(row.geometry, row_pm.geometry)
                        # for all splits
                        for line_num_sp, line_sp in enumerate(line_split):
                            # append split to the tmp split list, changing the index
                            good_lines_tmp = good_lines_tmp.append(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))
                
                    # if it is not the first cut
                    else:
                        
                        # iterate over the cuts done already *by index*
                        for index_glt, line_glt in good_lines_tmp.items(): 
    
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

                # add all the splits to the main list
                good_lines = good_lines.append(good_lines_tmp)

    print('Splitted:')
    print(bad_index)

    df_blocks = gpd.GeoDataFrame(geometry=list(polygonize(good_lines.geometry)))
    
    return(df_blocks)
