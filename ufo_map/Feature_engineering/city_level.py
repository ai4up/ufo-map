

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
import osmnx as ox
from ufo_map.Utils.helpers import nearest_neighbour, convert_to_igraph, get_shortest_dist, get_geometry_type, check_adjust_graph_crs
from ufo_map.Feature_engineering.socio_econ import feature_in_buffer


def shortest_distance_graph(gdf, gdf_center, ox_graph, feature_name):
    if len(gdf_center)==1:
        return distance_cbd_shortest_dist(gdf, gdf_center, ox_graph, feature_name)
    elif len(gdf_center)>1: 
        return distance_local_cbd_shortest_dist(gdf, gdf_center, ox_graph, feature_name)
    else:
        raise ValueError('No location for distance calculation provided!')


def polygon_centroids(gdf):
    gdf_points = gdf.copy(deep=True)
    gdf_points['geometry'] = gdf_points.geometry.centroid
    return gdf, gdf_points


def correct_distances_on_centers(gdf, gdf_center, gdf_points, feature_name):
    # get all ids of polygons that lie on top of centers to assign 0 meter distance
    gdf_sjoin = gpd.sjoin(gdf, gdf_center)
    dist_null_ids = gdf_sjoin['tractid'].tolist()

    gdf_points.loc[gdf_points['tractid'].isin(dist_null_ids), feature_name] = 0.0 
    return gdf_points


def distance_cbd_shortest_dist(gdf, gdf_loc, ox_graph, feature_name):
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
    
    ox_graph = check_adjust_graph_crs(gdf,ox_graph)
    
    geometry_types = get_geometry_type(gdf)
    if 'Polygon' in geometry_types:
        gdf, gdf_points = polygon_centroids(gdf)

    # then we have to convert the multigraph object to a dataframe
    gdf_nodes, gdf_edges = ox.utils_graph.graph_to_gdfs(ox_graph)

    # call nearest neighbour functions
    gdf_orig = nearest_neighbour(gdf_points, gdf_nodes)
    gdf_dest = nearest_neighbour(gdf_loc, gdf_nodes)

    graph_ig, list_osmids = convert_to_igraph(ox_graph)
    gdf_points[feature_name] = gdf_orig.apply(lambda x: get_shortest_dist(graph_ig,
                                                                list_osmids,
                                                                x.osmid,
                                                                gdf_dest.osmid.iloc[0],
                                                                'length'),
                                                                axis=1)

    # add distance from hex center to nearest node (only for nodes where distance != inf)
    dist_start = gdf_orig['distance'][gdf_points[feature_name] != np.inf]
    dist_end = gdf_dest['distance'][0]
    gdf_points.loc[gdf_points[feature_name] != np.inf,feature_name] += dist_start + dist_end

    # check for nodes that could not be connected
    # create numpy array
    np_geom = gdf_points.geometry[gdf_points[feature_name] == np.inf].values
    # assign distance to cbd array
    gdf_points.loc[gdf_points[feature_name] == np.inf,feature_name] = np_geom[:].distance(gdf_loc.geometry.iloc[0])
    
    if 'Polygon' in geometry_types:
        gdf_points = correct_distances_on_centers(gdf,gdf_loc,gdf_points,feature_name)
        gdf = pd.merge(gdf, gdf_points[['tractid', feature_name]])
    return gdf[['tractid',feature_name]]


def find_nearest_osmid(gdf, gdf_loc_local, ox_graph):
    # find nearest subcenters
    gdf_tmp = nearest_neighbour(gdf, gdf_loc_local)
    gdf_tmp = gdf_tmp.rename(columns={'distance': 'distance_crow'})
    # find nearest node odsmids at orig and dest
    gdf_nodes, gdf_edges = ox.utils_graph.graph_to_gdfs(ox_graph)
    gdf_orig = nearest_neighbour(gdf_tmp, gdf_nodes)
    gdf_dest = nearest_neighbour(gdf_loc_local, gdf_nodes)
    return gdf_orig.merge(gdf_dest, how='left', on='id_sub')


