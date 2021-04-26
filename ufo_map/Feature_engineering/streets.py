"""
Created on 

@author: 
"""

import numpy as np
import pandas as pd
import geopandas as gpd


def get_closest_object(geom,df_intersected,spatial_index):
    ''' Get closest object, as a one-element series.
    '''

    # empty list of matches indexes
    possible_matches_index = []
    buffer_size = 0
    precise_matches = gpd.GeoDataFrame()

    # until one index gets retrieved
    while len(precise_matches) == 0:

        buffer_size += 100
        buffered_geom = geom.centroid.buffer(buffer_size)

        # retrieve indexes
        possible_matches_index = list(spatial_index.intersection(buffered_geom.bounds))
        possible_matches = df_intersected.loc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(buffered_geom)]

    # retrieve rows and sort by distance to get the closest
    distances = precise_matches['geometry'].distance(geom)
    indexes = precise_matches.index

    return(sorted(zip(distances,indexes),key=lambda x: x[0])[0])



def get_closest_street_ft_values(df,
                        length_ft=False,
                        width_ft=False,
                        width_dev=False,
                        open_ft=False,
                        btw_m_e=False,
                        close_glo=False,
                        clo_500=False
                         ):

    fts_to_fetch = []

    if length_ft: fts_to_fetch.append('length')
    if width_ft: fts_to_fetch.append('width')
    if width_dev: fts_to_fetch.append('width_deviation')
    if open_ft: fts_to_fetch.append('openness')
    if btw_m_e: fts_to_fetch.append('betweenness_metric_e')
    if close_glo: fts_to_fetch.append('closeness_global')     
    if clo_500:fts_to_fetch.append('closeness500')
    
    # fetch them
    df_fts = df[fts_to_fetch]   
    
    # save as numpy arrays
    # initialize from first column
    closest_street_ft_values = np.array(df_fts.iloc[:,0].values)
    # add the others
    for ft in df_fts.columns.values[1:]:
        closest_street_ft_values = np.vstack((closest_street_ft_values,df_fts[ft].values))
        
    return closest_street_ft_values 




def feature_distance_to_closest_intersection(geometries,df_intersections,int_spatial_index):
    ''' Get distance to closest intersection.
    '''
    dist_to_closest_ints = [None] * len(df)

    for geom in geometries:

        closest_int,distance = get_closest_object(geom,df_intersections,int_spatial_index)

        dist_to_closest_ints.append(distance)

    return(dist_to_closest_ints)



def features_closest_street(gdf,
                            streets_gdf,
                            dist_ft=True,
                            length_ft=True,
                            width_ft=True,
                            width_dev=True,
                            open_ft=True,
                            btw_m_e=True,
                            close_glo=True,
                            clo_500=True):
    ''' Computes features from the closest street to an object/point of interest.

    Features:

    - distance_to_closest_road
    - street_length_closest_road
    - street_width_av_closest_road
    - street_width_std_closest_road
    - street_openness_closest_road
    - street_closeness_global_closest_road
    - street_betweeness_global_closest_road
    - street_betweeness_500_closest_road

    Returns: pandas dataframe with the features asked for (by default all).
    '''

    geometries = list(gdf.geometry)
    gdf_inter_sindex = streets_gdf.sindex

    closest_street_ft_values = get_closest_street_ft_values(streets_gdf,
                                            length_ft=length_ft,
                                            width_ft=width_ft,
                                            width_dev=width_dev,
                                            open_ft=open_ft,
                                            btw_m_e=btw_m_e,
                                            close_glo=close_glo,
                                            clo_500=clo_500)

    cols = []
    if dist_ft: cols.append('distance_to_closest_street')
    if length_ft: cols.append('street_length_closest_street')
    if width_ft: cols.append('street_width_av_closest_street')
    if width_dev: cols.append('street_width_std_closest_street')
    if open_ft: cols.append('street_openness_closest_street')
    if btw_m_e: cols.append('street_betweeness_global_closest_street')
    if close_glo: cols.append('street_closeness_global_closest_street')     
    if clo_500: cols.append('street_closeness_500_closest_street')


    values = np.zeros((len(gdf), len(cols)))

    for idx,geom in enumerate(geometries):

        # fetch closest street and distance
        distance,index_str = get_closest_object(geom,streets_gdf,gdf_inter_sindex)
        # fetch row with values in numpy array for appropriate index
        values[idx] = [distance] + closest_street_ft_values[:,index_str].tolist()

    return pd.DataFrame(values,columns=cols, index=gdf.index).fillna(0)






def get_column_names_dist_based_street()


def ft_get_intersection_count_within_buffer():


def features_street_distance_based():
    '''
    - street_length_total_within_buffer
    - street_length_av_within_buffer
    - street_length_std_within_buffer

    - (street_orientation_std_inter_buffer)
    - (street_linearity_av_inter_buffer)
    - (street_linearity_std_inter_buffer)
    - street_width_av_within_buffer
    - street_width_std_within_buffer

    - street_betweeness_global_max_within_buffer
    - street_betweeness_global_av_within_buffer
    - street_betweeness_500_max_within_buffer
    - street_betweeness_500_av_within_buffer
    '''
