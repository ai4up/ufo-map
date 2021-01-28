# -*- coding: utf-8 -*-
"""
Created on Tue Mar 24 09:52:35 2020

@author: miln
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely import wkt
from functools import singledispatch
from operator import itemgetter
from typing import TypeVar

from shapely.ops import polygonize, split

from shapely.geometry import Polygon
from shapely.geometry.base import (BaseGeometry,
                                   BaseMultipartGeometry)

## IMPORT UTILS -----------------------

def import_csv_w_wkt_to_gdf(path, crs):
    """ Imports a CSV file and load geometries into a GeoDataFrame
    """

    df = pd.read_csv(path)
    df.geometry = df.geometry.apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry=df.geometry, crs=crs)
    return gdf

## DATA PARSING UTILS-----------------

Geometry = TypeVar('Geometry', bound=BaseGeometry)

@singledispatch
def drop_z(geometry: Geometry) -> Geometry:
    """
    Removes Z-coordinate from a geometry object.
    Won't be necessary after it will be implemented in Shapely:
    https://github.com/Toblerity/Shapely/issues/709
    """

    if geometry.is_empty:
        return geometry
    geometry_type = type(geometry)
    xy_coordinates = map(itemgetter(0, 1), geometry.coords)
    return geometry_type(list(xy_coordinates))


@drop_z.register
def _(geometry: BaseMultipartGeometry):
    geometry_type = type(geometry)
    return geometry_type(list(map(drop_z, geometry.geoms)))


@drop_z.register
def _(geometry: Polygon):
    if geometry.is_empty:
        return geometry
    new_exterior = drop_z(geometry.exterior)
    new_interiors = list(map(drop_z, geometry.interiors))
    return Polygon(new_exterior, new_interiors)


def get_city_boundaries(df_buildings, crs=None, buffer_size=None, gdf=False):
    """
    Returns a GeoSeries or a GeoDataFrame with the boundaries of city, based on the convex hull
    around a building geometries of a city, and with a potential extra buffer.
    """

    # Draw a convex hull around the unary union of the centroid of all buildings
    hull = df_buildings.geometry.centroid.unary_union.convex_hull

    # Draw a 1-km buffer around the hull 
    buffer = hull.buffer(buffer_size)

    # Store the buffer into a GeoDataFrame
    if gdf==True:
        buffer_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(buffer))

    if gdf==False:
        buffer_gdf = gpd.GeoSeries(buffer)

    # Set the projection
    buffer_gdf.crs = crs

    return buffer_gdf 



def rm_duplicates_osm_streets(df_streets):
    """
    Removes duplicated streets like two ways streets.
    Returns a cleaned GeoDataFrame with street linestrings.
    """

    # round length value to one decimal (1 cm) 
    df_streets = df_streets.round({'length': 2})
    
    # remove duplicates based on osmid + length
    df_streets = df_streets.drop_duplicates(['osmid','length'],keep= 'first').reset_index(drop=True)

    # spatial index
    streets_spatial_index = df_streets.sindex
    
    #list index to remove
    index_to_remove = []

    # retrieve with spatial index buffer following the street shape (intersects)
    for index,row in df_streets.iterrows():

        buffer = row.geometry.buffer(1)

        possible_matches_index = list(streets_spatial_index.intersection(buffer.bounds))
        possible_matches = df_streets.loc[possible_matches_index] 
        precise_matches = possible_matches[possible_matches.intersects(buffer)]

        # filter by length
        precise_matches = precise_matches[precise_matches.length > 0.95 * precise_matches.loc[index].length]
        try:
            precise_matches = precise_matches[precise_matches.length < 1.05 * precise_matches.loc[index].length]
        except:
            print('index {} being weird'.format(index))
            continue

        # refine by overlap
        for index2,row2 in precise_matches.drop(index).iterrows():

            overlap = precise_matches.loc[index].geometry.intersection(precise_matches.loc[index2].geometry).length

            if 0.95 * precise_matches.loc[index].length < overlap < 1.05 * precise_matches.loc[index].length:
                
                if index2 not in index_to_remove:
                    
                    index_to_remove.append(index)

            if 0.05 * precise_matches.loc[index].length < overlap < 0.95 * precise_matches.loc[index].length or overlap > 1.05 * precise_matches.loc[index].length:

                print('Street {} has a suspect overlap of {}%.'.format(index,overlap/precise_matches.loc[index].length))

    print('Streets removed:')
    print(index_to_remove)
    df_streets = df_streets.drop(index_to_remove)

    return df_streets


def block_street_based(df_streets, verbose=False):
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

            # however, if *several* crossings
            if len(precise_matches) > 1:

                if verbose:
                    print('For street {}, there were {} crossings.'.format(index,len(precise_matches)))

                # get a temporary list for the splits
                good_lines_tmp = gpd.GeoSeries()

                # for all crossing lines
                for _, row_pm in precise_matches.iterrows():

                    # if it is the first cut...
                    if good_lines_tmp.empty:
                        
                        # split the original street
                        line_split = split(row.geometry, row_pm.geometry)
                        
                        #print(line_split)
                        #print(len(line_split))

                        # for all splits
                        for line_num_sp, line_sp in enumerate(line_split):
                            
                            #print(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))
                
                            # append split to the tmp split list, changing the index
                            good_lines_tmp = good_lines_tmp.append(gpd.GeoSeries(line_sp, index = [index * 10 + line_num_sp]))
                
                    # if it is not the first cut
                    else:

                        #print(good_lines_tmp)
                        
                        # iterate over the cuts done already *by index*
                        for index_glt, line_glt in good_lines_tmp.items(): 
                            
                            #print(index_glt)

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

                if verbose:
                    print(list(good_lines_tmp.index))

                # add all the splits to the main list
                good_lines = good_lines.append(good_lines_tmp)

    if verbose:
        print('Splitted:\n', bad_index)

    df_blocks = gpd.GeoDataFrame(geometry=list(polygonize(good_lines.geometry)))

    return df_blocks

##############################################
##############################################
## THESE ARE FUNCTIONS COPY-PASTED FROM 
## THE LIBRARY MOMEPY, BECAUSE THEY 
## REQUIRE INTERNET ACCESS, MOMEPY CANNOT
## BE USED DIRECTLY ON THE CLUSTER.
## FOR THE RELEASE, CREATE A COPY WITH 
## ORIGINALS FUNCTION.
##
##
##              (START MOMEPY)
##
##############################################
##############################################
import networkx as nx
import math
from shapely.geometry import LineString, Point

def momepy_mean_nodes(G, attr):
    """
    Calculates mean value of nodes attr for each edge.
    """
    for u, v, k in G.edges(keys=True):
        mean = (G.nodes[u][attr] + G.nodes[v][attr]) / 2

        G[u][v][k][attr] = mean



def momepy_gdf_to_nx(gdf_network, approach="primal", length="mm_len"):
    """
    Convert LineString GeoDataFrame to networkx.MultiGraph
    Parameters
    ----------
    gdf_network : GeoDataFrame
        GeoDataFrame containing objects to convert
    approach : str, default 'primal'
        Decide wheter genereate 'primal' or 'dual' graph.
    length : str, default mm_len
        name of attribute of segment length (geographical) which will be saved to graph
    Returns
    -------
    networkx.Graph
        Graph
    """
    gdf_network = gdf_network.copy()
    if "key" in gdf_network.columns:
        gdf_network.rename(columns={"key": "__key"}, inplace=True)
    # generate graph from GeoDataFrame of LineStrings
    net = nx.MultiGraph()
    net.graph["crs"] = gdf_network.crs
    gdf_network[length] = gdf_network.geometry.length
    fields = list(gdf_network.columns)

    if approach == "primal":
        _generate_primal(net, gdf_network, fields)

    # elif approach == "dual":
    #     _generate_dual(net, gdf_network, fields)

    else:
        raise ValueError(
            "Approach {} is not supported. Use 'primal' or 'dual'.".format(approach)
        )

    return net

def _generate_primal(G, gdf_network, fields):
    """
    Generate primal graph.
    Helper for gdf_to_nx.
    """
    G.graph["approach"] = "primal"
    key = 0
    for index, row in gdf_network.iterrows():
        first = row.geometry.coords[0]
        last = row.geometry.coords[-1]

        data = [row[f] for f in fields]
        attributes = dict(zip(fields, data))
        G.add_edge(first, last, key=key, **attributes)
        key += 1




def momepy_nx_to_gdf(net, points=True, lines=True, spatial_weights=False, nodeID="nodeID"):
    """
    Convert networkx.Graph to LineString GeoDataFrame and Point GeoDataFrame
    Parameters
    ----------
    net : networkx.Graph
        networkx.Graph
    points : bool
        export point-based gdf representing intersections
    lines : bool
        export line-based gdf representing streets
    spatial_weights : bool
        export libpysal spatial weights for nodes
    nodeID : str
        name of node ID column to be generated
    Returns
    -------
    GeoDataFrame
        Selected gdf or tuple of both gdf or tuple of gdfs and weights
    """
    # generate nodes and edges geodataframes from graph
    if "approach" in net.graph.keys():
        if net.graph["approach"] == "primal":
            nid = 1
            for n in net:
                net.nodes[n][nodeID] = nid
                nid += 1
            return _primal_to_gdf(
                net,
                points=points,
                lines=lines,
                spatial_weights=spatial_weights,
                nodeID=nodeID,
            )
        # if net.graph["approach"] == "dual":
        #     return _dual_to_gdf(net)
        # raise ValueError(
        #     "Approach {} is not supported. Use 'primal' or 'dual'.".format(
        #         net.graph["approach"]
            # )
        # )

    import warnings

    warnings.warn("Approach is not set. Defaulting to 'primal'.")

    nid = 1
    for n in net:
        net.nodes[n][nodeID] = nid
        nid += 1
    return _primal_to_gdf(
        net, points=points, lines=lines, spatial_weights=spatial_weights, nodeID=nodeID
    )



def _primal_to_gdf(net, points, lines, spatial_weights, nodeID):
    """
    Generate gdf(s) from primal network.
    Helper for nx_to_gdf.
    """
    if points is True:
        gdf_nodes = _points_to_gdf(net, spatial_weights)

        if spatial_weights is True:
            W = libpysal.weights.W.from_networkx(net)
            W.transform = "b"

    if lines is True:
        gdf_edges = _lines_to_gdf(net, lines, points, nodeID)

    if points is True and lines is True:
        if spatial_weights is True:
            return gdf_nodes, gdf_edges, W
        return gdf_nodes, gdf_edges
    if points is True and lines is False:
        if spatial_weights is True:
            return gdf_nodes, W
        return gdf_nodes
    return gdf_edges

def _points_to_gdf(net, spatial_weights):
    """
    Generate point gdf from nodes.
    Helper for nx_to_gdf.
    """
    node_xy, node_data = zip(*net.nodes(data=True))
    if isinstance(node_xy[0], int) and "x" in node_data[0].keys():
        geometry = [Point(data["x"], data["y"]) for data in node_data]  # osmnx graph
    else:
        geometry = [Point(*p) for p in node_xy]
    gdf_nodes = gpd.GeoDataFrame(list(node_data), geometry=geometry)
    if "crs" in net.graph.keys():
        gdf_nodes.crs = net.graph["crs"]
    return gdf_nodes


def _lines_to_gdf(net, lines, points, nodeID):
    """
    Generate linestring gdf from edges.
    Helper for nx_to_gdf.
    """
    starts, ends, edge_data = zip(*net.edges(data=True))
    if lines is True:
        node_start = []
        node_end = []
        for s in starts:
            node_start.append(net.nodes[s][nodeID])
        for e in ends:
            node_end.append(net.nodes[e][nodeID])
    gdf_edges = gpd.GeoDataFrame(list(edge_data))
    if points is True:
        gdf_edges["node_start"] = node_start
        gdf_edges["node_end"] = node_end
    if "crs" in net.graph.keys():
        gdf_edges.crs = net.graph["crs"]
    return gdf_edges


def _closeness_centrality(G, u=None, length=None, wf_improved=True, len_graph=None):
    r"""Compute closeness centrality for nodes. Slight adaptation of networkx
    `closeness_centrality` to allow normalisation for local closeness.
    Adapted script used in networkx.
    Closeness centrality [1]_ of a node `u` is the reciprocal of the
    average shortest path distance to `u` over all `n-1` reachable nodes.
    .. math::
        C(u) = \frac{n - 1}{\sum_{v=1}^{n-1} d(v, u)},
    where `d(v, u)` is the shortest-path distance between `v` and `u`,
    and `n` is the number of nodes that can reach `u`. Notice that the
    closeness distance function computes the incoming distance to `u`
    for directed graphs. To use outward distance, act on `G.reverse()`.
    Notice that higher values of closeness indicate higher centrality.
    Wasserman and Faust propose an improved formula for graphs with
    more than one connected component. The result is "a ratio of the
    fraction of actors in the group who are reachable, to the average
    distance" from the reachable actors [2]_. You might think this
    scale factor is inverted but it is not. As is, nodes from small
    components receive a smaller closeness value. Letting `N` denote
    the number of nodes in the graph,
    .. math::
        C_{WF}(u) = \frac{n-1}{N-1} \frac{n - 1}{\sum_{v=1}^{n-1} d(v, u)},
    Parameters
    ----------
    G : graph
      A NetworkX graph
    u : node, optional
      Return only the value for node u
    distance : edge attribute key, optional (default=None)
      Use the specified edge attribute as the edge distance in shortest
      path calculations
    len_graph : int
        length of complete graph
    Returns
    -------
    nodes : dictionary
      Dictionary of nodes with closeness centrality as the value.
    References
    ----------
    .. [1] Linton C. Freeman: Centrality in networks: I.
       Conceptual clarification. Social Networks 1:215-239, 1979.
       http://leonidzhukov.ru/hse/2013/socialnetworks/papers/freeman79-centrality.pdf
    .. [2] pg. 201 of Wasserman, S. and Faust, K.,
       Social Network Analysis: Methods and Applications, 1994,
       Cambridge University Press.
    """

    if length is not None:
        import functools

        # use Dijkstra's algorithm with specified attribute as edge weight
        path_length = functools.partial(
            nx.single_source_dijkstra_path_length, weight=length
        )
    else:
        path_length = nx.single_source_shortest_path_length

    nodes = [u]
    closeness_centrality = {}
    for n in nodes:
        sp = dict(path_length(G, n))
        totsp = sum(sp.values())
        if totsp > 0.0 and len(G) > 1:
            closeness_centrality[n] = (len(sp) - 1.0) / totsp
            # normalize to number of nodes-1 in connected part
            s = (len(sp) - 1.0) / (len_graph - 1)
            closeness_centrality[n] *= s
        else:
            closeness_centrality[n] = 0.0

    return closeness_centrality[u]
    

def momepy_betweenness_centrality(
    graph, name="betweenness", mode="nodes", weight="mm_len", endpoints=True, **kwargs
):
    """
    Calculates the shortest-path betweenness centrality for nodes.
    Wrapper around ``networkx.betweenness_centrality`` or ``networkx.edge_betweenness_centrality``.
    Betweenness centrality of a node `v` is the sum of the
    fraction of all-pairs shortest paths that pass through `v`
    .. math::
       c_B(v) =\\sum_{s,t \\in V} \\frac{\\sigma(s, t|v)}{\\sigma(s, t)}
    where `V` is the set of nodes, :math:`\\sigma(s, t)` is the number of
    shortest :math:`(s, t)`-paths,  and :math:`\\sigma(s, t|v)` is the number of
    those paths  passing through some  node `v` other than `s, t`.
    If `s = t`, :math:`\\sigma(s, t) = 1`, and if `v` in `{s, t}``,
    :math:`\\sigma(s, t|v) = 0`.
    Betweenness centrality of an edge `e` is the sum of the
    fraction of all-pairs shortest paths that pass through `e`
    .. math::
       c_B(e) =\\sum_{s,t \\in V} \\frac{\\sigma(s, t|e)}{\\sigma(s, t)}
    where `V` is the set of nodes, :math:`\\sigma(s, t)` is the number of
    shortest :math:`(s, t)`-paths, and :math:`\\sigma(s, t|e)` is the number of
    those paths passing through edge `e`.
    Parameters
    ----------
    graph : networkx.Graph
        Graph representing street network.
        Ideally genereated from GeoDataFrame using :py:func:`momepy.gdf_to_nx`
    name : str, optional
        calculated attribute name
    mode : str, default 'nodes'
        mode of betweenness calculation. 'node' for node-based, 'edges' for edge-based
    weight : str (default 'mm_len')
        attribute holding the weight of edge (e.g. length, angle)
    **kwargs
        kwargs for ``networkx.betweenness_centrality`` or ``networkx.edge_betweenness_centrality``
    Returns
    -------
    Graph
        networkx.Graph
    References
    ----------
    Porta S, Crucitti P and Latora V (2006) The network analysis of urban streets: A primal approach.
    Environment and Planning B: Planning and Design 33(5): 705–725.
    Examples
    --------
    >>> network_graph = mm.betweenness_centrality(network_graph)
    Note
    ----
    In case of angular betweenness, implementation is based on "Tasos Implementation".
    """
    netx = graph.copy()

    # has to be Graph not MultiGraph as MG is not supported by networkx2.4
    G = nx.Graph()
    for u, v, k, data in netx.edges(data=True, keys=True):
        if G.has_edge(u, v):
            if G[u][v][weight] > netx[u][v][k][weight]:
                nx.set_edge_attributes(G, {(u, v): data})
        else:
            G.add_edge(u, v, **data)

    if mode == "nodes":
        vals = nx.betweenness_centrality(
            G, weight=weight, endpoints=endpoints, **kwargs
        )
        nx.set_node_attributes(netx, vals, name)
    elif mode == "edges":
        vals = nx.edge_betweenness_centrality(G, weight=weight, **kwargs)
        for u, v, k in netx.edges(keys=True):
            try:
                val = vals[u, v]
            except KeyError:
                val = vals[v, u]
            netx[u][v][k][name] = val
    else:
        raise ValueError(
            "Mode {} is not supported. Use 'nodes' or 'edges'.".format(mode)
        )

    return netx



def momepy_closeness_centrality(graph, name="closeness", weight="mm_len", **kwargs):
    """
    Calculates the closeness centrality for nodes.
    Wrapper around ``networkx.closeness_centrality``.
    Closeness centrality of a node `u` is the reciprocal of the
    average shortest path distance to `u` over all `n-1` nodes within reachable nodes.
    .. math::
        C(u) = \\frac{n - 1}{\\sum_{v=1}^{n-1} d(v, u)},
    where `d(v, u)` is the shortest-path distance between `v` and `u`,
    and `n` is the number of nodes that can reach `u`.
    Parameters
    ----------
    graph : networkx.Graph
        Graph representing street network.
        Ideally genereated from GeoDataFrame using :py:func:`momepy.gdf_to_nx`
    name : str, optional
        calculated attribute name
    weight : str (default 'mm_len')
        attribute holding the weight of edge (e.g. length, angle)
    **kwargs
        kwargs for ``networkx.closeness_centrality``
    Returns
    -------
    Graph
        networkx.Graph
    Examples
    --------
    >>> network_graph = mm.closeness_centrality(network_graph)
    """
    netx = graph.copy()

    vals = nx.closeness_centrality(netx, distance=weight, **kwargs)
    nx.set_node_attributes(netx, vals, name)

    return netx


def momepy_local_closeness_centrality(
    graph, radius=5, name="closeness", distance=None, weight=None
):
    """
    Calculates local closeness for each node based on the defined distance.
    Subgraph is generated around each node within set radius. If distance=None,
    radius will define topological distance, otherwise it uses values in distance
    attribute. Based on networkx.closeness_centrality.
    Local closeness centrality of a node `u` is the reciprocal of the
    average shortest path distance to `u` over all `n-1` nodes within subgraph.
    .. math::
        C(u) = \\frac{n - 1}{\\sum_{v=1}^{n-1} d(v, u)},
    where `d(v, u)` is the shortest-path distance between `v` and `u`,
    and `n` is the number of nodes that can reach `u`.
    Parameters
    ----------
    graph : networkx.Graph
        Graph representing street network.
        Ideally genereated from GeoDataFrame using :py:func:`momepy.gdf_to_nx`
    radius: int
        number of topological steps defining the extent of subgraph
    name : str, optional
        calculated attribute name
    distance : str, optional
        Use specified edge data key as distance.
        For example, setting distance=’weight’ will use the edge weight to
        measure the distance from the node n during ego_graph generation.
    weight : str, optional
      Use the specified edge attribute as the edge distance in shortest
      path calculations in closeness centrality algorithm
    Returns
    -------
    Graph
        networkx.Graph
    References
    ----------
    Porta S, Crucitti P and Latora V (2006) The network analysis of urban streets: A primal approach.
    Environment and Planning B: Planning and Design 33(5): 705–725.
    Examples
    --------
    >>> network_graph = mm.local_closeness_centrality(network_graph, radius=400, distance='edge_length')
    """
    netx = graph.copy()
    lengraph = len(netx)
    for n in netx:
        sub = nx.ego_graph(
            netx, n, radius=radius, distance=distance
        )  # define subgraph of steps=radius
        netx.nodes[n][name] = _closeness_centrality(
            sub, n, length=weight, len_graph=lengraph
        )

    return netx


class momepy_StreetProfile:
    """
    Calculates the street profile characters.
    Returns a dictionary with widths, standard deviation of width, openness, heights,
    standard deviation of height and ratio height/width. Algorithm generates perpendicular
    lines to `right` dataframe features every `distance` and measures values on intersection
    with features of `left.` If no feature is reached within
    `tick_length` its value is set as width (being theoretical maximum).
    .. math::
        \\
    Parameters
    ----------
    left : GeoDataFrame
        GeoDataFrame containing streets to analyse
    right : GeoDataFrame
        GeoDataFrame containing buildings along the streets (only Polygon geometry type is supported)
    heights: str, list, np.array, pd.Series (default None)
        the name of the buildings dataframe column, np.array, or pd.Series where is stored building height. If set to None,
        height and ratio height/width will not be calculated.
    distance : int (default 10)
        distance between perpendicular ticks
    tick_length : int (default 50)
        lenght of ticks
    Attributes
    ----------
    w : Series
        Series containing street profile width values
    wd : Series
        Series containing street profile standard deviation values
    o : Series
        Series containing street profile openness values
    h : Series
        Series containing street profile heights values. Returned only when heights is set.
    hd : Series
        Series containing street profile heights standard deviation values. Returned only when heights is set.
    p : Series
        Series containing street profile height/width ratio values. Returned only when heights is set.
    left : GeoDataFrame
        original left GeoDataFrame
    right : GeoDataFrame
        original right GeoDataFrame
    distance : int
        distance between perpendicular ticks
    tick_length : int
        lenght of ticks
    heights : GeoDataFrame
        Series containing used height values
    References
    ----------
    Oliveira V (2013) Morpho: a methodology for assessing urban form. Urban Morphology 17(1): 21–33.
    Araldi A and Fusco G (2017) Decomposing and Recomposing Urban Fabric: The City from the Pedestrian
    Point of View. In: Gervasi O, Murgante B, Misra S, et al. (eds), Computational Science and Its
    Applications – ICCSA 2017, Lecture Notes in Computer Science, Cham: Springer International
    Publishing, pp. 365–376. Available from: http://link.springer.com/10.1007/978-3-319-62407-5.
    Examples
    --------
    >>> street_profile = momepy.StreetProfile(streets_df, buildings_df, heights='height')
    100%|██████████| 33/33 [00:02<00:00, 15.66it/s]
    >>> streets_df['width'] = street_profile.w
    >>> streets_df['deviations'] = street_profile.wd
    """

    def __init__(self, left, right, heights=None, distance=10, tick_length=50):
        self.left = left
        self.right = right
        self.distance = distance
        self.tick_length = tick_length

        if heights is not None:
            if not isinstance(heights, str):
                right = right.copy()
                right["mm_h"] = heights
                heights = "mm_h"

            self.heights = right[heights]

        sindex = right.sindex

        results_list = []
        deviations_list = []
        heights_list = []
        heights_deviations_list = []
        openness_list = []

        for idx, row in left.iterrows():
            # list to hold all the point coords
            list_points = []
            # set the current distance to place the point
            current_dist = distance
            # make shapely MultiLineString object
            shapely_line = row.geometry
            # get the total length of the line
            line_length = shapely_line.length
            # append the starting coordinate to the list
            list_points.append(Point(list(shapely_line.coords)[0]))
            # https://nathanw.net/2012/08/05/generating-chainage-distance-nodes-in-qgis/
            # while the current cumulative distance is less than the total length of the line
            while current_dist < line_length:
                # use interpolate and increase the current distance
                list_points.append(shapely_line.interpolate(current_dist))
                current_dist += distance
            # append end coordinate to the list
            list_points.append(Point(list(shapely_line.coords)[-1]))

            ticks = []
            for num, pt in enumerate(list_points, 1):
                # start chainage 0
                if num == 1:
                    angle = self._getAngle(pt, list_points[num])
                    line_end_1 = self._getPoint1(pt, angle, tick_length / 2)
                    angle = self._getAngle(line_end_1, pt)
                    line_end_2 = self._getPoint2(line_end_1, angle, tick_length)
                    tick1 = LineString([(line_end_1.x, line_end_1.y), (pt.x, pt.y)])
                    tick2 = LineString([(line_end_2.x, line_end_2.y), (pt.x, pt.y)])
                    ticks.append([tick1, tick2])

                # everything in between
                if num < len(list_points) - 1:
                    angle = self._getAngle(pt, list_points[num])
                    line_end_1 = self._getPoint1(
                        list_points[num], angle, tick_length / 2
                    )
                    angle = self._getAngle(line_end_1, list_points[num])
                    line_end_2 = self._getPoint2(line_end_1, angle, tick_length)
                    tick1 = LineString(
                        [
                            (line_end_1.x, line_end_1.y),
                            (list_points[num].x, list_points[num].y),
                        ]
                    )
                    tick2 = LineString(
                        [
                            (line_end_2.x, line_end_2.y),
                            (list_points[num].x, list_points[num].y),
                        ]
                    )
                    ticks.append([tick1, tick2])

                # end chainage
                if num == len(list_points):
                    angle = self._getAngle(list_points[num - 2], pt)
                    line_end_1 = self._getPoint1(pt, angle, tick_length / 2)
                    angle = self._getAngle(line_end_1, pt)
                    line_end_2 = self._getPoint2(line_end_1, angle, tick_length)
                    tick1 = LineString([(line_end_1.x, line_end_1.y), (pt.x, pt.y)])
                    tick2 = LineString([(line_end_2.x, line_end_2.y), (pt.x, pt.y)])
                    ticks.append([tick1, tick2])
            # widths = []
            m_heights = []
            lefts = []
            rights = []
            for duo in ticks:

                for ix, tick in enumerate(duo):
                    possible_intersections_index = list(
                        sindex.intersection(tick.bounds)
                    )
                    possible_intersections = right.iloc[possible_intersections_index]
                    real_intersections = possible_intersections.intersects(tick)
                    get_height = right.loc[list(real_intersections.index)]
                    possible_int = get_height.exterior.intersection(tick)

                    if not possible_int.is_empty.all():
                        true_int = []
                        for one in list(possible_int.index):
                            if possible_int[one].type == "Point":
                                true_int.append(possible_int[one])
                            elif possible_int[one].type == "MultiPoint":
                                for p in possible_int[one]:
                                    true_int.append(p)

                        if len(true_int) > 1:
                            distances = []
                            ix = 0
                            for p in true_int:
                                dist = p.distance(Point(tick.coords[-1]))
                                distances.append(dist)
                                ix = ix + 1
                            minimal = min(distances)
                            if ix == 0:
                                lefts.append(minimal)
                            else:
                                rights.append(minimal)
                        else:
                            if ix == 0:
                                lefts.append(
                                    true_int[0].distance(Point(tick.coords[-1]))
                                )
                            else:
                                rights.append(
                                    true_int[0].distance(Point(tick.coords[-1]))
                                )
                        if heights is not None:
                            indices = {}
                            for idx, row in get_height.iterrows():
                                dist = row.geometry.distance(Point(tick.coords[-1]))
                                indices[idx] = dist
                            minim = min(indices, key=indices.get)
                            m_heights.append(right.loc[minim][heights])

            openness = (len(lefts) + len(rights)) / len(ticks * 2)
            openness_list.append(1 - openness)
            if rights and lefts:
                results_list.append(2 * np.mean(lefts + rights))
                deviations_list.append(np.std(lefts + rights))
            elif not lefts and rights:
                results_list.append(2 * np.mean([np.mean(rights), tick_length / 2]))
                deviations_list.append(np.std(rights))
            elif not rights and lefts:
                results_list.append(2 * np.mean([np.mean(lefts), tick_length / 2]))
                deviations_list.append(np.std(lefts))
            else:
                results_list.append(tick_length)
                deviations_list.append(0)

            if heights is not None:
                if m_heights:
                    heights_list.append(np.mean(m_heights))
                    heights_deviations_list.append(np.std(m_heights))
                else:
                    heights_list.append(0)
                    heights_deviations_list.append(0)

        self.w = pd.Series(results_list, index=left.index)
        self.wd = pd.Series(deviations_list, index=left.index)
        self.o = pd.Series(openness_list, index=left.index)

        if heights is not None:
            self.h = pd.Series(heights_list, index=left.index)
            self.hd = pd.Series(heights_deviations_list, index=left.index)
            self.p = self.h / self.w

    # http://wikicode.wikidot.com/get-angle-of-line-between-two-points
    # https://glenbambrick.com/tag/perpendicular/
    # angle between two points
    def _getAngle(self, pt1, pt2):
        x_diff = pt2.x - pt1.x
        y_diff = pt2.y - pt1.y
        return math.degrees(math.atan2(y_diff, x_diff))

    # start and end points of chainage tick
    # get the first end point of a tick
    def _getPoint1(self, pt, bearing, dist):
        angle = bearing + 90
        bearing = math.radians(angle)
        x = pt.x + dist * math.cos(bearing)
        y = pt.y + dist * math.sin(bearing)
        return Point(x, y)

    # get the second end point of a tick
    def _getPoint2(self, pt, bearing, dist):
        bearing = math.radians(bearing)
        x = pt.x + dist * math.cos(bearing)
        y = pt.y + dist * math.sin(bearing)
        return Point(x, y)


##############################################
##############################################
## THESE ARE FUNCTIONS COPY-PASTED FROM 
## THE LIBRARY MOMEPY, BECAUSE THEY 
## REQUIRE INTERNET ACCESS, MOMEPY CANNOT
## BE USED DIRECTLY ON THE CLUSTER.
## FOR THE RELEASE, CREATE A COPY WITH 
## ORIGINALS FUNCTION.
##
##
##              (END MOMEPY)
##
##############################################
##############################################
