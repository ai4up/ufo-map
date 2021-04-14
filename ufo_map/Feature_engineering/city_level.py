

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
    gdf['distance_cbd'] = np_geom[:].distance(gdf_loc.geometry.iloc[0])
   
    return gdf



def set_weektime(gdf, weekend):
    """
    Function to filter for weekdays or weekends.

    Args:
        - gdf: geodataframe with trip origin waypoint
        - weekend (bool): 
            0 := no weekend (Mo,...,Fr)
            1 := weekend (Sat, Sun)

    Returns:
        - gdf_out: geodataframe with trips only on either weekdays or weekends

    Last update: 13/04/21. By Felix.
    """

    if weekend:
        gdf['startdate'] = pd.to_datetime(gdf['startdate'])
        gdf_out = gdf[((gdf['startdate']).dt.dayofweek) >= 5]
    else:
        gdf['startdate'] = pd.to_datetime(gdf['startdate'])
        gdf_out = gdf[((gdf['startdate']).dt.dayofweek) < 5]

    return gdf_out