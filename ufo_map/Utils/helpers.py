# -*- coding: utf-8 -*-
"""
Created on Tue Mar 24 09:52:35 2020

@author: miln
"""
import os
from datetime import date
import argparse
from pathlib import Path
from contextlib import contextmanager

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt
from shapely import wkb
from shapely.geometry import MultiPolygon, Polygon
from scipy.spatial import cKDTree
import networkx as nx
import igraph as ig


def write_stats(stats, duration, path, filename):
    '''
    Reports stats on the run.

    Returns: pd.DataFrame

    TODO: currently remains rather eubucco-specific, make more general
    '''
    h, s = divmod(duration, 3600)
    m, s = divmod(s, 60)
    stats['duration'] = '{} h {} m {} s'.format(h, m, round(s, 0))
    stats['date'] = date.today().strftime('%d/%m/%Y')
    df_stats = pd.DataFrame(stats, index=['0'])

    Path(path).mkdir(parents=True, exist_ok=True)
    df_stats.to_csv(os.path.join(path, filename + '.csv'), index=False)
    print(df_stats.iloc[0])


def look_up_google_maps(row):
    '''
    Get a point that can be copy pasted in Google Map to inspect a building
    from an arbitrary coordinate reference system.

    Expected input: gpd.GeoDataFrame with a single row, for example gdf.iloc[[0]]

    Returns: tuple (lat,long) in WGS84
    '''
    row = row.to_crs(4326).centroid.iloc[0]
    return(row.y, row.x)


def look_up_google_maps_gml(string, crs):
    '''
    Get a point that can be copy pasted in Google Map to inspect a building
    from an arbitrary coordinate reference system.

    Expected input:

    * string with 2d or 3d list of points representing a polygon (either a mesh or building element
      e.g. footprint in the format 'x1 y1 x2 y2 ...' or 'x1 y1 z1 x2 y2 z2 ...',
      which can be taken e.g. from a <gml:LinearRing> element

    * the initial coordinate reference system

    Returns: tuple (lat,long) in WGS84
    '''
    coords_list = [float(s) for s in string.split()]
    if divmod(len(coords_list), 3)[1] == 0:
        poly = Polygon(zip(coords_list[0::3], coords_list[1::3]))
    else:
        poly = Polygon(zip(coords_list[0::2], coords_list[1::2]))
    row = gpd.GeoDataFrame(geometry=gpd.GeoSeries(poly), crs=crs).to_crs(4326).centroid.iloc[0]

    return(row.y, row.x)


def import_csv_w_wkt_to_gdf(path, crs, geometry_col='geometry'):
    '''
    Import a csv file with WKT geometry column into a GeoDataFrame

    Last modified: 12/09/2020. By: Nikola

    '''

    df = pd.read_csv(path)
    gdf = gpd.GeoDataFrame(df,
                           geometry=df[geometry_col].apply(wkt.loads),
                           crs=crs)
    return(gdf)


def save_csv_wkt(gdf, path_out, geometry_col='geometry'):
    ''' Save geodataframe to csv with wkt geometries.
    '''
    gdf[geometry_col] = gdf[geometry_col].apply(lambda x: x.wkt)
    gdf = pd.DataFrame(gdf).reset_index(drop=True)
    gdf.to_csv(path_out, index=False)


def get_all_paths(
        country_name,
        filename='',
        path_root_folder='/p/projects/eubucco/data/2-database-city-level',
        left_over=False,
        ua_mode=False):
    ''' Get the paths to all city files for a country and a given file group as a list.
    '''

    # added case for mixed osm-gov countries
    if filename == 'osm':
        path_paths_file = os.path.join(path_root_folder, 'osm_paths', "paths_" + country_name + "_osm.txt")
    else:
        path_paths_file = os.path.join(path_root_folder, country_name, "paths_" + country_name + ".txt")

    if left_over:
        path_paths_file = os.path.join(path_root_folder, country_name, "paths_failed_" +
                                       left_over + '_' + country_name + ".txt")
    if ua_mode:
        path_paths_file = os.path.join(path_root_folder, country_name, "paths_ua_" + country_name + ".txt")

    with open(path_paths_file) as f:
        paths = [line.rstrip() for line in f]

    if filename == '':
        return(paths)
    elif filename == 'osm':
        return(paths)
    else:
        return([f'{path}_{filename}.csv' for path in paths])


