"""
Socio-econ related features.
"""

# Imports
import pandas as pd
import geopandas as gpd
import numpy as np
import ufo_map.Utils.helpers as ufo_helpers


def _prepare_gdf(gdf,buffer_size):
    gdf_tmp = gdf.copy()    
    geometry_types = ufo_helpers.get_geometry_type(gdf_tmp)
    if 'Point' in geometry_types:
        gdf_tmp.geometry = gdf_tmp.geometry.centroid.buffer(buffer_size)
    return gdf_tmp, geometry_types


def _get_inter_area(row,gdf_data):
    try:
        # calc intersection area
        out = (row.geometry.intersection(gdf_data.geometry[row.index_right])).area
    except BaseException:
        # in rows which don't intersect with a raster of the density data (NaN)
        out = np.nan
    return out 


def _data_proportion_averaged(gdf_joined,gdf_data,column_name,id_col):
    """calculates feature value in relation to area where feature data is available"""
    # get intersecting area and delete rows where no data is available
    gdf_joined['intersecting_area'] = gdf_joined.apply(lambda row: _get_inter_area(row,gdf_data), axis=1)
    gdf_joined = gdf_joined[gdf_joined['intersecting_area'].notna()]
    # calc total area where feature data is available
    df_feature_area = gdf_joined.groupby(id_col)['intersecting_area'].sum().to_frame('total_feature_area').reset_index()
    # calculate weighted proportion
    gdf_joined = pd.merge(gdf_joined,df_feature_area)
    gdf_joined['feature_value_part'] = (gdf_joined['intersecting_area'] / gdf_joined['total_feature_area'])*gdf_joined[column_name]
    return gdf_joined


def _data_proportion_total(gdf_joined,gdf_data,column_name): 
    """calculates feature value in relation to whole area of buffer geometry"""
    gdf_joined['intersecting_area'] = gdf_joined.apply(lambda row: _get_inter_area(row,gdf_data), axis=1)
    gdf_joined = gdf_joined[gdf_joined['intersecting_area'].notna()]
    # data value * proportion of intersection
    gdf_joined['feature_value_part'] = (gdf_joined['intersecting_area'] / gdf_joined['total_data_area'])*gdf_joined[column_name]
    return gdf_joined


def _check_value_per_area(gdf_, feature_name, buffer_size, geometry_types, feature_type):
    # for pop dense get total count/m^2 instead of count
    if feature_type == 'total_per_area': 
        if 'Point' in geometry_types:
            gdf_[feature_name] = (gdf_[feature_name]/gdf_.geometry.centroid.buffer(buffer_size))*1e6 # metric is reported in count/km^2
        else:
            gdf_[feature_name] = (gdf_[feature_name]/gdf_.geometry.area)*1e6 # metric is reported in count/km^2
        return gdf_
    else: return gdf_


def feature_in_buffer(gdf, 
                    gdf_data, 
                    column_name, 
                    feature_name,
                    buffer_size=50,
                    id_col='tractid',
                    feature_type='weighted', # accepts: weighted, total, total_per_area
                    ):
    """
    Returns a feature value taken for each point or polygon in gdf.
    The value is calculated by taking 
    - the count in relation to available feature area (feature_type:=weighted)
    - the total count (feature_type:=total)
    - the total count per buffer/zip code area (feature_type:=total_per_area)
    of all feature values intersecting a buffer around the point/ polygon. 
    If there are areas that do not contain feature data, then they are not considered.
    """
    gdf_tmp, geometry_types = _prepare_gdf(gdf,buffer_size)
    gdf_data['total_data_area'] = gdf_data.geometry.area
    gdf_joined = gpd.sjoin(gdf_tmp, gdf_data[[column_name,'total_data_area','geometry']], how="left")
    
    if feature_type=='weighted':
        gdf_out = _data_proportion_averaged(gdf_joined,gdf_data,column_name,id_col)
    else:
        gdf_out = _data_proportion_total(gdf_joined,gdf_data,column_name)
    
    gdf_out_cleaned = gdf_out.loc[~gdf_out.feature_value_part.isna()]
    gdf_out_cleaned = gdf_out_cleaned.groupby(id_col)['feature_value_part'].sum().to_frame(feature_name).reset_index() 
    
    if 'Point' in geometry_types:
        gdf_sum = pd.merge(gdf[[id_col]],gdf_out_cleaned,how='left') # fills all rows where no intersection with nan
    else: 
        gdf_sum = pd.merge(gdf,gdf_out_cleaned[[id_col,feature_name]],how='left')

    return _check_value_per_area(gdf_sum,feature_name,buffer_size, geometry_types, feature_type) 


def trips_per_capita(gdf_o,
                    gdf_pop_dense, 
                    gdf_points,
                    pop_col,
                    feature_name,
                    buffer_size,
                    id_col):
    """
    Returns a feature value taken for each point or polygon in gdf.
    The value is calculated by dividing the number of trips by
    the total population count per buffer around a point/ per zip polygon. 
    If there are areas that do not contain feature data, then they are not considered.
    """
    # get population density data per buffer / polygon
    df_tot_pop = feature_in_buffer(gdf_o, gdf_pop_dense, pop_col, 
                    feature_name='pop_count',od_col='origin',
                    buffer_size=buffer_size,id_col=id_col, feature_type='total')
    
    # get number of trips per buffer / polygon
    gdf_points['id_origin'] = gdf_points['id_origin'].astype(str)
    gdf_points_num = gdf_points.groupby('id_origin').size().reset_index(name='num_trips')
    gdf_o = gdf_o.drop_duplicates(subset='id_origin').reset_index(drop=True)
    gdf = pd.merge(gdf_o, gdf_points_num, on='id_origin', how='left')

    print('merging and returning')
    gdf = pd.merge(gdf, df_tot_pop[['id','pop_count']], on='id')   
    gdf[feature_name] = gdf['num_trips']/gdf['pop_count']
    return gdf


