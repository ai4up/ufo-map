from lxml import etree
from shapely.geometry import Polygon,MultiPolygon
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
    


def poly_converter(ground_geoms_list, crs):

    '''
    Convert the ground surface polygon(s) of a building from CityGML file into a single WKT polygon.

    Takes as input a list of 3D ground surface geometries as CityGML strings.

    Outputs a 2D building footprint as a WKT string.

    Last modified: 12/09/2020. By: Nikola

    '''
    
    # if there is a least one ground surface polygon part for the building
    if len(ground_geoms_list) > 0:
        
        # create DataFrame for the building
        df_building = gpd.GeoDataFrame(np.nan, index = range(len(ground_geoms_list)), columns = ['geometry'], crs = crs)
            
        # iterate over ground surface parts polygons
        for i, poly in enumerate(ground_geoms_list):

            # extract string
            str_poly = poly.text

            # convert to coordinates to float
            exp_poly_float = [float(s) for s in str_poly.split()]

            # extract long, lat, height
            long = exp_poly_float[0::3]
            lat = exp_poly_float[1::3]
            
            # create shapely ground polygon from coords
            ground_geom = Polygon(zip(long, lat))

            # save the polygon into the GeoDataFrame
            df_building.loc[i, 'geometry'] = ground_geom

            # create new column for dissolve
            df_building['dissolve_column'] = 0

        # there might be problems with inappropriate polygons in the data 
        try:

            # dissolve all the parts into a single ground surface polygon
            df_building = df_building.dissolve(by = 'dissolve_column')

            # write the geometry of the ground surface polygon in WKT 
            geom_wkt = df_building.loc[0, :].geometry.wkt

            # Return the ground surface polygon
            return geom_wkt
    
        except:
            print('Problem with a geometry - returned nan.')
            return np.nan
    
    else:
        return np.nan




def citygml_to_df(cityGML_buildings, cityGML_root, file_info, crs, bbox = False):

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
    
    # add column for height bbox if need
    if bbox == True:
       columns.insert(2,'height_bbox')

    # create an empty dataframe
    df = pd.DataFrame(np.nan, index = range(0, len(cityGML_buildings)), columns = columns) 
    
    # iterate over the CityGML buildings
    for i, building in enumerate(tqdm(cityGML_buildings)):
    
        # extract the id of the building
        idn = building.get("{"+cityGML_root.nsmap['gml']+"}id")

        # store the id in the dataframe
        df.loc[i, 'id'] = idn
        
        # extract the building heights as a list
        # note: we use a list here because sometimes buidling parts are written as
        # <bldg:consistsOfBuildingPart> and each has a <bldg:measuredHeight>
        list_heights = building.findall('.//bldg:measuredHeight', cityGML_root.nsmap)

        # if there is no height, save height equals na
        if len(list_heights) == 0:

            df.loc[i, 'height_measured'] = np.nan
        
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

            # store the max height in the dataframe
            df.loc[i, 'height_measured'] = max(list_heights_float)


        # if parameter set to true, also compute the height using the bounding box
        if bbox == True:

            # compute and store the height with the bbox method
            df.loc[i, 'height_bbox'] = bbox_height_calculator(building, cityGML_root)


        # extract all ground surface polygons for the building
        ground_geoms_list = building.findall('.//bldg:GroundSurface//gml:posList', cityGML_root.nsmap)

        # convert the citygml string to a wkt polygon
        ground_polygon_wtk = poly_converter(ground_geoms_list = ground_geoms_list, crs = crs) 
        
        # store the final ground polygon for the building in the geometry column
        df.loc[i, 'geometry'] = ground_polygon_wtk
              
    # save the name of the source file
    df['country'] = file_info[0]
    df['region'] = file_info[1]
    df['city'] = file_info[2]
    df['district'] = file_info[3]    
    df['source file'] = file_info[4]
    
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