def arg_parser(flags):
    ''' function to lump together arg parser code for shorter text in main file.
    '''
    parser = argparse.ArgumentParser()
    for flag in flags:
        if isinstance(flag, tuple):
            parser.add_argument(f'-{flag[0]}', type=flag[1])
        else:
            parser.add_argument(f'-{flag}', type=int)

    args = parser.parse_args()
    return(args)


def multipoly_to_largest_poly(mutlipoly):
    '''
    Turn a multipolygon into the largest largest available polygon.

    Last modified: 26/01/2021. By: Nikola

    '''
    largest_poly_index = np.argmax([poly.area for poly in mutlipoly])
    largest_poly = mutlipoly[largest_poly_index]

    return largest_poly


def GDF_multipoly_to_largest_poly(gdf):
    '''
    Turn a multipolygon into the largest largest available polygon.

    Last modified: 27/01/2021. By: Nikola

    '''

    geom_list = [None] * len(gdf)

    for index, row in gdf.reset_index().iterrows():

        if isinstance(row.geometry, MultiPolygon):
            geom_list[index] = multipoly_to_largest_poly(row.geometry)

        else:
            geom_list[index] = row.geometry

    return geom_list


def get_indexes_multipoly(gdf):
    return([ind for ind, x in enumerate(gdf.geometry) if isinstance(x, MultiPolygon)])


def combined_multipoly_to_poly(gdf,
                               buffer_size=0.01,
                               verbose=False,
                               count=True):
    '''
    '''
    index_multi = get_indexes_multipoly(gdf)

    if len(index_multi) > 0:
        # removing multipoly with buffer
        len_start = len(index_multi)
        gdf.geometry = gdf.geometry.buffer(buffer_size)
        index_multi = get_indexes_multipoly(gdf)

        if len(index_multi) > 0:
            # take the largest building only
            gdf.geometry = GDF_multipoly_to_largest_poly(gdf)
            index_multi = get_indexes_multipoly(gdf)
            if verbose:
                print('Removed {} multipolygons out of {} buildings.'.format(len_start, len(gdf)))

            if len(index_multi) > 0:
                if verbose:
                    print('Remaining multipolygons: {}'.format(len(index_multi)))

            if count:
                return(gdf, len_start)
            else:
                return gdf

        else:
            if count:
                return(gdf, len_start)
            else:
                return gdf
    else:
        if verbose:
            print('No multipolygons.')
        if count:
            return(gdf, 0)
        else:
            return gdf


def drop_z(gdf):
    '''
    Removes the Z coordinates in all geometries.
    '''
    if any(['POLYGON Z' or 'POLYGON S' in geom.wkt for geom in gdf.geometry]):
        gdf['geometry'] = [wkb.loads(wkb.dumps(geom, output_dimension=2)) for geom in gdf['geometry']]

    return(gdf)


def import_trip_csv_to_gdf(path, crs):
    '''
    Import trip csv file from Inrix data with WKT geometry column into a GeoDataFrame

    Last modified: 25/02/2020. By: Felix

    '''

    df = pd.read_csv(path)

    # read in start location from csv
    gdf_origin = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.startloclon, df.startloclat), crs=crs)
    gdf_origin = gdf_origin[['tripid', 'tripdistancemeters',
                             'lengthoftrip', 'startdate', 'enddate', 'providertype', 'geometry']]
    # read in end location from csv
    gdf_dest = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.endloclon, df.endloclat), crs=crs)
    gdf_dest = gdf_dest[['tripid', 'tripdistancemeters', 'lengthoftrip',
                         'startdate', 'enddate', 'providertype', 'geometry']]

    return (gdf_origin, gdf_dest)


