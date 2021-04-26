"""
Created on 

@author: 
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from ufo_map.Utils.helpers_ft_eng import get_indexes_right_bbox


### HELPERS

def get_closest_object(geom,geom_intersections,spatial_index):
    ''' Get closest object, as a one-element series.
    '''

    # empty list of matches indexes
    possible_matches_index = []
    buffer_size = 0
    indexes = []

    # until one index gets retrieved
    while len(indexes) == 0:

        buffer_size += 100
        buffered_geom = geom.centroid.buffer(buffer_size).bounds

        # retrieve indexes
        indexes = list(spatial_index.intersection(buffered_geom))
        
    close_points = geom_intersections[indexes]

    # retrieve rows and sort by distance to get the closest
    distances = [item.distance(geom) for item in close_points]

    return(sorted(zip(distances,indexes),key=lambda x: x[0])[0])



def get_street_ft_values(df,
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
    street_ft_values = np.array(df_fts.iloc[:,0].values)
    # add the others
    for ft in df_fts.columns.values[1:]:
        street_ft_values = np.vstack((street_ft_values,df_fts[ft].values))
        
    return street_ft_values 



def compute_total_street_len_within_buffer(idx,group,geometries_streets_gdf,bbox_geom):
    '''Compute the total street length within a buffer.

    If the street continues beyond the buffer, only the part that is actually within
    gets added.

    '''
    total_str_len = 0 

    for j in group:
        geom = geometries_streets_gdf[j]
        total_str_len += geom.length if geom.within(bbox_geom[idx]) else geom.intersection(bbox_geom[idx]).length

    return(total_str_len)



### FEATURES 


def feature_distance_to_closest_intersection(geometries,geom_intersections,int_spatial_index):
    ''' Get distance to closest intersection.

    Geometries should be provided as numpy arrays.

    '''
    dist_to_closest_ints = [None] * len(geometries)

    for idx,geom in enumerate(geometries):

        distance,closest_int = get_closest_object(geom,geom_intersections,int_spatial_index)

        dist_to_closest_ints[idx] = distance

    return(dist_to_closest_ints)



def features_closest_street(gdf,
                            streets_gdf,
                            buffer_sizes,
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

    geometries = np.array(gdf.geometry)
    geometries_streets = np.array(streets_gdf.geometry)
    gdf_inter_sindex = streets_gdf.sindex

    street_ft_values = get_street_ft_values(streets_gdf,
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
        distance,index_str = get_closest_object(geom,geometries_streets,gdf_inter_sindex)
        # fetch row with values in numpy array for appropriate index
        values[idx] = [distance] + street_ft_values[:,index_str].tolist()

    return pd.DataFrame(values,columns=cols, index=gdf.index).fillna(0)



def feature_intersection_count_within_buffer(geometries,gdf_inter_sindex,buffer_sizes):
    '''
    Get the number of intersections within different buffer sizes.

    Returns a dataframe.
    '''

    results = pd.DataFrame()

    for buffer_size in buffer_sizes:

        col = 'intersection_count_within_{}'.format(buffer_size)

        # fetch points in buffer
        indexes,_ = get_indexes_right_bbox(geometries,gdf_inter_sindex,buffer_size)

        # retrieve counts
        results[col] = [len(x) for x in indexes]

    return results



def features_street_distance_based(gdf,
                         streets_gdf,
                         buffer_sizes,
                         tot_len=True,
                         av_len=True,
                         std_len=True,
                         av_width=True,
                         std_width=True,
                         max_btw_glo=True,
                         av_btw_glo=True,
                         max_clo_500=True,
                         av_clo_500=True
                                    ):
    ''' Computes street features within buffers.

    Features:
    - street_length_total_within_buffer
    - street_length_av_within_buffer
    - street_length_std_within_buffer
    - street_width_av_within_buffer
    - street_width_std_within_buffer
    - street_betweeness_global_max_within_buffer
    - street_betweeness_global_av_within_buffer
    - street_closeness_500_max_within_buffer
    - street_closeness_500_av_within_buffer

    Returns a dataframe.

    '''

    av_street_ft_values = get_street_ft_values(streets_gdf,
                                            length_ft=av_len,
                                            width_ft=av_width,
                                            width_dev=False,
                                            open_ft=False,
                                            btw_m_e=av_btw_glo,
                                            close_glo=False,
                                            clo_500=av_clo_500)

    std_street_ft_values = get_street_ft_values(streets_gdf,
                                            length_ft=std_len,
                                            width_ft=False,
                                            width_dev=std_width,
                                            open_ft=False,
                                            btw_m_e=False,
                                            close_glo=False,
                                            clo_500=False)

    max_street_ft_values = get_street_ft_values(streets_gdf,
                                        length_ft=False,
                                        width_ft=False,
                                        width_dev=False,
                                        open_ft=False,
                                        btw_m_e=max_btw_glo,
                                        close_glo=False,
                                        clo_500=max_clo_500)

    result_list = []

    for buffer_size in buffer_sizes:

        print(buffer_size)

        # prepare input
        geometries = list(gdf.geometry)
        geometries_streets_gdf = list(streets_gdf.geometry)
        gdf_inter_sindex = streets_gdf.sindex

        # get the streets in buffer
        indexes_right,bbox_geom = get_indexes_right_bbox(geometries,
                                                            gdf_inter_sindex,
                                                            buffer_size)
        
        # prepare output 
        cols = []
        if tot_len: cols.append(f'street_length_total_within_buffer_{buffer_size}')
        if av_len: cols.append(f'street_length_av_within_buffer_{buffer_size}')
        if av_width: cols.append(f'street_width_av_within_buffer_{buffer_size}')
        if av_btw_glo: cols.append(f'street_betweeness_global_av_within_buffer_{buffer_size}')
        if av_clo_500: cols.append(f'street_closeness_500_av_within_buffer_{buffer_size}')
        if std_len: cols.append(f'street_length_std_within_buffer_{buffer_size}')
        if std_width: cols.append(f'street_width_std_within_buffer_{buffer_size}')
        if max_btw_glo: cols.append(f'street_betweeness_global_max_within_buffer_{buffer_size}')
        if max_clo_500: cols.append(f'street_closeness_500_max_within_buffer_{buffer_size}')

        values = np.zeros((len(gdf), len(cols)))


        for idx,group in enumerate(indexes_right):

            if not group == []:

                row_values = []

                # get the actual total street length
                if tot_len:
                    row_values += [compute_total_street_len_within_buffer(idx,
                                                                         group,
                                                                         geometries_streets_gdf,
                                                                         bbox_geom)]
                # compute average values within buffer
                if av_len or av_btw_glo or av_clo_500:
                    row_values += av_street_ft_values[:, group].mean(axis=1).tolist()

                # compute std values within buffer
                if std_len or std_width:
                    row_values += std_street_ft_values[:, group].std(axis=1, ddof=1).tolist()

                # compute max values within buffer
                if max_clo_500 or max_btw_glo:
                    row_values += max_street_ft_values[:, group].max(axis=1).tolist()

            else:
                len_array= sum([tot_len,av_len,std_len,av_width,std_width,max_btw_glo,av_btw_glo,max_clo_500,av_clo_500])
                row_values = [0]*len_array  

            values[idx] = row_values

        # Assemble for a buffer size
        tmp_df = pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df