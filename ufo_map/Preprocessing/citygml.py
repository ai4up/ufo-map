from lxml import etree
from shapely.geometry import Polygon,MultiPolygon
from shapely.ops import unary_union
from shapely import wkt
import geopandas as gpd
import pandas as pd
import numpy as np
import sys
from tqdm import tqdm

# import own functions
from ufo_map.Utils.helpers import multipoly_to_largest_poly


def bbox_height_calculator(building, cityGML_root):

    '''
    Computes the height of a building by substracting the highest point and lowest point of its bounding box.

    Takes as input a CityGML building object.

    Returns a height as a float.

    Last modified: 12/09/2020. By: Nikola

    '''
        
    # extract lower and higher corner vectors 
    # (nsmap is namespace, in <CityModel ...>, maps e.g. xmlns:bldg to file where this object is defined) 
    lowerCorner = building.findall('./gml:boundedBy/gml:Envelope/gml:lowerCorner', cityGML_root.nsmap)[0].text
    upperCorner = building.findall('./gml:boundedBy/gml:Envelope/gml:upperCorner', cityGML_root.nsmap)[0].text
    
    # transform into float
    lowerCorner = [float(s) for s in lowerCorner.split()]
    upperCorner = [float(s) for s in upperCorner.split()]
    
    # substract the heights (third element of the vector)
    height_bbox = upperCorner[2] - lowerCorner[2]
    
    return height_bbox


def min_max_wall_height_calculator(building,path,namespace):
    '''
    Compute the height of a building by taking the distance between highest and lowest
    point of the walls, following the definition of the French cadaster.
    '''
    list = building.findall(path,namespace)
    list = [item.text for item in list]
    list = [item.split() for item in list] 
    list = [item[2::3] for item in list]
    list = [item for sublist in list for item in sublist]
    list = [float(item) for item in list]
    return(max(list)-min(list)) 


def get_measured_height(building,path,namespace):
    '''
    Get the height potentially available as a single value in the file.
    '''

    list_heights = building.findall(path, namespace)

    # if there is no height, save height equals na
    if len(list_heights) == 0:
        return(np.nan)
    
    # else get the max height in the list
    else:
        list_heights_float = []
        # iterate over the heights list
        for j in range(0, len(list_heights)):
            if list_heights[j].text is not None:
                # convert to float
                list_heights_float.append(float(list_heights[j].text))
            else:
                list_heights_float.append(np.nan)

        return(max(list_heights_float))


def poly_converter(ground_geoms_list, crs):

    '''
    Convert the ground surface polygon(s) of a building from CityGML file into a single WKT polygon.

    Takes as input a list of 3D ground surface geometries as CityGML strings.

    Outputs a 2D building footprint as a WKT string.

    Last modified: 12/09/2020. By: Nikola

    '''
    
    # if there is a least one ground surface polygon part for the building
    if len(ground_geoms_list) > 0:

        list_poly = []

        for poly in ground_geoms_list:

            str_poly = poly.text

            exp_poly_float = [float(s) for s in str_poly.split()]

            long = exp_poly_float[0::2]
            lat = exp_poly_float[1::2]

            list_poly.append(Polygon(zip(long, lat)))

        return unary_union(list_poly)

    else:
        return np.nan


def citygml_to_df(cityGML_buildings, 
                  cityGML_root, 
                  file_info, 
                  crs, 
                  measured_height=False, 
                  bbox = False,
                  measured_height_path = './/bldg:measuredHeight'
                  ):

    '''
    Converts a list of CityGML building objects into DataFrame with: 

    * footprint/ground polygon as wkt string

    * the max height for a building, from value provided as an attribute in the 3D data

    * optionally, compute the height using the min and max height values of the bounding box, 
      by setting bbox = True (parameter set by default to False)

    * the id of the building

    * file info: country, region, city, district, file_name. Pass the info as a vector. 
      If the info is not available, put NaN e.g. ['Germany', 'Berlin', 'Berlin', np.nan, 'E20db204']

    Last modified: 12/21/2020. By: Nikola

    '''
    
    # create a column list to pass in the dataframe
    columns = ['id','height_measured','country','region','city','district','source file','geometry']
    


    # create empty arrays
    id_array = [None]*len(cityGML_buildings)
    height_array = [None]*len(cityGML_buildings)
    geometry_array = [None]*len(cityGML_buildings)

    # add column for height bbox if need
    if bbox:
       height_bbox_array = [None]*len(cityGML_buildings)

    if measured_height:
        measured_height_array = [None]*len(cityGML_buildings)

    
    # iterate over the CityGML buildings
    for i, building in enumerate(tqdm(cityGML_buildings)):
    
        # extract the id of the building
        id_array[i] = building.get("{"+cityGML_root.nsmap['gml']+"}id")

        # compute height 
        height_array[i] = min_max_wall_height_calculator(building,'.//bldg:WallSurface//gml:posList',cityGML_root.nsmap)

        # compute the height using the bounding box
        if bbox:
            height_bbox_array[i] = bbox_height_calculator(building, cityGML_root)

        if measured_height:
            measured_height_array[i] = get_measured_height(building,measured_height_path,cityGML_root.nsmap)


        # extract all ground surface polygons for the building
        ground_geoms_list = building.findall('.//bldg:GroundSurface//gml:posList', cityGML_root.nsmap)

        # convert the citygml string to a wkt polygon
        ground_polygon_wtk = poly_converter(ground_geoms_list = ground_geoms_list, crs = crs) 
        
        # store the final ground polygon for the building in the geometry column
        geometry_array[i] = ground_polygon_wtk

    # save the name of the source file
    df = pd.DataFrame()

    df['id'] = id_array
    df['height'] = height_array
    if bbox: df['height_bbox'] = height_bbox_array
    if measured_height: df['measured_height'] = measured_height_array
    df['country'] = file_info[0]
    df['region'] = file_info[1]
    df['city'] = file_info[2]
    df['district'] = file_info[3]    
    df['source file'] = file_info[4]
    df['geometry'] = geometry_array
    
    return df


def parse_citygml(path_file,area_info,crs,bbox):

    '''
    Runs the whole pipeline from a path to CityGML file to a DataFrame.

    Last modified: 12/09/2020. By: Nikola

    '''

    # load citygml file
    citygml_file = etree.parse(path_file)

    # get the root element
    citygml_root = citygml_file.getroot()

    # extract a list of all building elements
    buildings = citygml_file.findall(".//{"+citygml_root.nsmap['bldg']+"}Building")

    # if there are buildings in the file
    try: 
        print('There are {} buildings in the file.'.format(len(buildings)))

        # parse file
        df = citygml_to_df(buildings,
                           citygml_root,
                           area_info,
                           crs,
                           bbox
                          )

    except:
        df = pd.DataFrame(columns = ['id','height_measured','country','region','city','district','source file','geometry'])

    return df

