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