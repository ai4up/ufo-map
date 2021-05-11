"""
Socio-econ related features.
"""

# Imports
import pandas as pd
import geopandas as gpd
import numpy as np


def pop_dens(gdf, gdf_dens,column_name,buffer_size):
    """
    Returns a population density value taken from gdf_dens for each point in gdf.
    The value is calculated by taking the weighted average of all density values intersecting 
    a buffer arrund the point.

    Args: 
        - gdf: geodataframe with points in 'geometry' column or in hex format
        - gdf_dens: geodataframe with polygon or hex raster containing population density values
        - column_name: name of column with data of interest
        - buffer_size: buffer_size (radius in m) for buffer around point; if buffer is None 
          data must be given in hex
        - APERTURE_SIZE: raster of hex

    Returns:
        - gdf_out wich is gdf + a column with population density values

    Last update: 21/04/21. By Felix.

    """
    if buffer_size is not None:
        # create gdf_out
        gdf_out = gdf
        
        # create buffer around points in gdf
        gdf.geometry = gdf.geometry.centroid.buffer(buffer_size)

        # calculate buffer area
        buffer_area = 3.1416*(buffer_size**2)

        # get density polygons intersecting the buffer
        gdf_joined = gpd.sjoin(gdf,gdf_dens[[column_name,'geometry']],how ="left", op="intersects")

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
        gdf_out['feature_pop_density'] = 0
        
        # assign weighted average population dens value to each point in gdf 
        for index in gdf_out.index:
            try:
                # multiply pop dens value with dens_part and sum up the parts to get weighted average
                gdf_out.feature_pop_density.loc[index] = sum(gdf_joined.column_name.loc[index]*gdf_joined.dens_part.loc[index])
            except:
                # assign 0 for points that don't intersect the population density raster
                gdf_out.feature_pop_density.loc[index] = 0
                continue
    else:
        # define hex_col name
        #hex_col = 'hex'+str(APERTURE_SIZE)
        hex_col = 'hex_id'
        # merge trips hex with pop dens hex
        gdf2 = gdf_dens.drop(columns={'geometry'})
        gdf_out = gdf.merge(gdf2,left_on = hex_col, right_on = hex_col)
        
        # find trips that don't have hex data and add 0s
        gdf_diff = gdf.merge(gdf2, how = 'outer' ,indicator=True).loc[lambda x : x['_merge']=='left_only']
        gdf_diff[column_name] = 0
        gdf_diff = gdf_diff.drop(columns="_merge")
        
        # add both together and drop unwanted columns
        gdf_out = pd.concat([gdf_out,gdf_diff], ignore_index=True)
        gdf_out = gdf_out.drop(columns={'OBJECTID','GRD_ID','CNTR_ID','Country','Date','Method','Shape_Leng','Shape_Area'})
        gdf_out = gdf_out.rename(columns={column_name:'feature_pop_density'})

    return gdf_out

def social_index(gdf,gdf_si,column_names):
    """
    Returns the social status as well as the derivative of the social status within a hex of size APERTURE_SIZE.

    Args: 
        - gdf: geopandas dataframe containing trip data in h3
        - gdf_si: geopandas dataframe containing social status data in h3
        - column_names = names of the columns in gdf_si of interest
        - APERTURE_SIZE: h3 size

    Returns:
        - gdf_out wich is gdf + a 2 columns: 'feature_social_status_index', 'feature_social_dynamic_index'

    Last update: 21/04/21. By Felix.

    """
    # define hex_col name
    #hex_col = 'hex'+str(APERTURE_SIZE)
    hex_col = 'hex_id'
    # merge trips hex with pop dens hex
    gdf2 = gdf_si.drop(columns={'geometry'})
    gdf_out = gdf.merge(gdf2,left_on = hex_col, right_on = hex_col)
    
    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how = 'outer' ,indicator=True).loc[lambda x : x['_merge']=='left_only']
    gdf_diff[column_names] = np.NaN
    gdf_diff = gdf_diff.drop(columns="_merge")
    
    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out,gdf_diff], ignore_index=True)
    gdf_out = gdf_out.drop(columns={'Unnamed: 0','district','section','area','population','class','class.1','status_dynamic_index'})
    gdf_out = gdf_out.rename(columns={'status_index':'feature_social_status_index','dynamic_index':'feature_social_dynamic_index'})
    
    # turn categorical +, - and +/- into -1,0,1
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '+', 'feature_social_dynamic_index'] = 1.0
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '+/-', 'feature_social_dynamic_index'] = 0.0
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '-', 'feature_social_dynamic_index'] = -1.0

    return gdf_out

def transit_dens(gdf,gdf_transit,column_name):
    """
    Returns the number of transit stations inside of hexagons.

    Args: 
        - gdf: geopandas dataframe containing trip data in h3
        - gdf_transit: geopandas dataframe containing number of transit stos in h3
        - column_name = names of the column in gdf_transit of interest
        - APERTURE_SIZE: h3 size

    Returns:
        - gdf_out wich is gdf + 1 column: 'feature_transit_density'

    Last update: 11/05/21. By Felix.

    """  
    hex_col = 'hex_id'
    # merge trips hex with pop dens hex
    gdf2 = gdf_transit.drop(columns={'geometry'})
    gdf_out = gdf.merge(gdf2,left_on = hex_col, right_on = hex_col)

    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how = 'outer' ,indicator=True).loc[lambda x : x['_merge']=='left_only']
    gdf_diff[column_name] = 0
    gdf_diff = gdf_diff.drop(columns="_merge")

    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out,gdf_diff], ignore_index=True)
    gdf_out = gdf_out[['hex_id','tripdistancemeters','lengthoftrip','points_in_hex','geometry',column_name]]
    gdf_out = gdf_out.rename(columns={column_name:'feature_transit_density'})
    return gdf_out
