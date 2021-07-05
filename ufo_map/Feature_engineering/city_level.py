

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
from collections import Counter
import networkx as nx
import igraph as ig
import osmnx as ox
from ufo_map.Utils.helpers import nearest_neighbour,convert_to_igraph, get_shortest_dist


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

def distance_cbd_shortest_dist(gdf, gdf_loc, graph):
    """  
    Returns a DataFrame with an additional line that contains the distance to a given point
    based on the shortest path calculated with igraph's shortest_path function.
    We convert to igraph in order to save 100ms per shortest_path calculation.
    For more info refer to the notebook shortest_path.ipynb or
    https://github.com/gboeing/osmnx-examples/blob/main/notebooks/14-osmnx-to-igraph.ipynb 
    
    Calculates the following:
        
        Features:
        ---------
        - Distance to CBD (based on graph network)
 
    Args:
        - gdf: geodataframe with trip origin waypoint
        - gdf_loc: location of Point of Interest (format: shapely.geometry.point.Point)
        - graph: Multigraph Object downloaded from osm  

    Returns:
        - gdf: a DataFrame of shape (number of columns(gdf)+1, len_gdf) with the 
          computed features

    Last update: 29/06/21. By Felix.
    """
    # then we have to convert the multigraph object to a dataframe
    gdf_nodes_4326, gdf_edges_4326 = ox.utils_graph.graph_to_gdfs(graph)
    
    gdf_4326 = gdf.to_crs(4326)
    gdf_loc_4326 = gdf_loc.to_crs(4326)

    # call nearest neighbour function
    gdf_orig_4326 = nearest_neighbour(gdf_4326, gdf_nodes_4326)
    gdf_dest_4326  = nearest_neighbour(gdf_loc_4326, gdf_nodes_4326)

    graph_ig, list_osmids = convert_to_igraph(graph)
    gdf['feature_distance_cbd'] = gdf_orig_4326.apply(lambda x: get_shortest_dist(graph_ig,
                                                                                     list_osmids, 
                                                                                     x.osmid, 
                                                                                     gdf_dest_4326.osmid.iloc[0], 
                                                                                     'length'),
                                                                                     axis=1)
    
    # add distance from hex center to nearest node (only for nodes where distance != inf)
    dist_start = gdf_orig_4326['distance'][gdf.feature_distance_cbd != np.inf]
    dist_end = gdf_dest_4326['distance'][0]
    gdf.feature_distance_cbd[gdf.feature_distance_cbd != np.inf] += dist_start + dist_end

    # check for nodes that could not be connected
    # create numpy array 
    np_geom = gdf.geometry[gdf.feature_distance_cbd == np.inf].values
    #assign distance to cbd array
    gdf.feature_distance_cbd[gdf.feature_distance_cbd == np.inf] = np_geom[:].distance(gdf_loc.geometry.iloc[0])

    print('Calculated distance to cbd based on shortest path')
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


def distance_local_cbd_shortest_dist(gdf, gdf_loc_local, graph):
    """  
    Returns a DataFrame with an additional line that contains the distance to points in gdf_loc_local
    based on the shortest path calculated with igraph's shortest_path function.
    We convert to igraph in order to save 100ms per shortest_path calculation.
    For more info refer to the notebook shortest_path.ipynb or
    https://github.com/gboeing/osmnx-examples/blob/main/notebooks/14-osmnx-to-igraph.ipynb 

    Calculates the following:
        
        Features:
        ---------
        - Distance to local cbd (based on graph network)

    Args:
        - gdf: geodataframe with trip origin waypoint
        - gdf_loc: location of Points of Interest (format: shapely.geometry.point.Point)
        - graph: Multigraph Object downloaded from osm  

    Returns:
        - gdf: a DataFrame of shape (number of columns(gdf)+1, len_gdf) with the 
            computed features

    Last update: 01/07/21. By Felix.
    """


    # call nearest neighbour to find nearest local center
    gdf_out = nearest_neighbour(gdf, gdf_loc_local)
    # rename distance column
    gdf_out = gdf_out.rename(columns={'distance':'distance_crow'})
    # remove unnecessary columns
    gdf_out = gdf_out.drop(columns={'closeness_global','kiez_name'})

    # convert input gdf to crs
    gdf_4326 = gdf_out.to_crs(4326)
    gdf_loc_local_4326 = gdf_loc_local.to_crs(4326)

    # then we have to convert the multigraph object to a dataframe
    gdf_nodes_4326, gdf_edges_4326 = ox.utils_graph.graph_to_gdfs(graph)
    # call nearest neighbour function to find nearest node
    gdf_orig_4326 = nearest_neighbour(gdf_4326, gdf_nodes_4326)
    gdf_dest_4326  = nearest_neighbour(gdf_loc_local_4326, gdf_nodes_4326)

    # merge on node ID 
    gdf_merge_4326 =  gdf_orig_4326.merge(gdf_dest_4326,how='left',on=['nodeID'])

    # convert to igraph
    graph_ig, list_osmids = convert_to_igraph(graph)
    
    # call get shortest dist func, where gdf_merge_3426.osmid_x is nearest node from starting point and osmid_y is 
    # nearest node from end destination (one of the neighbourhood centers)
    gdf['feature_distance_local_cbd'] = gdf_merge_4326.apply(lambda x: get_shortest_dist(graph_ig,
                                                                                        list_osmids, 
                                                                                        x.osmid_x, 
                                                                                        x.osmid_y, 
                                                                                        'length'),
                                                                                        axis=1)

    # add distance from hex center to nearest node (only for nodes where distance != inf)
    dist_start = gdf_merge_4326['distance_x'][gdf.feature_distance_local_cbd != np.inf]
    dist_end = gdf_merge_4326['distance_y'][gdf.feature_distance_local_cbd != np.inf]
    gdf.feature_distance_local_cbd[gdf.feature_distance_local_cbd != np.inf] += dist_start + dist_end

    # check for nodes that could not be connected and assing crow flies distance
    gdf.feature_distance_local_cbd[gdf.feature_distance_local_cbd == np.inf] = gdf_merge_4326['distance_crow'][gdf.feature_distance_local_cbd == np.inf]
    
    print('Calculated distance to local cbd based on shortest path')
    return gdf     


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