def create_city_building_files(path_area,country_name,local_crs):
	''' Create building files for individual cities from a larger unique file.
	'''
	start = time.time() 

	# fetch building file for given path
	path_root_folder = '/p/projects/eubucco/data/1-/' <<<<
	path_building_folder = path_root_folder + path_area  
	path_building_files = glob.glob(path_building_folder+'/*')

	buildings = gpd.GeoDataFrame()
	for path_building_file in path_building_files:
		buildings = buildings.append(import_csv_w_wkt_to_gdf(path_building_file,local_crs))

	# create boundary and building file lists
	paths_in = [path for path in get_all_paths(country_name,'boundary') if path_area in path]
	paths_out = [path for path in get_all_paths(country_name,'buildings') if path_area in path]
	paths = list(zip(paths_in,paths_out))

	for path in paths:

		boundary = import_csv_w_wkt_to_gdf(path,local_crs,geometry_col= XXX).geometry
		boundary_plus_buffer = import_csv_w_wkt_to_gdf(path,local_crs,geometry_col= XXX).geometry
		print(boundary.city)

		city = get_area_plus_buffer(gdf, boundary, boundary_plus_buffer)

		save_csv_wkt(city_streets,path[1])

	end = time.time()
	last = divmod(end - start, 60)
	print('Done in {} minutes {} seconds'.format(last[0],last[1])) 


def get_area_plus_buffer(gdf, boundary, boundary_plus_buffer):
    '''
    Returns the elements within an area, and within a buffer around it, marking both
    as being within the main area or the buffer.
    '''
    # joins
    area_plus_buffer = gpd.sjoin(gdf,boundary_plus_buffer,how="inner", op="intersects")
    area = gpd.sjoin(area_plus_buffer,boundary_plus_buffer,how="inner", op="intersects")

    # aggregation
    area_plus_buffer = area_plus_buffer[~area_plus_buffer.index.isin(area.index)]
    area['is_buffer'] = False
    area_plus_buffer['is_buffer'] = True
    area = area.append(area_plus_buffer)
    area = area.drop(columns=['index_right'])

    return(area)



def remove_within_buffer_from_boundary(gdf,buffer_size,GADM_file,GADM_level,area_name,crs):
	'''Removes buildings within a distance from a boundary.
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
