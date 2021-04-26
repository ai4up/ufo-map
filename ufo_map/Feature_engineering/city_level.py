

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
from ufo_map.Utils.helpers import nearest_neighbour


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
    gdf['distance_cbd'] = np_geom[:].distance(gdf_loc.geometry.iloc[0])
   
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
    gdf_out = gdf_out.rename(columns={"name": "local_CBD", "distance_loc_cbd": "distance"})
    gdf_out = gdf_out.drop(columns={'nodeID','closeness_global'})
    return gdf_out



def pop_dens(gdf, gdf_dens,buffer_size):
    """
    Returns a population density value taken from gdf_dens for each point in gdf.
    The value is calculated by taking the weighted average of all density values intersecting 
    a buffer arrund the point.

    Args: 
        - gdf: geodataframe with points in 'geometry' column
        - gdf_dens: geodataframe with polygon raster containing population density values
        - buffer_size: buffer_size (radius in m) for buffer around point

    Returns:
        - gdf_out wich is gdf + a column with population density values

    Last update: 21/04/21. By Felix.

    """
    # create gdf_out
    gdf_out = gdf
    
    # create buffer around points in gdf
    gdf.geometry = gdf.geometry.centroid.buffer(buffer_size)

    # calculate buffer area
    buffer_area = 3.1416*(buffer_size**2)

    # get density polygons intersecting the buffer
    gdf_joined = gpd.sjoin(gdf,gdf_dens[['TOT_P_2018','geometry']],how ="left", op="intersects")

    # define function that calculates intersecting area of buffer and dens polygons
    def get_inter_area(row):
        try:
            # calc intersection area
            out = (row.geometry.intersection(gdf_dens.geometry[row.index_right])).area
        except:
            # in rows which don't intersect with a raster of the density data (NaN)
            out = 0    
        return out # intersecting area

    # calculate shared area of polygons
    gdf_joined['dens_part']=gdf_joined.apply(get_inter_area,axis=1)
    
    # calculate their share in the buffer
    gdf_joined['dens_part']=gdf_joined['dens_part']/buffer_area 

    # initialise new column in gdf
    gdf_out['pop_dens_buffer'] = 0
    
    # assign weighted average population dens value to each point in gdf 
    for index in gdf_out.index:
        try:
            # multiply pop dens value with dens_part and sum up the parts to get weighted average
            gdf_out.pop_dens_buffer.loc[index] = sum(gdf_joined.TOT_P_2018.loc[index]*gdf_joined.dens_part.loc[index])
        except:
            # assign 0 for points that don't intersect the population density raster
            gdf_out.pop_dens_buffer.loc[index] = 0
            continue

    return gdf_out