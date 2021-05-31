import pandas as pd
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



def split_crossing_streets(streets):
    ''' Splits any street that does not end at an intersection, but crosses an other street.
    '''
    
    lines_to_polygonize = streets.geometry

    # get lines to split
    joined_gdf = gpd.sjoin(streets, streets, how="left", op="crosses")
    joined_gdf = joined_gdf.dropna(subset=['index_right'])

    # get set of index of lines to split   
    indexes_lines_to_split = set(joined_gdf.index)
    # get indexes to split with respectively
    indexes_lines_split_with = [joined_gdf.loc[idx_to_split].index_right for idx_to_split in indexes_lines_to_split]
    
    print(f'Will split roads:{indexes_lines_to_split}')
    
    for idx_to_split,idx_split_with in zip(indexes_lines_to_split,indexes_lines_split_with): 
        
        # initalize line to split
        street_left = gpd.GeoSeries(streets.loc[idx_to_split].geometry,index=[idx_to_split])
        # make sure to gdfs for iterrows
        if type(idx_split_with) != pd.core.series.Series: idx_split_with = [idx_split_with]
        
        # for all lines to split with
        for idx_right,row in streets.loc[idx_split_with].iterrows():

            # for all splits from the line to split (originally one, then possibly more)
            for idx_left,line_left in zip(street_left.index,street_left):

                # perform the split between the line to split with and splits for the main line
                splits = [line_split for line_split in split(line_left, row.geometry)]

                # if the lines crossed and generated splits
                if len(splits)>1:

                    # add the splits to the geoseries, change index
                    for n_split,line_split in enumerate(splits): 
                        street_left = street_left.append(gpd.GeoSeries(line_split,index=[idx_left*10+n_split]))

                    # remove the line that has been split
                    street_left = street_left.drop(idx_left)
      
        # update the main geoseries
        lines_to_polygonize = lines_to_polygonize.drop(idx_to_split)
        lines_to_polygonize = lines_to_polygonize.append(street_left)
    
    return(lines_to_polygonize)



def generate_sbb(streets):
    ''' Generate a GeoDataFrame with street-based blocks polygons from street linestrings,
    and computes a few metrics.
    '''

    lines_to_polygonize = split_crossing_streets(streets)

    sbb = gpd.GeoDataFrame(geometry=list(polygonize(lines_to_polygonize.geometry)))

    sbb['area'] = sbb.area
    sbb['streets_based_block_orientation'] =  momepy.Orientation(sbb).series
    sbb['Corners'] =  momepy.Corners(sbb).series

    max_dist = sbb.geometry.map(lambda g: g.centroid.hausdorff_distance(g.exterior))
    circle_area = sbb.geometry.centroid.buffer(max_dist).area
    sbb['Phi'] = sbb.geometry.area / circle_area

    return(sbb)

