import pandas as pd
import geopandas as gpd
from shapely import wkt
import os


def fetch_GADM_info_country(GADM_country_code,
                         levels='all',
                         path_sheet = 'gadm_table.csv',
                         path_root_folder = '/p/projects/eubucco/data/0-raw-data/gadm'):
    '''Goes in the GADM sheet and picks up the info.
    '''
    # open sheet
    GADM_sheet = pd.read_csv(os.path.join(path_root_folder,path_sheet))

    # filter by country name
    GADM_country = GADM_sheet[GADM_sheet['gadm_code'] == GADM_country_code]

    # get GADM city file
    GADM_file = gpd.read_file(os.path.join(path_root_folder,
                            GADM_country.country_name.iloc[0],
                            f'gadm36_{GADM_country.gadm_code.iloc[0]}_{GADM_country.level_city.iloc[0]}.shp'))

    

    if levels=='all':
        return(GADM_file,GADM_country.country_name.iloc[0],eval(GADM_country.all_levels.iloc[0]),GADM_country.local_crs.iloc[0])
    else:
        return(GADM_file,GADM_country.country_name.iloc[0],GADM_country.level_city.iloc[0],GADM_country.local_crs.iloc[0])



def create_folders(GADM_country_code,
                   path_root_folder = '/p/projects/eubucco/data/2-database-city-level'):
    ''' Create folders for arbitrary nesting GADM nesting level.
    '''

    GADM_file,country_name,GADM_all_levels,_ = fetch_GADM_info_country(GADM_country_code)

    print(country_name)
    print(GADM_all_levels)


    for n,folder_level in enumerate(GADM_all_levels):

        # create parent folder
        if folder_level==1:
            list_areas = list(set(GADM_file.NAME_1))
            for area in list_areas:
                os.makedirs(os.path.join(path_root_folder,country_name,area), exist_ok=False)

        # create next ones
        else:
            list_names = [f'NAME_{level}' for level in GADM_all_levels[:n+1]]
            list_paths = [None]*len(GADM_file)
            for i in range(len(GADM_file)):
                list_paths[i] = '/'.join(GADM_file.iloc[i][list_names].values)

            for path in list_paths:
                os.makedirs(os.path.join(path_root_folder,country_name,path), exist_ok=False)


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
                              country_name,
                              GADM_all_levels,
                              local_crs,
                              path_root_folder='/p/projects/eubucco/data/2-database-city-level'):
    '''
    Returns a csv with  GADM geometries for a each GADM city for a country, 
    both in WGS84 and local crs, and two buffers of 500 and 2000 meters. 
    
    Also returns a list of paths to all cities folder as a .txt file.
    
    '''
    list_paths = []

    for idx in range(len(GADM_file)):

        city_name = GADM_file.iloc[idx][f'NAME_{GADM_all_levels[-1]}']
        print(city_name)

        city_row_local_crs = GADM_file.iloc[[idx]].to_crs(local_crs)

        # create gdf and populate
        city_boundary_gdf = pd.DataFrame({'country': GADM_file.iloc[idx].NAME_0,
                                        'region': GADM_file.iloc[idx].NAME_1,
                                        'city': city_name,
                                        'boundary_GADM_WGS84': GADM_file.iloc[idx].geometry.wkt,
                                        'boundary_GADM': city_row_local_crs.iloc[0].geometry.wkt,
                                        'boundary_GADM_500m_buffer': city_row_local_crs.geometry.iloc[0].buffer(500).wkt,
                                        'boundary_GADM_2k_buffer': city_row_local_crs.geometry.iloc[0].buffer(500).wkt},
                                        index = [0]
                                        )


        names = [f'NAME_{level}' for level in GADM_all_levels]
        path = '/'.join(GADM_file.iloc[idx][names].values)
        path_out = os.path.join(path_root_folder,country_name,path,city_name)
        list_paths += os.path.join(path_out)
        city_boundary_gdf.to_csv(path_out+'_boundary.csv',index=False)

    textfile = open(os.path.join(path_root_folder,country_name,"paths_"+country_name".txt"), "w") 
    for element in list_paths: textfile.write(element + "\n")
    textfile.close()


