import numpy as np 
import pandas as pd
import geopandas as gpd
from lxml import etree
from shapely.geometry import Polygon,GeometryCollection
from shapely.ops import unary_union
from shapely.geometry import Point
from statistics import mean


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
    return(footprints.merge(height.rename('computed_height'),left_on=ID,right_index=True))



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



def get_var_attrib(var_elem,bldg_elem_list,gml_root,dataset_name):
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
    
    if dataset_name == 'vantaa-gov':
        list_ = [] 
        for elem in bldg_elem_list:
            try: list_.append(list_elem_to_max(elem.findall(".//{}".format(var_elem),gml_root.nsmap)))
            except: 
                list_.append(np.nan)
        return(list_)
    else:
        list_h = [elem.findall(".//{}".format(var_elem),gml_root.nsmap) for elem in bldg_elem_list]
        return([list_elem_to_max(elem_list) for elem_list in list_h])



def get_uni_attrib(str_elem,bldg_elem_list,gml_root,dataset_name):
    '''
    Returns a list of building attributes encoded as text in a children building element, in cases where 
    there is a unique value relevant per building e.g. type.

    Warning:
    - when <bldg:bla>text</bldg:bla>, var_elem should be 'bla';
    - when <gen:str_or_intAttribute name="bla">
                <gen:value>text</gen:value>
        var_elem should be 'gen:str_or_intAttribute/[@name="bla"]/gen:value'
    '''
    if dataset_name == 'vantaa-gov':
        list_ = []
        for elem in bldg_elem_list:
            try:
                if elem.find(".//{}".format(str_elem),gml_root.nsmap)!= None:
                    list_.append(elem.find(".//{}".format(str_elem),gml_root.nsmap).text)  
                else: list_.append(None) 
            except:
                list_.append(None)
        return(list_)
    else:
        return([elem.find(".//{}".format(str_elem),gml_root.nsmap).text if elem.find(".//{}".format(str_elem),gml_root.nsmap)!= None else None for elem in bldg_elem_list])




def get_curr_use_attrib(var_elem,bldg_elem_list,gml_root,key):
    '''
    Returns a list of building current use attributes encoded as text in a children building element.
    So far, it is programmed for the cyprus case but can be adjusted later. 

    A: Felix
    D: 20.12.21

    '''
    # find all current use entries
    list_curr_use_full = ([elem.find(".//{}".format(var_elem),gml_root.nsmap) for elem in bldg_elem_list])
    
    if not None in list_curr_use_full:
        # if no None directly return list elems
        return [elem.attrib[key] for elem in list_curr_use_full if elem != None]
    else:
        # get attrib for all elements that are not None
        list_curr_use = [elem.attrib[key] for elem in list_curr_use_full if elem != None]
        # get indexes of list entries that have a current use value
        index_not_none = np.where(np.array(list_curr_use_full,dtype=object) != None)[0].tolist()
        # get str of current use and allocate to list
        for i_list,i_match in enumerate(index_not_none):
            # take current use out of link 
            # TODO: adjust if future parsing steps do not have links but simple str
            list_curr_use_full[i_match]=list_curr_use[i_list]
        return list_curr_use_full



def axis_order_confusion(list_poly_elem,input_crs):
    '''
        Checks if the gml coordinates are assigned as x,y or y,x.
        If y,x, returns confusion==True
    '''
    pt_cnfsn = [float(s) for s in list_poly_elem[0][0].text.split()]

    print(f"Initial CRS: {(pt_cnfsn[0], pt_cnfsn[1])}")
    
    pt_cnfsn = gpd.GeoDataFrame(geometry=gpd.GeoSeries(Point((pt_cnfsn[0], pt_cnfsn[1]))),crs=input_crs).to_crs(4326)
    print(f"WGS84: {pt_cnfsn.geometry[0].wkt}")
    
    if pt_cnfsn.geometry.x[0] > pt_cnfsn.geometry.y[0]:
        print("Axis order confusion")
        return(True)

    else: return(False)



