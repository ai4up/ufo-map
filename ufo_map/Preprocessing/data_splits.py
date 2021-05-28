from shapely.geometry import Point, MultiPoint, Polygon
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt


def make_pizza(df, do_plot=False, share=0.2, angle=2*np.pi/2):
    """
    cuts a pizza slice out of df based on geometry
    If row is element of slice the entry in columns "pizza" is "test"
    else train. 
    In:
        df: geopandas.GeoDataFrame; needs geometry column with one shapely.geometry.Point per row
        do_plot: bool; plots if True
        share: float; share of examples used for testing
        angle: float; angle of center of slice
    Out:
        updated GeoDataFrame
    """
    
    center = MultiPoint(df.geometry).centroid

    def assign(point, center, angle):
    
        north = np.array([np.cos(angle), np.sin(angle)])
        
        vector = np.array([point.x - center.x, point.y - center.y])
        angle = np.arccos(np.inner(vector, north) / np.linalg.norm(vector))
    
        return angle
        
    
    df["pizza"] = df.geometry.apply(lambda entry: assign(entry, center, angle))
    
    def ecdf(data):
        """ Compute ECDF """
        x = np.sort(data)
        n = x.size
        y = np.arange(1, n+1) / n
        return(x,y)
    
    x, cdf = ecdf(df["pizza"])
    
    threshold = len(y[y < share])
    threshold = x[threshold]
    
    def assign_task(entry, threshold):
        if entry < threshold:
            return "test"
        else:
            return "train"
        
    df["pizza"] = df["pizza"].apply(lambda entry: assign_task(entry, threshold))
    
    if do_plot:
        fig, ax = plt.subplots(1, 1, figsize=(7,7))
        df.plot(ax=ax, column="pizza")
        plt.show()
        
    return df



if __name__ == "__main__":
    
    n = 10000
    x = np.random.rand(n)
    y = np.random.rand(n)
    df = gpd.GeoDataFrame({"idx": range(n)}, geometry=gpd.points_from_xy(x, y))
    df = make_pizza(df, do_plot=True, share=0.05)
