import sys, os
import socket
import geopandas as gpd

if 'cs-' in socket.gethostname(): sys.path.append('/p/projects/eubucco/git-ufo-map')
elif socket.gethostname() == '60-MCC': sys.path.append(r'C:\Users\miln\tubCloud\Work-in-progress\building-project\git-ufo-map')
else: sys.exit('I am sorry but who are you?')

from ufo_map.Utils.helpers import multipoly_to_largest_poly



def get_area_plus_buffer(gdf, boundary, boundary_plus_buffer):
    '''
    Fetches elements within an area, and within a buffer around it, marking both
    as being within the main area or the buffer with a boolean in a column `is_buffer`.

    Returns: gpd.GeoDataFrame
    '''
    
    # joins
    area_plus_buffer = gpd.sjoin(gdf,boundary_plus_buffer,how="inner", op="intersects").drop(columns=['index_right'])
    area = gpd.sjoin(area_plus_buffer,boundary,how="inner", op="intersects").drop(columns=['index_right'])

    # aggregation
    area_plus_buffer = area_plus_buffer[~area_plus_buffer.index.isin(area.index)]
    area['is_buffer'] = False
    area_plus_buffer['is_buffer'] = True
    area = area.append(area_plus_buffer)

    return(area)



def remove_within_buffer_from_boundary(gdf,buffer_size,GADM_file,GADM_level,area_name,crs):
    '''
    Removes elements within a distance from a boundary.
    
    TODO: there is something wrong here. Test.

    '''
    reg_boundary = GADM_file[GADM_file[GADM_level]==name_dept].geometry.iloc[0]
    reg_boundary_minus_buff = reg_boundary.buffer(-buffer_size)
    if  type(reg_boundary_minus_buff) == MultiPolygon:
        reg_boundary_minus_buff = multipoly_to_largest_poly(reg_boundary_minus_buff)
    reg_boundary_minus_buff = gpd.GeoDataFrame(geometry = gpd.GeoSeries(reg_boundary_minus_buff),
                                         crs = crs)
    within_buffer = gpd.sjoin(buildings, reg_boundary_minus_buff, how='inner', op='within')

    return(within_buffer)




# def get_area_plus_buffer(area_name, gdf, GADM_file, GADM_level, crs, buff_size):
#     '''
#     Returns the elements within an area, and within a buffer around it, marking both
#     as being within the main area or the buffer.
#     '''

#     # gdf boundary + 500
#     boundary = retrieve_admin_boundary_gdf(area_name, GADM_file, GADM_level, crs, buff_size)

#     # sjoin get with buffer 500
#     area_plus_buffer = gpd.sjoin(gdf,boundary,how="inner", op="intersects")
#     area_plus_buffer = area_plus_buffer.drop(columns=['index_right'])

#     print(len(area_plus_buffer))

#     # gdf boundary
#     boundary = retrieve_admin_boundary_gdf(area_name, GADM_file, GADM_level, crs)

#     # sjoin get city
#     area = gpd.sjoin(area_plus_buffer,boundary,how="inner", op="intersects")
#     area = area.drop(columns=['index_right'])
#     print(len(area))

#     area_plus_buffer = area_plus_buffer[~area_plus_buffer.index.isin(area.index)]
#     area['is_buffer'] = False
#     area_plus_buffer['is_buffer'] = True

#     area = area.append(area_plus_buffer)
#     print(len(area))

#     area['city'] = area_name

#     return(area)
