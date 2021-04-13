

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
from scipy.spatial import cKDTree
from shapely.geometry import Point



def features_distance_cbd(gdf, gdf_loc):
   """  
    Returns a DataFrame with an additional line that contains the distance to a given point
    
    Calculates the following:
        
        Features:
        ---------
        - Distance to CBD
 
    Args:
        - df: dataframe with trip origin waypoint
        - loc_CBD: location of Point of Interest (format: shapely.geometry.point.Point)  

    Returns:
        - gdf_out: a DataFrame of shape (number of columns(df)+1, len_df) with the 
          computed features

    Last update: 2/12/21. By Felix.

    """
    # Calculate Distance Metrics and Assign to df
    # create geodataframe

    # create numpy array
    np_geom = gdf.geometry.values
    # 1.create new column in dataframe to assign distance to CBD array to
    gdf['distance_cbd'] = np_geom[:].distance(gdf_loc.geometry.iloc[0])
   
    return gdf



def features_distance_local_cbd(gdf, gdf_loc):
   """  
    Returns a DataFrame with an additional line that contains the distance to the nearest point of a point cloud.
    Taken from: https://gis.stackexchange.com/questions/222315/geopandas-find-nearest-point-in-other-dataframe  
    
    Calculates the following:
        
        Features:
        ---------
        - Distance to nearest local center
 
    Args:
        - gdf: dataframe with trip origin waypoint
        - gdf_loc: geodataframe with point cloud

    Returns:
        - gdf_out: a DataFrame of shape (number of columns(df)+1, len_df) with the 
          computed features

    Last update: 12/04/21. By Felix.

    """
    nA = np.array(list(gdf.geometry.apply(lambda x: (x.x, x.y))))
    nB = np.array(list(gdf_loc.geometry.apply(lambda x: (x.x, x.y))))
    btree = cKDTree(nB)
    dist, idx = btree.query(nA, k=1)
    gdB_nearest = gdf_loc.iloc[idx].drop(columns="geometry").reset_index(drop=True)
    gdf_out = pd.concat(
        [
            gdf.reset_index(drop=True),
            gdB_nearest,
            pd.Series(dist, name='dist')
        ], 
        axis=1)

    return gdf_out