"""
Created on 4/2/2021

@author: Nikola

TODO: add support for features on which land use a point e.g. trip origin is. 
"""

def building_in_ua(geometries,ua_sindex,geometries_ua,classes):
    '''
    Warning: this will break if a building is only in road...
    '''
    
    list_building_in_ua = [None] * len(geometries)

    for index,geometry in enumerate(geometries):
        
        # get buildings possibly interesecting
        indexes_right = list(ua_sindex.intersection(geometry.bounds))
                
        # get the intersection area of each potential UA poly
        inter_areas = [geometries_ua[i].intersection(geometry).area for i in indexes_right]
                
        # get the class of the max intersection
        list_building_in_ua[index] = [classes[i] for i in indexes_right][inter_areas.index(max(inter_areas))]
    
    return(list_building_in_ua)



def get_indexes_right_bbox(geometries,ua,buffer_size):
    '''
    Return list of list of indexes of lu polygons intersecting each bounding box, 
    and list of the bounding box geometries
    '''
    # initialize output lists
    bbox_geom = [None]*len(geometries)
    indexes_right = [None]*len(geometries)  
        
    for index,geometry in enumerate(geometries):

        # get bounding box as tuple
        bbox = geometry.centroid.buffer(buffer_size).bounds
        # get list polygons intersecting
        indexes_right[index] = list(ua_sindex.intersection(bbox))
        # get bounding box geometry
        bbox_geom[index] = (Polygon([(bbox[0],bbox[1]),(bbox[0],bbox[3]),\
                                     (bbox[2],bbox[3]),(bbox[2],bbox[1])]))

    return(indexes_right,bbox_geom)



def get_areas_within_buff(keys,values,all_keys,road_area):
    '''
    Returns clean list of areas per land use class from all lu polygons found in bbox.
    '''
    # initialize container
    res = defaultdict(list)
    
    # create dictionary lu class: polygon areas summed for this lu
    for i, j in zip(keys, values): res[i].append(j)
    res = {key: sum(res[key]) for key in dict(res).keys()}
    
    # get list of areas including 0 if the lu class is not here
    res = [res[key] if key in res.keys() else 0 for key in all_keys]
    
    # add road area
    res.append(road_area)
    
    return(res)


def ua_areas_in_buff(geometries,classes,ua_sindex,buffer_size,all_keys):
    '''
    Returns a dataframe with features within a bounding box.
    '''
    # remove lu road for the land classe names list
    all_keys_no_road = [x for x in all_keys if x != 'lu_roads']

    # get lu polygons interesecting the bbox and the bbox geoms
    indexes_right,bbox_geom = get_indexes_right_bbox(geometries,ua_sindex,buffer_size)

    # initialize the list of areas list for each building/bbox
    areas_in_buff = []

    for idx,group in enumerate(indexes_right):

        # get a list of the areas of each lu class in bbox
        inter_area = [geometries_ua[i].intersection(bbox_geom[idx]).area for i in group]

        # get a list of the lu classe names in bbox
        classes_in_buff = [classes[i] for i in group]
        
        # compute the area covered by roads in bbox
        road_area = pow(buffer_size*2,2) - sum(inter_area)

        # get clean list with areas per lu class summed up + lu road
        areas_in_buff.append(get_areas_within_buff(classes_in_buff,inter_area,all_keys_no_road,road_area))

    # list of the columns names specific to buffer size
    all_keys_buff_size = [item+'_within_buffer_'+str(buffer_size) for item in all_keys_no_road+['lu_roads']]

    return(pd.DataFrame(data = areas_in_buff, columns = all_keys_buff_size))



def check_all_dummies(all_keys,output):
    '''
    Add new columns with 0s if there were not all land classes (e.g. when running on subset).
    '''
    for col in ['bld_in_'+item for item in all_keys]:
        if col not in output.columns:
            output[col] = 0
    return(output)



def features_urban_atlas(gdf,ua,buffer_sizes,typologies,building_mode=True):
    '''
    Compute urban atlas features! Returns a dataframe with all the features for the land use 
    classes provided in the typologies dictionary.
    
    Features within bounding boxes and for the building of interest.
    
    TODO: add support for points as object of interest.
    '''
    # get the name of the different land use classes
    all_keys = list(set(typologies.values()))
    
    # get list of inputs for calculations
    geometries = list(gdf.geometry)
    geometries_ua = list(ua.geometry)
    classes = list(ua.class_2012)
    
    # get spatial index of buildings gdf
    ua_sindex = ua.sindex
    
    # initialize output df
    output = pd.DataFrame()
    
    if building_mode:
        
        print('Building in UA...')
        
        # get an array of the land use class in which the building falls
        building_in_ua_list = building_in_ua(geometries,ua_sindex,geometries_ua,classes)
        
        # one-hot encoding of the array 
        output = pd.get_dummies(pd.Series(building_in_ua_list), prefix='bld_in')
        output = check_all_dummies(all_keys,output)
        
    for buffer_size in buffer_sizes:
        
        print('UA in buffer of size {}...'.format(buffer_size))
        
        # get dataframe with areas covered by land use cases within bounding box
        output_buff_size = ua_areas_in_buff(geometries,classes,ua_sindex,buffer_size,all_keys)
        
        output = pd.concat([output,output_buff_size], axis=1)
         
    return(output)        