def zips_within_threshold(df, threshold=10000):
    num_jobs = 0
    zip_index = []
    
    for index, row in df.iterrows():
        if row["num_jobs"] < threshold:
            num_jobs += row["num_jobs"] 
            zip_index.append(index)
        else:
            if not zip_index: # add index 0
                zip_index.append(index)
            break
    return zip_index


def weighted_distance_to_n_jobs(gdf, i, distance_matrix, n=10000):
    # for i-th col, sort and find index of closest points 
    closest_point_ids = distance_matrix[i].sort_values().index
    zip_index = zips_within_threshold(gdf.loc[closest_point_ids], threshold=n)

    distance = distance_matrix[i][zip_index] # distance
    jobs = gdf.loc[zip_index]['num_jobs'] # job
    if jobs.sum()>0:
        return np.average(distance.to_numpy(), weights=jobs.to_numpy())
    else: 
        return np.average(distance.to_numpy())


def prepare_employment_data(gdf,gdf_emp_raw, id_col):
    return feature_in_buffer(gdf, 
                                gdf_emp_raw, 
                                'num_jobs', 
                                buffer_size=50,
                                id_col = id_col,
                                feature_name='num_jobs',
                                feature_type='total'
                                )
    #return gdf_emp.drop_duplicates(subset='id_origin').reset_index()


def employment_access(gdf, gdf_emp_raw, feature_name, threshold=0.1, id_col = 'tractid'):
    # prepare
    gdf_emp = feature_in_buffer(gdf, gdf_emp_raw, 'num_jobs', feature_name='num_jobs',feature_type='total')
    gdf_emp.loc[gdf_emp['num_jobs'].isna(),'num_jobs'] = 0.0 # set nans to 0 jobs 
    threshold = int(threshold*gdf_emp['num_jobs'].sum())
    
    # assign
    gdf_tmp = gdf_emp.copy(deep=True)
    gdf_tmp['geometry'] = gdf_tmp.geometry.centroid
    distance_matrix = gdf_tmp.geometry.apply(lambda x: gdf_tmp.distance(x))

    for i in gdf_emp.index:
        if i%100==0:print(i)
        gdf_emp.loc[i,feature_name] = weighted_distance_to_n_jobs(gdf_tmp, i, distance_matrix, threshold) 
    
    return pd.merge(gdf,gdf_emp[[id_col,feature_name]],on=id_col)


def zips_within_threshold_v2(df, n_jobs=10000):
    num_jobs = 0
    zip_index = []
    
    for index, row in df.iterrows():
        if num_jobs < n_jobs:
            num_jobs += row["num_jobs"] 
            zip_index.append(index)
        else:
            # if not zip_index: # add index 0
            #     zip_index.append(index)
            break
    return zip_index


def weighted_distance_to_n_jobs_v2(gdf_emp, i, distance_matrix, n_jobs=10000):
    # for i-th col, sort and find index of closest points 
    closest_point_ids = distance_matrix[i].sort_values().index
    zip_index = zips_within_threshold_v2(gdf_emp.loc[closest_point_ids], n_jobs=n_jobs)

    distance = distance_matrix[i][zip_index] # distance
    jobs = gdf_emp.loc[zip_index]['num_jobs'] # job
    if jobs.sum()>0:
        return np.average(distance.to_numpy(), weights=jobs.to_numpy())
    else:
        raise ValueError('No Jobs found?!')


def prep_for_employment_access(gdf,gdf_emp_raw):
    # create 10 km buffer around our area of analysis
    gdf_bound = gdf.iloc[[0]]
    gdf_bound['geometry'] = gdf.geometry.unary_union
    gdf_bound['geometry'] = gdf_bound.geometry.buffer(10000)
    gdf_bound = gdf_bound.drop(columns='tractid') 
    return gpd.sjoin(gdf_emp_raw, gdf_bound)


def employment_access_v2(gdf, gdf_emp_raw, feature_name, threshold=0.1, id_col = 'tractid'):
    # prepare
    gdf_emp = prep_for_employment_access(gdf,gdf_emp_raw)
    gdf_emp.loc[gdf_emp['num_jobs'].isna(),'num_jobs'] = 0.0 # set nans to 0 jobs 
    n_jobs = int(threshold*gdf_emp['num_jobs'].sum())
    
    # assign
    gdf_emp_tmp = gdf_emp.copy(deep=True)
    gdf_tmp = gdf.copy(deep=True)
    
    gdf_emp_tmp['geometry'] = gdf_emp_tmp.geometry.centroid
    gdf_tmp['geometry'] = gdf_tmp.geometry.centroid

    distance_matrix = gdf_emp_tmp.geometry.apply(lambda x: gdf_tmp.distance(x))

    for i in gdf.index:
        if i%100==0:print(i)
        gdf.loc[i,feature_name] = weighted_distance_to_n_jobs_v2(gdf_emp, i, distance_matrix, n_jobs) 
    
    return gdf



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
