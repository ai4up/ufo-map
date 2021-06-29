# -*- coding: utf-8 -*-
"""
Created on Tue Mar 24 09:52:35 2020

@author: miln
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt
from shapely.geometry import MultiPolygon
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.wkt import loads
import sys
import networkx as nx
import igraph as ig


def import_csv_w_wkt_to_gdf(path,crs,geometry_col='geometry'):
	'''
	Import a csv file with WKT geometry column into a GeoDataFrame

    Last modified: 12/09/2020. By: Nikola

    '''

	df = pd.read_csv(path)
	gdf = gpd.GeoDataFrame(df, 
						geometry=df[geometry_col].apply(wkt.loads),
						crs=crs)
	return(gdf)


def save_csv_wkt(gdf,path_out,geometry_col = 'geometry'):
	''' Save geodataframe to csv with wkt geometries.
	'''
	gdf[geometry_col] = gdf[geometry_col].apply(lambda x: x.wkt)
	gdf = pd.DataFrame(gdf).reset_index(drop=True)
	gdf.to_csv(path_out,index=False)



def get_all_paths(country_name,filename=''):
	''' Get the paths to all city files for a country and a given file group as a list.
	'''
	path_root_folder = '/p/projects/eubucco/data/2-database-city-level'
	path_paths_file = os.path.join(path_root_folder,country_name,"paths_"+country_name+".txt")
	with open('path_paths_file') as f:
	    paths = [line.rstrip() for line in f]
	paths = [f'{path}_{filename}.csv' for path in paths]


def arg_parser(flags):
  ''' function to lump together arg parser code for shorter text in main file.
  '''
  parser = argparse.ArgumentParser()
  for flag in flags:
      parser.add_argument(f'-{args}', type=int)
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

    for index,row in gdf.iterrows():

        if type(row.geometry) == MultiPolygon:
            geom_list[index] = multipoly_to_largest_poly(row.geometry)

        else:
            geom_list[index] = row.geometry
    
    return geom_list


def combined_multipoly_to_poly(gdf,
                            buffer_size):
    '''
    '''
    index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

    if len(index_multi)>0:

        print('Initial multipolygons: {}'.format(len(index_multi)))

        print('Trying to remove multipolygons with a small buffer...')

        gdf.geometry = gdf.geometry.buffer(buffer_size)

        index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

        print('Remaining multipolygons: {}'.format(len(index_multi)))

        if len(index_multi)>0:

            print('Removing remaining multipolygons by keeping the largest polygon...')

            gdf.geometry = GDF_multipoly_to_largest_poly(gdf)

            index_multi = [ind for ind, x in enumerate(gdf.geometry) if type(x) == MultiPolygon]

            print('Remaining multipolygons: {}'.format(len(index_multi)))

            return gdf

        else:

            return gdf

    else:

        print('No multipolygons.')

        return gdf


def import_trip_csv_to_gdf(path,crs):
    '''
    Import trip csv file from Inrix data with WKT geometry column into a GeoDataFrame

    Last modified: 25/02/2020. By: Felix

    '''
    
    df = pd.read_csv(path)
    
    # read in start location from csv
    gdf_origin = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.startloclon, df.startloclat),crs=crs)
    gdf_origin = gdf_origin[['tripid','tripdistancemeters','lengthoftrip','startdate','enddate','providertype','geometry'] ]
    # read in end location from csv
    gdf_dest = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.endloclon, df.endloclat),crs=crs)
    gdf_dest = gdf_dest[['tripid','tripdistancemeters','lengthoftrip','startdate','enddate','providertype','geometry'] ]
    
    return (gdf_origin, gdf_dest)


def get_data_within_part(part,points,boundary_parts):
    
        print(part)
        
        part_gdf = boundary_parts[boundary_parts['part'] == part][boundary_parts.has_buffer=='no_buffer']
        part_buffer_gdf = boundary_parts[boundary_parts['part'] == part][boundary_parts.has_buffer=='buffer']
  
        # spatial join layer and part
        df_in_part = gpd.sjoin(points, part_gdf, how='inner', op='within')

        # spatial join layer and part + buffer 
        df_in_part_plus_buffer = gpd.sjoin(points, part_buffer_gdf, how='inner', op='intersects')

        ## get buffered values only
        df_in_buffer_only = df_in_part_plus_buffer[~df_in_part_plus_buffer.index.isin(df_in_part.index)]

        # mark buffered buildings
        df_in_part['index_right'] = False
        df_in_buffer_only['index_right'] = True

        ## append buffered area marked
        df_in_part = df_in_part.append(df_in_buffer_only)

        # change buffer col name
        df_in_part.rename(columns={'index_right':'buffer_part'}, inplace=True)  
        
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

def get_shortest_dist(graph_ig,osmids, orig_osmid, dest_osmid, weight='length'):    
    # calculate shortest distance using igraph
    return graph_ig.shortest_paths(source=osmids.index(orig_osmid), target=osmids.index(dest_osmid), weights=weight)[0][0]