def poly_converter(list_poly_elem,confusion=False,mode='3d'):
    '''
    Converts a list of geometry elements (pos:Polygon) into a single Shapely polygon
    or multipolygon.

    Choose whether 2D or 3D is given as input.

    Returns: Tuple with 
                - Shapely polygon
                - Boolean
    '''
    # initialise marker that checks if elem contains invalid geom
    bool_is_invalid = False
    
    if confusion: lat,lon = 1,0
    else: lat,lon = 0,1
    
    #intialise list
    list_poly = [None]*len(list_poly_elem)
    for idx,poly in enumerate(list_poly_elem):
        exp_poly_float = [float(s) for s in poly.text.split()]

        if mode=='2d':
            try:
                list_poly[idx] = Polygon(zip(exp_poly_float[lat::2], exp_poly_float[lon::2]))
            except:
                list_poly[idx] = GeometryCollection()
                print('WARNING (3)! unknown issue')
                print(exp_poly_float)
            # Check for invalid polygons and correct
            if list_poly[idx].is_valid==False:
                if list_poly[idx].area > 0:
                    print('WARNING (1)! invalid polygon detected and fixed')
                    # buffer fix taken from: https://coderedirect.com/questions/331645/fix-invalid-polygon-in-shapely
                    list_poly[idx] = list_poly[idx].buffer(0)
                    # set invalid marker to True
                    bool_is_invalid = True              

        elif mode=='3d': 
            try:
                list_poly[idx] = Polygon(zip(exp_poly_float[lat::3], exp_poly_float[lon::3]))
            except:
                list_poly[idx] = GeometryCollection()
                print('Warning: Broken geom. Empty geom created.')

            # Check for invalid polygons and correct
            if list_poly[idx].is_valid==False:
                if list_poly[idx].area > 1:
                    print(list_poly[idx].area)
                    print('WARNING (1)! invalid polygon detected and fixed')
                    # buffer fix taken from: https://coderedirect.com/questions/331645/fix-invalid-polygon-in-shapely
                    list_poly[idx] = list_poly[idx].buffer(0)
                    # set invalid marker to True
                    bool_is_invalid = True   

        else: sys.exit('Choose 2d or 3d.')
    # To check where we have false polygons uncomment the following
    #print([p.is_valid for p in list_poly])        
    return(unary_union(list_poly), bool_is_invalid)



def point_converter(list_poly_elem):
    '''
    Converts a list of points elements (pos:Point) into a single Shapely polygon.
    
    '''
    lat = [None]*len(list_poly_elem)
    lon = [None]*len(list_poly_elem)
    for idx,poly in enumerate(list_poly_elem):
        poly_float = [float(s) for s in poly.text.split()]
        lon[idx],lat[idx] = poly_float[0],poly_float[1]
    return(Polygon(zip(lon,lat)))



def poly_converter_hamburg(list_poly_elem,gml_root):
    '''
        Converts a list of footprint parts given as gml:pos within gml:LinearRing
        into a single Shapely Polygon or MultiPolygon per building.
    '''
    list_poly = [elem.findall(".//{}".format('gml:pos'),gml_root.nsmap) 
                 for elem in list_poly_elem]
    
    return(unary_union([point_converter(elem) for elem in list_poly]))



def surface_to_height(meshes,sngl=False,av=False,roof=False,meshes_roof=None):
    '''
    Compute the height as a float for a building as the difference between 
    the lowest and highest z values across all walls of the building.
    
    By default (sngl=False), multiple surfaces are considered, otherwise, only 
    one surface is, e.g. when idenfying ground polygon in case of gml:Solid.
    
    Option to return the mean of the values considered (av=True).

    Roof=True option computes additionally the min height of the roof elements.

    Returns:
        - if av=True: the height between the highest and lowest point in the meshes
                      and the average height of meshes as floats
        - if roof=True: the height between the lowest wall point (meshes) and the
                        lowest roof point (meshes_roof) 
        - else: the height between the highest and lowest point in the meshes
                as a float

    '''
    if sngl: meshes = [float(item) for item in meshes.text.split()[2::3]]
    else:
        meshes = [item.text.split()[2::3] for item in meshes]
        meshes = [float(item) for sublist in meshes for item in sublist]
    if av: return(round(max(meshes)-min(meshes),2), np.mean(meshes))
    elif roof: 
        meshes_roof = [item.text.split()[2::3] for item in meshes_roof]
        meshes_roof = [float(item) for sublist in meshes_roof for item in sublist]
        try: 
            height = round(min(meshes_roof)-min(meshes),2)
        except:
            print('Missing part in roof or wall')
            height = np.nan 
        return(height)
    else: 
        try: 
            height = round(max(meshes)-min(meshes),2)
        except:
            print('Missing part in roof or wall')
            height = np.nan 
        return(height)
        


def get_max_heights_wall(bldg_elem_list,gml_root,wall_elem='bldg:WallSurface//gml:posList'):
    '''
    Returns a list of building heights as floats, from a list of building elements
    computed as the difference between the lowest and highest z values across 
    all walls of the building.
    '''
    list_wall_elems = [elem.findall(".//{}".format(wall_elem),gml_root.nsmap) \
                   for elem in bldg_elem_list]
    return([surface_to_height(elem) for elem in list_wall_elems])



