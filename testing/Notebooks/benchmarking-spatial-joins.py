import geopandas as gpd
import sys
import time

>>> path_root = r'C:/Users/miln/tubCloud/Work-in-progress/building-project/git-ufo-map'
sys.path.append(path_root)
from ufo_map.Utils.helpers import import_csv_w_wkt_to_gdf


>>> path = r'C:\Users\miln\tubCloud\Work-in-progress\building-project\old_git\ML_paper\Data\Data samples\1.3-add_osm_buildings\Udine_buildings.csv'

crs = 7794
gdf = import_csv_w_wkt_to_gdf(path,crs)

gdf_sindex = gdf.sindex
geometries = gdf.geometry


print('sindex square 100')
start = time.time()
indexes_right = []
for index,geometry in enumerate(geometries):
    print(index)
    indexes_right.append(list(gdf_sindex.intersection(geometry.centroid.buffer(100).bounds)))
end = time.time()
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(indexes_right[0])

print("\n=====================================\n")

print('sindex square 500')
start = time.time()
indexes_right = []
for index,geometry in enumerate(geometries):
    print(index)
    indexes_right.append(list(gdf_sindex.intersection(geometry.centroid.buffer(500).bounds)))
end = time.time()
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(indexes_right[0])

print("\n=====================================\n")

print('sindex round 100')
start = time.time()
indexes_right = []
for index,geometry in enumerate(geometries):
    print(index)
    buffer = geometry.centroid.buffer(100)
    possible_matches_index = list(gdf_sindex.intersection(buffer.bounds))
    possible_matches = gdf.loc[possible_matches_index] 
    indexes_right.append(possible_matches[possible_matches.intersects(buffer)].index)
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(indexes_right[0])

print("\n=====================================\n")

print('sindex round 500')
start = time.time()
indexes_right = []
for index,geometry in enumerate(geometries):
    print(index)
    buffer = geometry.centroid.buffer(500)
    possible_matches_index = list(gdf_sindex.intersection(buffer.bounds))
    possible_matches = gdf.loc[possible_matches_index] 
    indexes_right.append(possible_matches[possible_matches.intersects(buffer)].index)
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(indexes_right[0])

print("\n=====================================\n")

print('francois 100')
start = time.time()
buffer_series = gdf.geometry.centroid.buffer(100).values
buffer_gdf = gpd.GeoDataFrame(geometry=buffer_series)
building_only_gdf = gpd.GeoDataFrame(geometry=gdf.geometry)
joined_gdf = gpd.sjoin(buffer_gdf, building_only_gdf, how="left", op="intersects")
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(joined_gdf.loc[0].index_right.values)

print("\n=====================================\n")

print('francois 500')
buffer_series = gdf.geometry.centroid.buffer(500).values
buffer_gdf = gpd.GeoDataFrame(geometry=buffer_series)
building_only_gdf = gpd.GeoDataFrame(geometry=gdf.geometry)
joined_gdf = gpd.sjoin(buffer_gdf, building_only_gdf, how="left", op="intersects")
last = divmod(end - start, 60)
print('{} minutes {} seconds'.format(last[0],last[1])) 
print(joined_gdf.loc[0].index_right.values)