def distance_local_cbd_shortest_dist(gdf, gdf_loc_local, ox_graph, feature_name):
    """
    Returns a DataFrame with an additional line that contains the distance to points in gdf_loc_local
    based on the shortest path calculated with igraph's shortest_path function.
    We convert to igraph in order to save 100ms per shortest_path calculation.
    For more info refer to the notebook shortest_path.ipynb or
    https://github.com/gboeing/osmnx-examples/blob/main/notebooks/14-osmnx-to-igraph.ipynb
    """
    # create unique id for each cbd in gdf_loc_local
    gdf_loc_local = gdf_loc_local.reset_index(drop=True)
    gdf_loc_local['id_sub'] = gdf_loc_local.index

    ox_graph = check_adjust_graph_crs(gdf,ox_graph)
    geometry_types = get_geometry_type(gdf)
    if 'Polygon' in geometry_types:
        gdf_poly, gdf_points = polygon_centroids(gdf)
        
    gdf_osmid = find_nearest_osmid(gdf_points,gdf_loc_local, ox_graph)
    graph_ig, list_osmids = convert_to_igraph(ox_graph) # transformation for performance
    gdf_points[feature_name] = gdf_osmid.apply(lambda x: get_shortest_dist(graph_ig,
                                                                list_osmids,
                                                                x.osmid_x,
                                                                x.osmid_y,
                                                                'length'),
                                                                axis=1)

    # add distance from hex center to nearest node (only for nodes where distance != inf)
    dist_start = gdf_osmid['distance_x'][gdf_points[feature_name] != np.inf]
    dist_end = gdf_osmid['distance_y'][gdf_points[feature_name] != np.inf]
    gdf_points.loc[gdf_points[feature_name] != np.inf, feature_name] += dist_start + dist_end

    # check for nodes that could not be connected and assing crow flies distance
    gdf_points.loc[gdf_points[feature_name]==np.inf,feature_name] = np.nan

    if 'Polygon' in geometry_types:
        gdf_points = correct_distances_on_centers(gdf_poly, gdf_loc_local, gdf_points,feature_name)  
        gdf = pd.merge(gdf, gdf_points[['tractid', feature_name]])   
    return gdf[['tractid',feature_name]]


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
    gdf_out = gdf_out.drop(columns={'nodeID', 'closeness_global', 'kiez_name'})
    return gdf_out


def features_city_boundary(gdf_boundary):
    '''
    '''


def features_city_level_buildings(gdf_buildings):
    '''
    Features:
    - total_buildings_city
    - av_building_footprint_city
    - std_building_footprint_city
    '''
    return pd.DataFrame({
        'total_buildings_city': len(gdf_buildings),
        'total_buildings_footprint_city': gdf_buildings.geometry.area.sum(),
        'av_building_footprint_city': gdf_buildings.geometry.area.mean(),
        'std_building_footprint_city': gdf_buildings.geometry.area.std()},
        index=[0])


def features_city_level_blocks(gdf_buildings, block_sizes=[5, 10, 20]):
    '''
    Features:
    - n_detached_buildings
    - block_i_to_j (starting from 2, up to inf, values chosen in block sizes)
    '''

    # get counts
    gdf_buildings['TouchesIndexes'] = gdf_buildings['TouchesIndexes'].astype(str)
    single_blocks = gdf_buildings.drop_duplicates(subset=['TouchesIndexes'])
    counts_df = pd.DataFrame.from_dict(dict(Counter(single_blocks.BlockLength)), orient='index').sort_index()

    # prepare ranges
    values = [1, 2] + block_sizes + [np.inf]
    ranges = []
    for idx, _ in enumerate(values[:-1]):
        ranges.append([values[idx], values[idx + 1] - 1])

    # compute metrics
    results = pd.DataFrame(index=[0])
    for r in ranges:
        results[f'blocks_{r[0]}_to_{r[1]}'] = counts_df.loc[r[0]:r[1]][0].sum()

    results.rename(columns={'blocks_1_to_1': 'n_detached_buildings'}, inplace=True)
    return(results)


def feature_city_level_intersections(gdf_intersections):
    '''
    Features:
     - total_intersection_city
    '''
    return pd.DataFrame({'intersections_count': len(gdf_intersections)},
                        index=[0])


def features_city_level_streets(gdf_streets):
    '''
    Features:
    - total_length_street_city
    - av_length_street_city
    '''
    return pd.DataFrame({
        'total_length_street_city': gdf_streets.geometry.length.sum(),
        'av_length_street_city': gdf_streets.geometry.length.mean()},
        index=[0])


def features_city_level_sbb(gdf_sbb):
    '''
    Features:
    - total_number_block_city
    - av_area_block_city
    - std_area_block_city
    '''
    return pd.DataFrame({
        'total_number_block_city': len(gdf_sbb),
        'av_area_block_city': gdf_sbb.geometry.area.mean(),
        'std_area_block_city': gdf_sbb.geometry.area.std()},
        index=[0])


def features_city_level_urban_atlas(gdf_ua, poly_ua_boundary):
    '''
    Features:
    - prop_lu_{}_city

    '''
    # sum up land use classes and divide by area of the overall area available in the city
    props = gdf_ua.groupby('class_2012')['area'].sum() / poly_ua_boundary.area
    # fetch index/names and values to save
    results = pd.DataFrame()
    for idx in range(len(props)):
        results[f'prop_{props.index[idx]}'] = [props[idx]] * len(gdf)
    return(results)


