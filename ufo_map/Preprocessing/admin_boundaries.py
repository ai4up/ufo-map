import geopandas as gpd
from shapely import wkt


def get_area_plus_buffer(area_name, gdf, GDAM_file, GDAM_level, crs, buff_size):
    '''
    Returns the elements within an area, and within a buffer around it, marking both
    as being within the main area or the buffer.
    '''

    # gdf boundary + 500
    boundary = retrieve_admin_boundary_gdf(area_name, GDAM_file, GDAM_level, crs, buff_size)

    # sjoin get with buffer 500
    area_plus_buffer = gpd.sjoin(gdf,boundary,how="inner", op="intersects")
    area_plus_buffer = area_plus_buffer.drop(columns=['index_right'])

    print(len(area_plus_buffer))

    # gdf boundary
    boundary = retrieve_admin_boundary_gdf(area_name, GDAM_file, GDAM_level, crs)

    # sjoin get city
    area = gpd.sjoin(area_plus_buffer,boundary,how="inner", op="intersects")
    area = area.drop(columns=['index_right'])
    print(len(area))

    area_plus_buffer = area_plus_buffer[~area_plus_buffer.index.isin(area.index)]
    area['is_buffer'] = False
    area_plus_buffer['is_buffer'] = True

    area = area.append(area_plus_buffer)
    print(len(area))

    area['city'] = area_name

    return(area)


def retrieve_admin_boundary_gdf(city_name, GDAM_file, GDAM_level, crs):
    '''
    Returns a GeoDataFrame with a GDAM geometry for a given GDAM region name.
    
    Last modified: 27/01/2021. By: Nikola

    '''
    # get polygon (maybe issues with multipolys?)
    city_boundary_poly = GDAM_file[GDAM_file[GDAM_level]==city_name].geometry.iloc[0]
    
    # cast it into gdf
    city_boundary_gdf = gpd.GeoDataFrame(geometry = gpd.GeoSeries(city_boundary_poly),
                                         crs = crs)
    return(city_boundary_gdf)



def admin_boundary_plus_buffers_gdf_wkt(city_name,GDAM_file,GDAM_level,crs):
    '''
    Returns a GeoDataFrame with a GDAM geometry for a given GDAM region name, and
    two buffers of 500 and 2000 meters. The geometries are written in WKT to
    be saved directly in a csv.
    
    Last modified: 27/01/2021. By: Nikola

    '''
    # get polygon (maybe issues with multipolys?)
    city_boundary_poly = GDAM_file[GDAM_file[GDAM_level]==city_name].geometry.iloc[0]

    # create gdf and populate
    city_boundary_gdf = gpd.GeoDataFrame()
    
    boundary_gdam = gpd.GeoDataFrame({'city' : city_name,
                                       'geometry' : city_boundary_poly.wkt,
                                       'boundary_name' : 'boundary_gdam'}, 
                                     index = [0])

    boundary_gdam_500m_buffer = gpd.GeoDataFrame({'city' : city_name,
                                               'geometry' : city_boundary_poly.buffer(500).wkt,
                                               'boundary_name' : 'boundary_gdam_500m_buffer'}, 
                                             index = [1])

    boundary_gdam_2k_buffer = gpd.GeoDataFrame({'city' : city_name,
                 'geometry' : city_boundary_poly.buffer(2000).wkt,
                 'boundary_name' : 'boundary_gdam_2k_buffer'}, 
                 index = [2])

    city_boundary_gdf = city_boundary_gdf.append(boundary_gdam)
    city_boundary_gdf = city_boundary_gdf.append(boundary_gdam_500m_buffer)
    city_boundary_gdf = city_boundary_gdf.append(boundary_gdam_2k_buffer)
    
    city_boundary_gdf.crs = crs
    
    return(city_boundary_gdf)


## Get 500m within
def remove_within_buffer_from_boundary(gdf,buffer_size,GDAM_file,GDAM_level,area_name,crs):

    reg_boundary = GDAM_file[GDAM_file[GDAM_level]==name_dept].geometry.iloc[0]
    reg_boundary_minus_buff = reg_boundary.buffer(-buffer_size)
    if  type(reg_boundary_minus_buff) == MultiPolygon:
        reg_boundary_minus_buff = multipoly_to_largest_poly(reg_boundary_minus_buff)
    reg_boundary_minus_buff = gpd.GeoDataFrame(geometry = gpd.GeoSeries(reg_boundary_minus_buff),
                                         crs = crs)
    within_buffer = gpd.sjoin(buildings, reg_boundary_minus_buff, how='inner', op='within')

    return(within_buffer)