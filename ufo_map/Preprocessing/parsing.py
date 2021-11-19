import numpy as np 
import pandas as pd
import geopandas as gpd
from lxml import etree
from shapely.geometry import Polygon
from shapely.ops import unary_union


pd.options.mode.chained_assignment = None

### SHP

def calc_height_shp(walls_gdf,id_col):
    '''
    Compute building heights per building based on wall geometries, from a GeoDataFrame
    containing only walls geometries and a common id per building.
    
    Returns a Series of the heights as float, and indexed by id.
    
    ''' 
    h = [[x[-1] for x in list(poly.exterior.coords)] for poly in walls_gdf['geometry']]
    walls_gdf['h_min'] = [min(x) for x in h]
    walls_gdf['h_max'] = [max(x) for x in h]
    s_min = walls_gdf.groupby([id_col])['h_min'].min()
    s_max = walls_gdf.groupby([id_col])['h_max'].max()
    return(s_max.subtract(s_min))



def walls_to_height_shp(gdf,ID,elem_shp):
    '''
    Returns a GeoDataFrame filterting only building footprints from a GeoDataFrame gdf 
    containing semantically labelled building parts as hyperplanes in a 3D space, 
    and computes the max wall height as an additional column (float). 

    Takes as other inputs a three-element list elem_shp where: 
    * elem_shp[0] is the column differenciating building types, 
    * elem_shp[1] the str value for the footprint 
    * elem_shp[3] the str value for the walls.     

    and ID, the column of the building id.

    '''
    footprints = gdf[gdf[elem_shp[0]] == elem_shp[1]].dissolve(by=ID,as_index=False)
    walls = gdf[gdf[elem_shp[0]] == elem_shp[2]]
    height = calc_height_shp(walls,ID)
    return(footprints.merge(height.rename('height'),left_on=ID,right_index=True))



### GML

def get_bldg_elements(gml,gml_root,bldg_elem):
    '''
    Returns a list of xml elements corresponding to individual buildings.
    '''
    return(gml.findall(".//{}".format(bldg_elem),gml_root.nsmap))



def get_ids(bldg_elem_list,gml_root):
    '''
    Returns a list of buildings ids, assuming they are stored as an
    attribute of building element, as 'gml:id'.
    '''
    return([elem.attrib['{'+gml_root.nsmap['gml']+'}'+'id'] for elem in bldg_elem_list])



def list_elem_to_max(elem_list):
    '''
    Converts a list of elements containing a float value as text to a max float.
    '''
    for idx,elem in enumerate(elem_list):
        if elem!='' and elem.text is not None: elem_list[idx] = float(elem.text)
        else: elem_list[idx] = np.nan
    return(max(elem_list))



def get_var_attrib(var_elem,bldg_elem_list,gml_root):
    '''
    Returns a list of atributes e.g. heights or number of floors as float, from a list of building elements
    given that the attributes are encoded in the gml file as text in an element e.g. 'gml:measured_height'. 
    The function searches for all elements within a building and takes the max.

    Warning:
    - when <bldg:bla>text</bldg:bla>, var_elem should be 'bla';
    - when <gen:str_or_intAttribute name="bla">
                <gen:value>text</gen:value>
        var_elem should be 'gen:str_or_intAttribute/[@name="bla"]/gen:value'
    '''
    list_h = [elem.findall(".//{}".format(var_elem),gml_root.nsmap) for elem in bldg_elem_list]
    return([list_elem_to_max(elem_list) for elem_list in list_h])



def get_uni_attrib(str_elem,bldg_elem_list,gml_root):
    '''
    Returns a list of building attributes encoded as text in a children building element, in cases where 
    there is a unique value relevant per building e.g. type.

    Warning:
    - when <bldg:bla>text</bldg:bla>, var_elem should be 'bla';
    - when <gen:str_or_intAttribute name="bla">
                <gen:value>text</gen:value>
        var_elem should be 'gen:str_or_intAttribute/[@name="bla"]/gen:value'
    '''
    return([elem.find(".//{}".format(str_elem),gml_root.nsmap).text for elem in bldg_elem_list])



def poly_converter(list_poly_elem,mode='3d'):
    '''
    Converts a list of geometry elements (pos:Polygon) into a single Shapely polygon
    or multipolygon.

    Choose whether 2D or 3D is given as input.
    '''
    list_poly = [None]*len(list_poly_elem)
    for idx,poly in enumerate(list_poly_elem):
        exp_poly_float = [float(s) for s in poly.text.split()]
        if mode=='2d':
            list_poly[idx] = Polygon(zip(exp_poly_float[0::2], exp_poly_float[1::2]))
        else: 
            list_poly[idx] = Polygon(zip(exp_poly_float[0::3], exp_poly_float[1::3]))
    return(unary_union(list_poly))



