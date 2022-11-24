"""
Created on

@author:
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
from ufo_map.Utils.helpers import _check_geometry_type


# HELPERS

def get_closest_object(geom, geom_intersections, spatial_index):
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

    return(sorted(zip(distances, indexes), key=lambda x: x[0])[0])


def get_sbb_containing_object(geom, geom_sbbs, spatial_index):
    '''
    Get the index of the sbb where an object of interest stands.
    '''

    # get sbbs that intersect the bounds of the object
    indexes = list(spatial_index.intersection(geom.bounds))
    matches = geom_sbbs[indexes]

    if len(matches) == 1:

        return indexes[0]

    elif len(matches) > 1:

        areas = [item.intersection(geom).area for item in matches]

        return(sorted(zip(areas, indexes), key=lambda x: x[0])[0][1])

    else:
        return(None)


def ft_fetcher(df, fts_to_fetch):

    df_fts = df[fts_to_fetch]

    # save as numpy arrays
    # initialize from first column
    ft_values = np.array(df_fts.iloc[:, 0].values)
    # add the others
    for ft in df_fts.columns.values[1:]:
        ft_values = np.vstack((ft_values, df_fts[ft].values))

    return(ft_values)


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

    if length_ft:
        fts_to_fetch.append('length')
    if width_ft:
        fts_to_fetch.append('width')
    if width_dev:
        fts_to_fetch.append('width_deviation')
    if open_ft:
        fts_to_fetch.append('openness')
    if btw_m_e:
        fts_to_fetch.append('betweenness_metric_e')
    if close_glo:
        fts_to_fetch.append('closeness_global')
    if clo_500:
        fts_to_fetch.append('closeness500')

    return ft_fetcher(df, fts_to_fetch)


def get_sbb_ft_values(sbb_df,
                      area_ft=True,
                      phi_ft=True,
                      corners_ft=True,
                      orientation_ft=True):

    fts_to_fetch = []

    if area_ft:
        fts_to_fetch.append('area')
    if phi_ft:
        fts_to_fetch.append('Phi')
    if corners_ft:
        fts_to_fetch.append('Corners')
    if orientation_ft:
        fts_to_fetch.append('streets_based_block_orientation')

    return ft_fetcher(sbb_df, fts_to_fetch)


def compute_total_street_len_within_buffer(idx, group, geometries_streets_gdf, bbox_geom):
    '''Compute the total street length within a buffer.

    If the street continues beyond the buffer, only the part that is actually within
    gets added.

    '''
    total_str_len = 0

    for j in group:
        geom = geometries_streets_gdf[j]
        total_str_len += geom.length if geom.within(bbox_geom[idx]) else geom.intersection(bbox_geom[idx]).length

    return(total_str_len)


# FEATURES


def feature_distance_to_closest_intersection(geometries, geom_intersections, int_spatial_index):
    ''' Get distance to closest intersection.

    Geometries should be provided as numpy arrays.

    '''
    print('Computing distance to closest intersection...')

    dist_to_closest_ints = [None] * len(geometries)

    for idx, geom in enumerate(geometries):

        distance, closest_int = get_closest_object(geom, geom_intersections, int_spatial_index)

        dist_to_closest_ints[idx] = distance

    return(dist_to_closest_ints)


def features_closest_street(gdf,
                            streets_gdf,
                            buffer_sizes=[100, 500],
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
    print('Computing closest street fts')

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
    if dist_ft:
        cols.append('distance_to_closest_street')
    if length_ft:
        cols.append('street_length_closest_street')
    if width_ft:
        cols.append('street_width_av_closest_street')
    if width_dev:
        cols.append('street_width_std_closest_street')
    if open_ft:
        cols.append('street_openness_closest_street')
    if btw_m_e:
        cols.append('street_betweeness_global_closest_street')
    if close_glo:
        cols.append('street_closeness_global_closest_street')
    if clo_500:
        cols.append('street_closeness_500_closest_street')

    values = np.zeros((len(gdf), len(cols)))

    for idx, geom in enumerate(geometries):

        # fetch closest street and distance
        distance, index_str = get_closest_object(geom, geometries_streets, gdf_inter_sindex)
        # fetch row with values in numpy array for appropriate index
        values[idx] = [distance] + street_ft_values[:, index_str].tolist()

    return pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)


def feature_intersection_count_within_buffer(geometries, gdf_inter_sindex, buffer_sizes=[100, 500]):
    '''
    Get the number of intersections within different buffer sizes.

    Returns a dataframe.
    '''
    print('Computing intersection count')

    results = pd.DataFrame()

    for buffer_size in buffer_sizes:

        col = 'intersection_count_within_{}'.format(buffer_size)

        # fetch points in buffer
        indexes, _ = get_indexes_right_bbox(geometries, gdf_inter_sindex, buffer_size)

        # retrieve counts
        results[col] = [len(x) for x in indexes]

    return results


def features_street_distance_based(gdf,
                                   streets_gdf,
                                   buffer_sizes=[100, 500],
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
    print('Computing street distance based')

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
        indexes_right, bbox_geom = get_indexes_right_bbox(geometries,
                                                          gdf_inter_sindex,
                                                          buffer_size)

        # prepare output
        cols = []
        if tot_len:
            cols.append(f'street_length_total_within_buffer_{buffer_size}')
        if av_len:
            cols.append(f'street_length_av_within_buffer_{buffer_size}')
        if av_width:
            cols.append(f'street_width_av_within_buffer_{buffer_size}')
        if av_btw_glo:
            cols.append(f'street_betweeness_global_av_within_buffer_{buffer_size}')
        if av_clo_500:
            cols.append(f'street_closeness_500_av_within_buffer_{buffer_size}')
        if std_len:
            cols.append(f'street_length_std_within_buffer_{buffer_size}')
        if std_width:
            cols.append(f'street_width_std_within_buffer_{buffer_size}')
        if max_btw_glo:
            cols.append(f'street_betweeness_global_max_within_buffer_{buffer_size}')
        if max_clo_500:
            cols.append(f'street_closeness_500_max_within_buffer_{buffer_size}')

        values = np.zeros((len(gdf), len(cols)))

        for idx, group in enumerate(indexes_right):

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
                len_array = sum([tot_len, av_len, std_len, av_width, std_width,
                                max_btw_glo, av_btw_glo, max_clo_500, av_clo_500])
                row_values = [0] * len_array

            values[idx] = row_values

        # Assemble for a buffer size
        tmp_df = pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df


def features_own_sbb(gdf,
                     sbb_gdf,
                     area_ft=True,
                     phi_ft=True,
                     corners_ft=True):
    '''
    Compute street based block features for the sbb where the object
    of interest stands.

    Features:
    - street_based_block_area
    - street_based_block_phi
    - street_based_block_corners

    Returns a pd dataframe with the features.
    '''
    print('Computing own sbb')

    geometries = np.array(gdf.geometry)
    geometries_sbb = np.array(sbb_gdf.geometry)
    spatial_index = sbb_gdf.sindex

    sbb_ft_values = get_sbb_ft_values(sbb_gdf,
                                      area_ft=area_ft,
                                      phi_ft=phi_ft,
                                      corners_ft=corners_ft,
                                      orientation_ft=False)

    cols = []

    if area_ft:
        cols.append('street_based_block_area')
    if phi_ft:
        cols.append('street_based_block_phi')
    if corners_ft:
        cols.append('street_based_block_corners')

    values = np.zeros((len(gdf), len(cols)))

    for idx, geom in enumerate(geometries):

        # fetch closest street and distance
        index_sbb = get_sbb_containing_object(geom, geometries_sbb, spatial_index)

        if index_sbb is not None:
            # fetch row with values in numpy array for appropriate index
            values[idx] = sbb_ft_values[:, index_sbb].tolist()

        else:
            values[idx] = [0] * sum([area_ft, phi_ft, corners_ft])

    return pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)


def features_sbb_distance_based(gdf,
                                sbb_gdf,
                                buffer_sizes=[100, 500],
                                n_sbb=True,
                                av_area=True,
                                std_area=True,
                                av_phi=True,
                                std_phi=True,
                                std_ori=True
                                ):
    """ Compute features on street based blocks within different bounding boxes.

    Features:
    - street_based_block_number_inter_buffer
    - street_based_block_av_area_inter_buffer
    - street_based_block_std_area_inter_buffer
    - street_based_block_av_phi_inter_buffer
    - street_based_block_std_phi_inter_buffer
    - street_based_block_std_orientation_inter_buffer

    Returns a pd dataframe with the features.
    """
    print('Computing SBB distance based')

    sbb_av_ft_values = get_sbb_ft_values(sbb_gdf,
                                         area_ft=av_area,
                                         phi_ft=av_phi,
                                         corners_ft=False,
                                         orientation_ft=False)

    sbb_std_ft_values = get_sbb_ft_values(sbb_gdf,
                                          area_ft=std_area,
                                          phi_ft=std_phi,
                                          corners_ft=False,
                                          orientation_ft=std_ori)

    result_list = []

    for buffer_size in buffer_sizes:

        print(buffer_size)

        # prepare input
        geometries = list(gdf.geometry)
        geometries_sbb = list(sbb_gdf.geometry)
        gdf_inter_sindex = sbb_gdf.sindex

        # get the streets in buffer
        indexes_right, bbox_geom = get_indexes_right_bbox(geometries,
                                                          gdf_inter_sindex,
                                                          buffer_size)
        # prepare output
        cols = []
        if n_sbb:
            cols.append(f'street_based_block_number_inter_buffer_{buffer_size}')
        if av_area:
            cols.append(f'street_based_block_av_area_inter_buffer_{buffer_size}')
        if av_phi:
            cols.append(f'street_based_block_av_phi_inter_buffer_{buffer_size}')
        if std_area:
            cols.append(f'street_based_block_std_area_inter_buffer_{buffer_size}')
        if std_phi:
            cols.append(f'street_based_block_std_phi_inter_buffer_{buffer_size}')
        if std_ori:
            cols.append(f'street_based_block_std_orientation_inter_buffer_{buffer_size}')

        values = np.zeros((len(gdf), len(cols)))

        for idx, group in enumerate(indexes_right):

            if not group == []:

                row_values = []

                if n_sbb:
                    row_values += [len(group)]

                if av_area or av_phi:
                    row_values += sbb_av_ft_values[:, group].mean(axis=1).tolist()

                if std_area or std_phi or std_ori:
                    row_values += sbb_std_ft_values[:, group].std(axis=1, ddof=1).tolist()

            else:
                len_array = sum([n_sbb, av_area, std_area, av_phi, std_phi, std_ori])
                row_values = [0] * len_array

            values[idx] = row_values

        # Assemble for a buffer size
        tmp_df = pd.DataFrame(values, columns=cols, index=gdf.index).fillna(0)
        result_list.append(tmp_df)

    # Assemble for all buffer sizes
    full_df = pd.concat(result_list, axis=1)

    return full_df


def feature_beta_index(gdf, graph):
    """
    Returns the beta index (average num of edges per node) within a polygon raster (f.e. hexagons).

    Args:
        - gdf: geopandas dataframe containing trip data in h3 and h3_hex polygons
        - graph: nx multigraph object
        - crs: crs of gdf

    Returns:
        - gdf_out wich is gdf + 1 column: 'feature_beta_index'

    Last update: 01/08/21. By Felix.

    """

    # first convert the multigraph object to a dataframe
    gdf_nodes_4326, gdf_edges_4326 = ox.utils_graph.graph_to_gdfs(graph)
    gdf_nodes = gdf_nodes_4326.to_crs(gdf.crs).reset_index()

    # get number of edges per node
    dict_edges_per_nodes = ox.stats.streets_per_node(graph)
    # look for every value of 'hex_id' column in dict and write indexes in "edges per node"
    gdf_nodes["edges_per_node"] = gdf_nodes["osmid"].apply(lambda x: dict_edges_per_nodes.get(x))

    # save gdf for later
    gdf_out = gdf.copy()
    # drop geometry column from gdf and create new geometry column with hex geometries
    gdf_hex = gdf.drop(columns='geometry')
    gdf_hex = gpd.GeoDataFrame(gdf_hex, geometry=gdf_hex.h3_hexagon, crs=gdf.crs)

    # get sjoin between nodes and hex
    gdf_joined = gpd.sjoin(gdf_nodes, gdf_hex, op='within')
    # group by 'hex_id' (alternatively right index would work as well )
    dict_node_groups = gdf_joined.groupby('hex_id').groups
    # look for every value of 'hex_id' column in dict and write indexes in "nodes in hex"
    gdf_hex["nodes_in_hex"] = gdf_hex["hex_id"].apply(lambda x: dict_node_groups.get(x))

    # group by 'hex_id' (alternatively right index would work as well)
    df_out = gdf_joined.groupby('hex_id')['edges_per_node'].mean().to_frame('feature_beta_index').reset_index()
    # merge with gdf_out
    gdf_out = pd.merge(gdf_out, df_out, on='hex_id', how='left')

    print('Calculated beta index')
    return gdf_out



def ft_intersections_per_buffer(gdf,g,feature_name,od_col='origin',buffer_size=500):
    """
    Func feature_intersection_count_within_buffer resulted in allocation
    of count to wrong ids. This function allocates to right id.

    Returns: df['id',feature_name]
    """
    gdf_nodes, gdf_edges = ox.utils_graph.graph_to_gdfs(g,
                                                        nodes=True,
                                                        edges=True,
                                                        fill_edge_geometry=True)
    gdf_intersections = gdf_nodes.loc[gdf_nodes.street_count>1]
    
    #gdf_tmp = gdf[['id','id_'+od_col,'geometry']].copy(deep=True)
    gdf_tmp = gdf.copy(deep=True)
    
    geometry_type = _check_geometry_type(gdf_tmp)
    if geometry_type=='Point': 
        gdf_tmp['geometry'] = gdf_tmp.geometry.buffer(buffer_size)
    else: 
        gdf_tmp = gdf_tmp.drop_duplicates(subset='id_'+od_col).reset_index(drop=True)
        gdf_tmp['area'] = gdf_tmp.geometry.area

    gdf_sjoin = gpd.sjoin(gdf_tmp,gdf_intersections,how='inner')
    intersections_id_buffer = gdf_sjoin.groupby('id').size().to_frame().rename(columns={0:feature_name})
    
    df_tmp = pd.merge(gdf_tmp,intersections_id_buffer,on='id',how='left')
    df_tmp.loc[df_tmp[feature_name].isna(),feature_name] = 0.0

    if geometry_type=='Point': return df_tmp[['id','feature_name']]
    else: 
        # when calculated per polygon we average per polygon size 
        df_tmp[feature_name] = 1e4*df_tmp[feature_name]/df_tmp['area'] 
        df_out = pd.merge(gdf[['id','id_'+od_col,'geometry']],df_tmp[['id_'+od_col,feature_name]])
        return df_out[['id',feature_name]]
