"""
Socio-econ related features.
"""

# Imports
import pandas as pd
import geopandas as gpd
import numpy as np
from ufo_map.Utils.helpers import _check_geometry_type


def _get_feature_proportion(gdf_joined,gdf_dens,column_name):
    def _get_inter_area(row):
        try:
            # calc intersection area
            out = (row.geometry.intersection(gdf_dens.geometry[row.index_right])).area
        except BaseException:
            # in rows which don't intersect with a raster of the density data (NaN)
            out = 0
        return out  
    gdf_joined['intersecting_area'] = gdf_joined.apply(_get_inter_area, axis=1)
    df_feature_area = gdf_joined.groupby('id')['intersecting_area'].sum().to_frame('total_feature_area').reset_index()
    gdf_joined = pd.merge(gdf_joined,df_feature_area)
    gdf_joined['feature_value_part'] = (gdf_joined['intersecting_area'] / gdf_joined['total_feature_area'])*gdf_joined[column_name]
    return gdf_joined


def feature_in_buffer(gdf, gdf_dens, column_name, feature_name='feature_pop_density',od_col='origin', buffer_size=50):
    """
    Returns a feature value taken for each point in gdf.
    The value is calculated by taking the weighted average of all feature values intersecting
    a buffer arrund the point. If there are areas that do not contain feature data, then they
    are not considered in the weighted average.
    
    This function can be applied to any count values that are provided per polygon, such as
    population count or income.
    """
        
    gdf_tmp = gdf.copy()
    geometry_types = _check_geometry_type(gdf_tmp)
    if 'Point' in geometry_types:
        gdf_tmp.geometry = gdf_tmp.geometry.centroid.buffer(buffer_size)
    else: 
        gdf_tmp = gdf_tmp.drop_duplicates(subset='id_'+od_col).reset_index(drop=True)

    gdf_joined = gpd.sjoin(gdf_tmp, gdf_dens[[column_name, 'geometry']], how="left")
    gdf_out = _get_feature_proportion(gdf_joined,gdf_dens,column_name)    
    if 'Point' in geometry_types:
        return gdf_out.groupby('id')['feature_value_part'].sum().to_frame(feature_name).reset_index()
    else: 
        gdf_out = gdf_out.groupby('id_'+od_col)['feature_value_part'].sum().to_frame(feature_name).reset_index()
        return pd.merge(gdf,gdf_out[['id_'+od_col,feature_name]],on='id_'+od_col,how='left')



def pop_dens_h3(gdf, gdf_dens, column_name, feature_name=None, buffer_size=50):    
    # define hex_col name
    #hex_col = 'hex'+str(APERTURE_SIZE)
    hex_col = 'hex_id'
    # merge trips hex with pop dens hex
    gdf2 = gdf_dens.drop(columns={'geometry'})
    gdf_out = gdf.merge(gdf2, left_on=hex_col, right_on=hex_col)

    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how='outer', indicator=True).loc[lambda x: x['_merge'] == 'left_only']
    gdf_diff[column_name] = 0
    gdf_diff = gdf_diff.drop(columns="_merge")

    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out, gdf_diff], ignore_index=True)
    gdf_out = gdf_out.drop(
        columns={
            'OBJECTID',
            'GRD_ID',
            'CNTR_ID',
            'Country',
            'Date',
            'Method',
            'Shape_Leng',
            'Shape_Area'})
    gdf_out = gdf_out.rename(columns={column_name: 'feature_pop_density'}) #TODO adjust

    print('Calculated population density')
   


def social_index(gdf, gdf_si, column_names):
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
    gdf_out = gdf.merge(gdf2, left_on=hex_col, right_on=hex_col)

    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how='outer', indicator=True).loc[lambda x: x['_merge'] == 'left_only']
    gdf_diff[column_names] = np.NaN
    gdf_diff = gdf_diff.drop(columns="_merge")

    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out, gdf_diff], ignore_index=True)
    gdf_out = gdf_out.drop(
        columns={
            'Unnamed: 0',
            'district',
            'section',
            'area',
            'population',
            'class',
            'class.1',
            'status_dynamic_index'})
    gdf_out = gdf_out.rename(
        columns={
            'status_index': 'feature_social_status_index',
            'dynamic_index': 'feature_social_dynamic_index'})

    # turn categorical +, - and +/- into -1,0,1
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '+', 'feature_social_dynamic_index'] = 1.0
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '+/-', 'feature_social_dynamic_index'] = 0.0
    gdf_out.loc[gdf_out.feature_social_dynamic_index == '-', 'feature_social_dynamic_index'] = -1.0
    print('Calculated social status')
    return gdf_out


def transit_dens(gdf, gdf_transit, column_name):
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
    gdf_out = gdf.merge(gdf2, left_on=hex_col, right_on=hex_col)

    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how='outer', indicator=True).loc[lambda x: x['_merge'] == 'left_only']
    gdf_diff[column_name] = 0
    gdf_diff = gdf_diff.drop(columns="_merge")

    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out, gdf_diff], ignore_index=True)
    gdf_out = gdf_out.drop(columns={'lat', 'lng'})
    gdf_out = gdf_out.rename(columns={column_name: 'feature_transit_density'})
    print('Calculated transit density')
    return gdf_out


def income(gdf, gdf_si, column_names):
    """
    Returns the income within a hex of size APERTURE_SIZE. The income is the weighted average income per plz.
    The weighted average income is calculated based on categories 1-7, derived from Axciom data.

    Args:
        - gdf: geopandas dataframe containing trip data in h3
        - gdf_si: geopandas dataframe containing income data in h3
        - column_names = names of the columns in gdf_si of interest
        - APERTURE_SIZE: h3 size

    Returns:
        - gdf_out wich is gdf + column: 'feature_income'

    Last update: 21/04/21. By Felix.

    """
    # define hex_col name
    #hex_col = 'hex'+str(APERTURE_SIZE)
    hex_col = 'hex_id'
    # merge trips hex with pop dens hex
    gdf2 = gdf_si.drop(columns={'geometry'})
    gdf_out = gdf.merge(gdf2, left_on=hex_col, right_on=hex_col)

    # find trips that don't have hex data and add 0s
    gdf_diff = gdf.merge(gdf2, how='outer', indicator=True).loc[lambda x: x['_merge'] == 'left_only']
    gdf_diff[column_names] = np.NaN
    gdf_diff = gdf_diff.drop(columns="_merge")

    # add both together and drop unwanted columns
    gdf_out = pd.concat([gdf_out, gdf_diff], ignore_index=True)
    gdf_out = gdf_out.drop(
        columns={
            'plz',
            'ph_to',
            'stat_1u2',
            'stat_3',
            'stat_4',
            'stat_5',
            'stat_6',
            'stat_7',
            'stat_8u9',
            'mean'})
    gdf_out = gdf_out.rename(columns={'weigthed_mean': 'feature_income'})

    print('Calculated income status')
    return gdf_out