def point_converter(list_poly_elem):
    '''
    Converts a list of points elements (pos:Point) into a single Shapely polygon or multipolygon.
    
    TODO: check why there are invalid polygons.

    '''
    lat = lon = [None]*len(list_poly_elem)
    for idx,poly in enumerate(list_poly_elem):
        poly_float = [float(s) for s in poly.text.split()]
        lat[idx],lon[idx] = poly_float[0],poly_float[1]
    return(Polygon(zip(lat,lon)))



def surface_to_height(meshes,sngl=False,av=False):
    '''
    Compute the height as a float for a building as the difference between 
    the lowest and highest z values across all walls of the building.
    
    By default (sngl=False), multiple surfaces are considered, otherwise, only 
    one surface is, e.g. when idenfying ground polygon in case of gml:Solid.
    
    Option to return the mean of the values considered (av=True).
    '''
    if sngl: meshes = [float(item) for item in meshes.text.split()[2::3]]
    else:
        meshes = [item.text.split()[2::3] for item in meshes]
        meshes = [float(item) for sublist in meshes for item in sublist]
    if av: return(round(max(meshes)-min(meshes),2), np.mean(meshes))
    else: return(round(max(meshes)-min(meshes),2))


def get_heights_wall(wall_elem,bldg_elem_list,gml_root):
    '''
    Returns a list of building heights as floats, from a list of building elements
    computed as the difference between the lowest and highest z values across 
    all walls of the building.
    '''
    list_wall_elems = [elem.findall(".//{}".format(wall_elem),gml_root.nsmap) \
                   for elem in bldg_elem_list]
    return([surface_to_height(elem) for elem in list_wall_elems])



def ground_surf_solid_idx(list_surf_elems):
    '''
    Returns the index of the ground surface for a list of surface elements
    where the ground surface is identified by having both the min difference
    in z coordinates (flat surface) and the lowest average z coordinate (to
    distinguish from flat roof). 
    '''
    x,y = zip(*[surface_to_height(elem,sngl=True,av=True) \
                for elem in list_surf_elems]) 
    x,y = np.array(x), np.array(y)
    return([item for item in np.argwhere(x==x.min()) if item in np.argwhere(y==y.min())][0][0])



def get_footprints(ft_elem,bldg_elem_list,gml_root,pt=False,solid=None,mode='3d'):
    '''
    Returns building footprint polygons for each building from a list of building element,
    as a list of Shapely polygons or multipolygons. 

    The point (pt) option enables to parse list of points instead of lists of meshes.

    The solid option enables to retrieve footprint polygons that are not semantically
    labelled, by identifying them with the `get_ground_solid_elem` function.
    
    Choose whether 2D or 3D is given as input via parameter `mode`.
    
    '''
    list_foot_elems = [elem.findall(".//{}".format(ft_elem),gml_root.nsmap) for elem in bldg_elem_list]
    if solid=='solid':
        return([poly_converter([elem[ground_surf_solid_idx(elem)]]) for elem in list_foot_elems])
    else:
        if pt:
            return([point_converter(elem) for elem in list_foot_elems])
        else:
            return([poly_converter(elem,mode=mode) for elem in list_foot_elems])



def is_roof_flat_or_slanted(roof_elem):
    '''
    Assesses if roof element is flat (height differencial is 0) or slanted otherwise.
    Returns: str
    '''
    roof_z = [float(s) for s in roof_elem.text.split()[2::3]]
    if min(roof_z)-max(roof_z)== 0: return('flat roof')
    else: return('slanted roof')


def get_roof_type_from_lod2(ft_elem,bldg_elem_list,gml_root):
    '''
    Assesses for a list of roofs whether they are flat or slanted.
    The input should be a list of list of roof elements per roof from LoD2 data.
    In case of a single roof element, the function inspects it directly, otherwise,
    it inspects the roof element with the largest area. 
    
    Returns: list of str
    '''
    # get roof elements
    list_roof_elems = [elem.findall(".//{}".format(ft_elem),gml_root.nsmap) for elem in bldg_elem_list]
    roof_type = [None]*len(list_roof_elems)
    
    for idx,roof in enumerate(list_roof_elems):
        # if single element go ahead
        if len(roof)==1: roof_type[idx] = is_roof_flat_or_slanted(roof[0])
        
        elif len(roof)>1:
            # otherwise, lets get first element with the largest area
            roof_elem_areas = [None]*len(roof)
            for idx2,roof_elem in enumerate(roof):
                coords = [float(s) for s in roof_elem.text.split()]
                roof_elem_areas[idx2] = Polygon([coords[i:i+3] for i in range(0, len(coords), 3)]).area
            roof_type[idx] = is_roof_flat_or_slanted(roof[np.argmax(roof_elem_areas)])
        
        else: sys.exit('Looks like we did not fetch roof elements correctly previously.')
    
    return(roof_type)