def get_data_within_part(part, points, boundary_parts):

    print(part)

    part_gdf = boundary_parts[boundary_parts['part'] == part][boundary_parts.has_buffer == 'no_buffer']
    part_buffer_gdf = boundary_parts[boundary_parts['part'] == part][boundary_parts.has_buffer == 'buffer']

    # spatial join layer and part
    df_in_part = gpd.sjoin(points, part_gdf, how='inner', op='within')

    # spatial join layer and part + buffer
    df_in_part_plus_buffer = gpd.sjoin(points, part_buffer_gdf, how='inner', op='intersects')

    # get buffered values only
    df_in_buffer_only = df_in_part_plus_buffer[~df_in_part_plus_buffer.index.isin(df_in_part.index)]

    # mark buffered buildings
    df_in_part['index_right'] = False
    df_in_buffer_only['index_right'] = True

    # append buffered area marked
    df_in_part = df_in_part.append(df_in_buffer_only)

    # change buffer col name
    df_in_part.rename(columns={'index_right': 'buffer_part'}, inplace=True)

    return df_in_part


def nearest_neighbour(gdA, gdB):
    """
    Function to calculate for every entry in gdA, the nearest neighbour
    among the points in gdB

    taken from https://gis.stackexchange.com/questions/222315/geopandas-find-nearest-point-in-other-dataframe

    Args:
    - gdA: geodataframe with points in geometry column
    - gdB: geodataframe with points in geometry column

    Returns:
        - gdf_out: geodataframe wich is gdA + 2 columns containing
        the name of the closest point and the distance

    Last update: 13/04/21. By Felix.
    """
    nA = np.array(list(gdA.geometry.apply(lambda x: (x.x, x.y))))
    nB = np.array(list(gdB.geometry.apply(lambda x: (x.x, x.y))))
    btree = cKDTree(nB)
    dist, idx = btree.query(nA, k=1)
    gdB_nearest = gdB.iloc[idx].drop(columns="geometry").reset_index(drop=False)
    gdf_out = pd.concat(
        [
            gdA.reset_index(drop=True),
            gdB_nearest,
            pd.Series(dist, name='distance')
        ],
        axis=1)

    return gdf_out


def convert_to_igraph(graph_nx, weight='length'):
    """
    Function to convert networkx (or osmnx) graph element to igraph

    Args:
    - graph_nx (networkx graph): multigraph object
    - weight (string) = 'length': attribute of the graph

    Returns:
        - G_ig (igraph element): converted graph
        - osmids (list): list with osm IDs of nodes

    Last update: 29/06/21. By Felix.
    """
    # retrieve list of osmid id's and relabel
    G_nx = graph_nx
    osmids = list(G_nx.nodes)
    G_nx = nx.relabel.convert_node_labels_to_integers(G_nx)
    # give each node its original osmid as attribute since we relabeled them
    osmid_values = {k: v for k, v in zip(G_nx.nodes, osmids)}
    nx.set_node_attributes(G_nx, osmid_values, "osmid")
    # convert networkx graph to igraph
    G_ig = ig.Graph(directed=True)
    G_ig.add_vertices(G_nx.nodes)
    G_ig.add_edges(G_nx.edges())
    G_ig.vs["osmid"] = osmids
    G_ig.es[weight] = list(nx.get_edge_attributes(G_nx, weight).values())
    return G_ig, osmids


def get_shortest_dist(graph_ig, osmids, orig_osmid, dest_osmid, weight='length'):
    # calculate shortest distance using igraph
    return graph_ig.shortest_paths(
        source=osmids.index(orig_osmid),
        target=osmids.index(dest_osmid),
        weights=weight)[0][0]


def flatten_list(ls):
    """
    helper function that flattes a list of list of lists and removes duplicates
    """
    list_lv2 = [item for sublist in ls for item in sublist]
    list_flat = [item for sublist in list_lv2 for item in sublist]
    return list(set(list_flat))


@contextmanager
def chdir(path):
    old_pwd = os.getcwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(old_pwd)