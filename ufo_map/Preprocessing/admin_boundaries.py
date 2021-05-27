import geopandas as gpd
from shapely import wkt
import os


def fetch_GADM_info_country(GADM_country_code,
                         levels='all',
                         path_sheet = XXX,
                         path_root_file = XXX):
    '''Goes in the GADM sheet and picks up the info.
    '''
    # open sheet
    GADM_sheet = pd.read_csv(path_sheet)
    # filter by country name
    GADM_country = GADM_sheet[GADM_sheet.country_code == GADM_country_code]
    # get GADM city file
    GADM_file = os.path.join(path_root_file,XXX)

    if levels=='all':
        return(GADM_file,GDAM_country.all_levels,GDAM_country.local_crs)
    else:
        return(GADM_file,GDAM_country.level_city,GDAM_country.local_crs)


def create_folders(GADM_country_code,
                   parent_levels = [1],
                   path_root_folder = XXX):
    ''' Create folders for arbitrary nesting GADM nesting level.
    '''

    GADM_file,GADM_level,_ = fetch_GADM_info_city(GADM_country_code)

    folder_levels = parent_levels + [GADM_level]

    for n,folder_level in enumerate(folder_levels):

        # create parent folder
        if folder_level==1:
            list_areas = list(set(GDAM_file['NAME_1']))
            for area in list_areas:
                try: os.makedirs(os.path.join(path_root_folder,area), exist_ok=False)
                except: f'Folder for {area} exists.'

        # create next ones
        else:
            list_names = [f'NAME_{level}' for level in folder_levels[:n]]
            list_paths = [None]*len(GADM_file)
                for i in range(len(GADM_file)):
                    list_paths[i] = '/'.join(GADM_file.iloc[i][list_names].values)

            for path in list_paths:
                try: os.makedirs(os.path.join(path_root_folder,path), exist_ok=False)
            except: f'Folder for {path} exists.'


def get_area_plus_buffer(area_name, gdf, GADM_file, GADM_level, crs, buff_size):
    '''
    Returns the elements within an area, and within a buffer around it, marking both
    as being within the main area or the buffer.
    '''

    # gdf boundary + 500
    boundary = retrieve_admin_boundary_gdf(area_name, GADM_file, GADM_level, crs, buff_size)

    # sjoin get with buffer 500
    area_plus_buffer = gpd.sjoin(gdf,boundary,how="inner", op="intersects")
    area_plus_buffer = area_plus_buffer.drop(columns=['index_right'])

    print(len(area_plus_buffer))

    # gdf boundary
    boundary = retrieve_admin_boundary_gdf(area_name, GADM_file, GADM_level, crs)

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


def retrieve_admin_boundary_gdf(city_name, GADM_file, GADM_level, crs):
    '''
    Returns a GeoDataFrame with a GADM geometry for a given GADM region name.
    
    Last modified: 27/01/2021. By: Nikola

    '''
    # get polygon (maybe issues with multipolys?)
    city_boundary_poly = GADM_file[GADM_file[GADM_level]==city_name].geometry.iloc[0]
    
    # cast it into gdf
    city_boundary_gdf = gpd.GeoDataFrame(geometry = gpd.GeoSeries(city_boundary_poly),
                                         crs = crs)
    return(city_boundary_gdf)



def create_city_boundary_files(GADM_file,
                              GADM_all_levels,
                              local_crs,
                              path_root_folder):
    '''
    Returns a GeoDataFrame with a GADM geometry for a given GADM region name, and
    two buffers of 500 and 2000 meters. The geometries are written in WKT to
    be saved directly in a csv.
    
    Last modified: 27/01/2021. By: Nikola

    '''
    for city_row in GADM_file.itterows():

        city_name = city_row[f'NAME_{GADM_all_levels[-1]}'][0]
        print(city_name)

        # create gdf and populate
        city_boundary_gdf = gpd.GeoDataFrame()
        city_boundary_gdf['country'] = city_row.NAME_0[0]
        city_boundary_gdf['region'] = city_row.NAME_1[0]
        city_boundary_gdf['city'] = city_name
        city_boundary_gdf['boundary_GADM_WGS84'] =  city_row.geometry.iloc[0].wkt

        city_row_local_crs = GADM_file[[GADM_file[GADM_level]==city_name]].to_crs(local_crs)

        city_boundary_gdf['boundary_GADM'] = city_row_local_crs.geometry.iloc[0].wkt
        city_boundary_gdf['boundary_GADM_500m_buffer'] = city_row_local_crs.geometry.iloc[0].buffer(500).wkt
        city_boundary_gdf['boundary_GADM_2k_buffer'] = city_row_local_crs.geometry.iloc[0].buffer(500).wkt
        
        names = [f'NAME_{level}' for level in GADM_all_levels]
        path = '/'.join(city_row[names].values)
        path_out = os.path.join(path_root_folder,path,city_name+'_boundary.csv')
        city_boundary_gdf.to_csv(path_out,index_col=False)


def remove_within_buffer_from_boundary(gdf,buffer_size,GADM_file,GADM_level,area_name,crs):

    reg_boundary = GADM_file[GADM_file[GADM_level]==name_dept].geometry.iloc[0]
    reg_boundary_minus_buff = reg_boundary.buffer(-buffer_size)
    if  type(reg_boundary_minus_buff) == MultiPolygon:
        reg_boundary_minus_buff = multipoly_to_largest_poly(reg_boundary_minus_buff)
    reg_boundary_minus_buff = gpd.GeoDataFrame(geometry = gpd.GeoSeries(reg_boundary_minus_buff),
                                         crs = crs)
    within_buffer = gpd.sjoin(buildings, reg_boundary_minus_buff, how='inner', op='within')

    return(within_buffer)