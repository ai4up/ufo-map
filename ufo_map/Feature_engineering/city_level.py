

""" City level module

This module includes all functions to calculate features on the city level.

At the moment, it contains the following main functions:

- features_distance_cbd
- features_distance_local_cbd

@authors: Nikola, Felix 

"""

# Imports
import pandas as pd
import geopandas as gpd
import numpy as np
from ufo_map.Utils.helpers import nearest_neighbour
from collections import Counter


def distance_cbd(gdf, gdf_loc):
    """  
    Returns a DataFrame with an additional line that contains the distance to a given point
    
    Calculates the following:
        
        Features:
        ---------
        - Distance to CBD
 
    Args:
        - gdf: geodataframe with trip origin waypoint
        - gdf_loc: location of Point of Interest (format: shapely.geometry.point.Point)  

    Returns:
        - gdf: a DataFrame of shape (number of columns(gdf)+1, len_df) with the 
          computed features

    Last update: 2/12/21. By Felix.

    """
    
    # create numpy array
    np_geom = gdf.geometry.values
    # 1.create new column in dataframe to assign distance to CBD array to
    gdf['feature_distance_cbd'] = np_geom[:].distance(gdf_loc.geometry.iloc[0])
   
    return gdf



def distance_local_cbd(gdf, gdf_loc_local):
    """
    Function to caluclate location of closest local city center for each point. 
    
    Args:
    - gdf: geodataframe with points in geometry column
    - gdf_loc_local: geodataframe with points in geometry column

    Returns:
        - gdf_out: geodataframe with trips only on either weekdays or weekends

    Last update: 13/04/21. By Felix.
    """  
    # call nearest neighbour function
    gdf_out = nearest_neighbour(gdf, gdf_loc_local)
    # rename columns and drop unneccessary ones
    gdf_out = gdf_out.rename(columns={"distance": "feature_distance_local_cbd"})
    gdf_out = gdf_out.drop(columns={'nodeID','closeness_global','kiez_name'})
    return gdf_out


def features_city_level_buildings(gdf,gdf_buildings): 
    '''
    Features:
    - total_buildings_city
    - av_building_footprint_city
    - std_building_footprint_city
    '''
    results = pd.DataFrame()
    results['total_buildings_city'] = [len(gdf_buildings)] * len(gdf)
    results['av_building_footprint_city'] = [gdf_buildings.geometry.area.mean()] * len(gdf)
    results['std_building_footprint_city'] = [gdf_buildings.geometry.area.std()] * len(gdf)
    return(results)


def features_city_level_blocks(gdf,gdf_buildings,block_sizes=[5,10,20]):
    '''
    Features:
    - n_detached_buildings
    - block_i_to_j (starting from 2, up to inf, values chosen in block sizes)
    '''

    # get counts
    single_blocks = gdf_buildings.drop_duplicates(subset = 'TouchesIndexes')
    counts_df = pd.DataFrame.from_dict(dict(Counter(single_blocks.BlockLength)),orient='index').sort_index()

    # prepare ranges
    values = [1,2]+block_sizes+[np.inf]
    ranges = []
    for idx,_ in enumerate(values[:-1]):
        ranges.append([values[idx],values[idx+1]-1])

    # compute metrics
    results = pd.DataFrame()
    for r in ranges: 
        results[f'blocks_{r[0]}_to_{r[1]}'] = [counts_df.loc[r[0]:r[1]][0].sum()] * len(gdf)

    results.rename(columns={'blocks_1_to_1':'n_detached_buildings'},inplace=True)
    return(results)



def feature_city_level_intersections(gdf,gdf_intersections):
    '''
    Features:
     - total_intersection_city
    '''
    return(pd.Series([len(gdf_intersections)] * len(gdf)))


def features_city_level_streets(gdf,gdf_streets):
    '''
    Features:
    - total_length_street_city
    - av_length_street_city
    '''
    results = pd.DataFrame()
    results['total_length_street_city'] = [gdf_streets.geometry.length.sum()] * len(gdf)
    results['av_length_street_city'] = [gdf_streets.geometry.length.mean()] * len(gdf)
    return(results)

def features_city_level_sbb(gdf,gdf_sbb):
    '''
    Features:
    - total_number_block_city
    - av_area_block_city
    - std_area_block_city
    '''
    results = pd.DataFrame()
    results['total_number_block_city'] = [len(gdf_sbb)] * len(gdf)
    results['av_area_block_city'] = [gdf_sbb.geometry.area.mean()] * len(gdf)
    results['std_area_block_city'] = [gdf_sbb.geometry.area.std()] * len(gdf)
    return(results)


def features_city_level_urban_atlas(gdf,gdf_ua,poly_ua_boundary):
    '''
    Features:
    - prop_lu_{}_city
    
    '''
    # sum up land use classes and divide by area of the overall area available in the city
    props = gdf_ua.groupby('class_2012')['area'].sum()/poly_ua_boundary.area
    # fetch index/names and values to save
    results = pd.DataFrame()
    for idx in range(len(props)):
        results[f'prop_{props.index[idx]}'] = [props[idx]] * len(gdf)
    return(results)