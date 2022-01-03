import sys
sys.path.append('/p/projects/eubucco/git-ufo-map')

from ufo_map.Preprocessing.preproc_streets import *
from ufo_map.Utils.helpers import import_csv_w_wkt_to_gdf
import matplotlib.pyplot as plt
from importlib.metadata import version

print('geopandas')
print('osmnx')
print('momepy')

gdf = import_csv_w_wkt_to_gdf(r'XXX',crs=2169)
sbb = generate_sbb(gdf)

# expected:
# Will split roads:{0, 1, 2, 515, 4, 5, 1024, 1536, 8, 1538, 3591, 15, 4623, 1530, 2585, 3611, 
# 3619, 3620, 551, 552, 553, 555, 556, 557, 558, 559, 560, 4655, 62, 1602, 1093, 4170, 75, 1612,
# 1614, 1615, 1616, 2130, 2136, 90, 99, 2663, 105, 107, 4602, 1652, 3189, 633, 1659, 126, 2193, 
# 176, 189, 191, 193, 194, 195, 708, 712, 713, 202, 203, 205, 206, 207, 1231, 209, 722, 211, 723, 
# 213, 725, 215, 726, 217, 218, 219, 220, 1755, 222, 223, 224, 228, 229, 230, 231, 1767, 236, 2797, 
# 239, 4337, 244, 245, 246, 248, 3320, 3321, 4345, 1788, 2820, 2822, 1801, 1809, 1811, 3349, 1819, 
# 1820, 812, 4913, 308, 309, 4919, 314, 2366, 1856, 2371, 1348, 2372, 2373, 330, 2379, 1362, 1371, 
# 2402, 2408, 4971, 2415, 370, 2420, 2421, 2423, 2425, 890, 2426, 2427, 2944, 2964, 1432, 5017, 2471, 
# 4009, 1972, 956, 1473, 968, 4553, 4044, 2002, 983, 984, 4570, 4577, 488, 489, 492, 493, 4078, 1520, 
# 1522, 1524, 1527, 1528, 506, 1531, 4604, 1533, 1534}


fig, ax = plt.subplots(figsize=(10,10))
sbb.plot(ax=ax, color='grey')
gdf.plot(ax=ax)
plt.savefig('sbb_out.png')