def city_area_km2(gdf,feature_name):
    """calculates tot area and assigns one val to all rows of col 'feature_name'"""
    gdf_zips = gdf.copy(deep=True)
    gdf_zips['area'] = gdf_zips.geometry.area
    gdf[feature_name] = gdf_zips.area.sum()*1e-6
    return gdf

def network_length_km(gdf, ox_graph,feature_name):
    """calculates oxgraph network length and assigns one val to all rows of col 'feature_name'"""
    ox_graph = check_adjust_graph_crs(gdf,ox_graph)
    _, gdf_edges = ox.utils_graph.graph_to_gdfs(ox_graph)

    gdf_streets = gdf_edges.reset_index()
    gdf_streets['street_length'] = gdf_streets.geometry.length
    gdf[feature_name] = gdf_streets['street_length'].sum()*1e-3
    return gdf


def _lu_to_gdf(df_lu):
    # create gdf out of lu data
    df_lu['geometry'] = gpd.points_from_xy(x=df_lu['bbox'].str['minx'], y=df_lu['bbox'].str['miny'])
    return gpd.GeoDataFrame(df_lu,crs=4326)


def lu_counts_per_zip(gdf, df_lu):
    gdf_lu = _lu_to_gdf(df_lu).to_crs(gdf.crs)
    gdf_sjoin = gpd.sjoin(gdf,gdf_lu[['land_use','geometry']],how='left')    
    df_lu_counts = gdf_sjoin.groupby('tractid')['land_use'].value_counts().to_frame('counts').reset_index()
    
    # get total num of pois per class
    class_counts = df_lu['land_use'].value_counts()
    return df_lu_counts, class_counts


def _get_pop_count_per_geom(gdf_pop, gdf):
    return feature_in_buffer(gdf, gdf_pop, 'total_population', 'counts',
                                    id_col='tractid',feature_type='total')[['tractid','counts']]


def _add_pop_data(gdf_pop, gdf):
    df_pop = _get_pop_count_per_geom(gdf_pop, gdf) 
    pop_merge = pd.merge(gdf,df_pop,on='tractid')
    pop_merge['total_count'] = pop_merge['counts'].sum()
    pop_merge['lu_perc'] = pop_merge['counts']/pop_merge['total_count']
    pop_merge['land_use']='Population Count'
    # merge df_lu_counts with pop dense data
    return pop_merge


def prepare_lu_data(gdf, df_lu, entropy_type='classic', gdf_pop = None):
    """
    2 possible entropy calculations require different preprocessing steps, defined via "entropy_type"
    - 'classic': relative count per taz
    - 'normed': relative count to overall count, relative per taz
    
    """
    print('preparing lu data...')
    df_lu_counts, class_counts = lu_counts_per_zip(gdf, df_lu)

    df_lu['total_count'] = np.nan
    for lu_class in class_counts.index:
        df_lu_counts.loc[df_lu_counts['land_use']==lu_class,'total_count'] = class_counts[lu_class]
    
    if gdf_pop is not None:
        df_pop = _add_pop_data(gdf_pop, gdf)
        
    if entropy_type=='normed':
        df_lu_counts['lu_perc'] = df_lu_counts['counts']/df_lu_counts['total_count']
        if gdf_pop is not None: df_lu_counts = pd.concat([df_lu_counts, df_pop[['tractid','land_use','counts','total_count','lu_perc']]])
        df_lu_counts = pd.merge(df_lu_counts,df_lu_counts.groupby('tractid')['lu_perc'].sum().to_frame('perc_sum'), on ='tractid') 
        df_lu_counts['lu_vals'] = df_lu_counts['lu_perc']/df_lu_counts['perc_sum']
    else: 
        if gdf_pop is not None: df_lu_counts = pd.concat([df_lu_counts, df_pop[['tractid','land_use','counts','total_count']]])
        df_lu_counts = pd.merge(df_lu_counts, df_lu_counts.groupby('tractid')['counts'].sum().to_frame('zip_counts').reset_index())
        df_lu_counts['lu_vals'] = df_lu_counts['counts']/df_lu_counts['zip_counts']
    
    return df_lu_counts
    

def land_use_entropy(gdf,
                df_lu,
                entropy_type = 'classic',
                gdf_pop = None):
    
    df_lu_counts = prepare_lu_data(gdf, df_lu,entropy_type, gdf_pop)
    class_counts = len(set(df_lu_counts.land_use))

    def _get_entropy(a):
        return -(sum(a['lu_vals']*np.log(a['lu_vals'])))/np.log(class_counts)
    
    return df_lu_counts.groupby('tractid').apply(lambda x: _get_entropy(x[['lu_vals']])).to_frame('ft_lu_entropy_'+entropy_type).reset_index()