def get_min_heights_roof(bldg_elem_list,gml_root,roof_elem='bldg:RoofSurface//gml:posList',wall_elem='bldg:WallSurface//gml:posList'):
    '''
    Returns a list of building heights as floats, from a list of building elements
    computed as the difference between the lowest and highest z values across 
    all walls of the building.
    '''
    list_roof_elems = [elem.findall(".//{}".format(roof_elem),gml_root.nsmap) \
                   for elem in bldg_elem_list]
    list_wall_elems = [elem.findall(".//{}".format(wall_elem),gml_root.nsmap) \
                   for elem in bldg_elem_list]
    return([surface_to_height(list_wall_elems[i], roof=True, meshes_roof=list_roof_elems[i]) \
        for i in range(len(list_roof_elems))])



# def ground_surf_solid_idx(list_surf_elems):
#     '''
#     Returns the index of the ground surface for a list of surface elements
#     where the ground surface is identified by having both the min difference
#     in z coordinates (flat surface) and the lowest average z coordinate (to
#     distinguish from flat roof). 
#     '''
#     dz,av_z = zip(*[surface_to_height(elem,sngl=True,av=True) \
#                 for elem in list_surf_elems]) 
#     dz,av_z = np.array(dz), np.array(av_z)

#     ft_idxs = [item for item in np.argwhere(dz==dz.min()) if item in np.argwhere(av_z==av_z.min())]    

#     if ft_idxs != []: return(ft_idxs[0][0])
#     else: 
#         try: 
#             print('no clear footprint')
#             return([item for item in np.argwhere(dz==dz.min()) if av_z[item] < mean(av_z)][0][0])
#         except: 
#             print(dz,av_z)    


# def ground_surf_solid_idx2(list_surf_elems):
#     '''
#     Returns the index of the ground surface for a list of surface elements
#     where the ground surface is identified by having both the min difference
#     in z coordinates (flat surface) and the lowest average z coordinate (to
#     distinguish from flat roof). 
#     '''
#     dz,av_z = zip(*[surface_to_height(elem,sngl=True,av=True) \
#                 for elem in list_surf_elems]) 
#     dz,av_z = np.array(dz), np.array(av_z)

    
#     dz_0 = np.argwhere(dz==0) # indexes of horizontal elements
    
#     if len(dz_0) == 1: return(dz_0[0][0]) # there is only one footprint
    
#     elif len(dz_0) > 1: # there are several horizontal elems, check the lowest
#         d = {j: av_z[j] for j in [i[0] for i in np.argwhere(dz==0)]}
#         return(min(d, key=d.get))    
#     else: return 'no ft'



def get_footprints(ft_elem,bldg_elem_list,gml_root,input_crs,dataset_name=None,pt=False,
    # solid=None,
    mode='3d'):
    '''
    Returns building footprint polygons for each building from a list of building element,
    as a list of Shapely polygons or multipolygons. 

    The point (pt) option enables to parse list of points instead of lists of meshes.

    The solid option enables to retrieve footprint polygons that are not semantically
    labelled, by identifying them with the `get_ground_solid_elem` function.
    
    Choose whether 2D or 3D is given as input via parameter `mode`.

    '''
    list_foot_elems = [elem.findall(".//{}".format(ft_elem),gml_root.nsmap) for elem in bldg_elem_list]
    
    # check for confusion (TODO: move these conditions inside the axis_order_confusion function)
    if len(list_foot_elems)>0 and len([item for item in list_foot_elems if item != []])==0:
        confusion = False
    elif len(list_foot_elems)>0 and list_foot_elems[0] ==[]:
        confusion = axis_order_confusion([item for item in list_foot_elems if item != []],input_crs)
    elif len(list_foot_elems)>0: confusion = axis_order_confusion(list_foot_elems,input_crs)
    else: confusion = False 

    # # run geom converters
    # if solid=='solid':
    #     list_ = [None] * len(list_foot_elems)
    #     for idx,elem in enumerate(list_foot_elems):
    #         gr_idx = ground_surf_solid_idx(elem)
    #         if gr_idx == 'no ft' : 
    #             print(f'No ft for {idx}')
    #             list_[idx] = GeometryCollection()
    #         else: list_[idx] = poly_converter([elem[gr_idx]])
    #     return(list_)
    
    if dataset_name=='hamburg-gov': 
        return([poly_converter_hamburg(elem,gml_root) for elem in list_foot_elems])

    else:
        if pt:
            return([point_converter(elem) for elem in list_foot_elems])
        else:
            return([poly_converter(elem,confusion,mode=mode) for elem in list_foot_elems])



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