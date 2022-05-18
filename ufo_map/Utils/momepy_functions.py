"""
Created on Tue Mar 24 15:37:57 2020

@author: miln
"""

import numpy as np
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon
import math
import random

##############################################
##############################################
# THESE ARE FUNCTIONS COPY-PASTED FROM
# THE LIBRARY MOMEPY, BECAUSE THEY
# REQUIRE INTERNET ACCESS, MOMEPY CANNOT
# BE USED DIRECTLY ON THE CLUSTER.
# FOR THE RELEASE, CREATE A COPY WITH
# ORIGINALS FUNCTION.
##
##
# (END MOMEPY)
##
##############################################
##############################################


def _azimuth(point1, point2):
    """azimuth between 2 shapely points (interval 0 - 180)"""
    angle = np.arctan2(point2[0] - point1[0], point2[1] - point1[1])
    return np.degrees(angle) if angle > 0 else np.degrees(angle) + 180


def _longest_axis(points):
    circ = _make_circle(points)
    return circ[2] * 2


def _make_circle(points):
    # Convert to float and randomize order
    shuffled = [(float(x), float(y)) for (x, y) in points]
    random.shuffle(shuffled)

    # Progressively add points to circle or recompute circle
    c = None
    for (i, p) in enumerate(shuffled):
        if c is None or not _is_in_circle(c, p):
            c = _make_circle_one_point(shuffled[: i + 1], p)
    return c


def _make_circle_one_point(points, p):
    c = (p[0], p[1], 0.0)
    for (i, q) in enumerate(points):
        if not _is_in_circle(c, q):
            if c[2] == 0.0:
                c = _make_diameter(p, q)
            else:
                c = _make_circle_two_points(points[: i + 1], p, q)
    return c


def _make_circle_two_points(points, p, q):
    circ = _make_diameter(p, q)
    left = None
    right = None
    px, py = p
    qx, qy = q

    # For each point not in the two-point circle
    for r in points:
        if _is_in_circle(circ, r):
            continue

        # Form a circumcircle and classify it on left or right side
        cross = _cross_product(px, py, qx, qy, r[0], r[1])
        c = _make_circumcircle(p, q, r)
        if c is None:
            continue
        elif cross > 0.0 and (
            left is None
            or _cross_product(px, py, qx, qy, c[0], c[1])
            > _cross_product(px, py, qx, qy, left[0], left[1])
        ):
            left = c
        elif cross < 0.0 and (
            right is None
            or _cross_product(px, py, qx, qy, c[0], c[1])
            < _cross_product(px, py, qx, qy, right[0], right[1])
        ):
            right = c

    # Select which circle to return
    if left is None and right is None:
        return circ
    if left is None:
        return right
    if right is None:
        return left
    if left[2] <= right[2]:
        return left
    return right


def _make_circumcircle(p0, p1, p2):
    # Mathematical algorithm from Wikipedia: Circumscribed circle
    ax, ay = p0
    bx, by = p1
    cx, cy = p2
    ox = (min(ax, bx, cx) + max(ax, bx, cx)) / 2.0
    oy = (min(ay, by, cy) + max(ay, by, cy)) / 2.0
    ax -= ox
    ay -= oy
    bx -= ox
    by -= oy
    cx -= ox
    cy -= oy
    d = (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)) * 2.0
    if d == 0.0:
        return None
    x = (
        ox
        + (
            (ax * ax + ay * ay) * (by - cy)
            + (bx * bx + by * by) * (cy - ay)
            + (cx * cx + cy * cy) * (ay - by)
        )
        / d
    )
    y = (
        oy
        + (
            (ax * ax + ay * ay) * (cx - bx)
            + (bx * bx + by * by) * (ax - cx)
            + (cx * cx + cy * cy) * (bx - ax)
        )
        / d
    )
    ra = math.hypot(x - p0[0], y - p0[1])
    rb = math.hypot(x - p1[0], y - p1[1])
    rc = math.hypot(x - p2[0], y - p2[1])
    return (x, y, max(ra, rb, rc))


def _cross_product(x0, y0, x1, y1, x2, y2):
    return (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)


_MULTIPLICATIVE_EPSILON = 1 + 1e-14


def _is_in_circle(c, p):
    return (
        c is not None
        and math.hypot(p[0] - c[0], p[1] - c[1]) <= c[2] * _MULTIPLICATIVE_EPSILON
    )


def _make_diameter(p0, p1):
    cx = (p0[0] + p1[0]) / 2.0
    cy = (p0[1] + p1[1]) / 2.0
    r0 = math.hypot(cx - p0[0], cy - p0[1])
    r1 = math.hypot(cx - p1[0], cy - p1[1])
    return (cx, cy, max(r0, r1))


class momepy_Perimeter:
    """
    Calculates perimeter of each object in given GeoDataFrame. It can be used for any
    suitable element (building footprint, plot, tessellation, block).
    It is a simple wrapper for geopandas `gdf.geometry.length` for the consistency of momepy.
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects to analyse
    Attributes
    ----------
    series : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    Examples
    --------
    >>> buildings = gpd.read_file(momepy.datasets.get_path('bubenec'), layer='buildings')
    >>> buildings['perimeter'] = momepy.Perimeter(buildings).series
    >>> buildings.perimeter[0]
    137.18630991119903
    """

    def __init__(self, gdf):
        self.gdf = gdf
        self.series = self.gdf.geometry.length


class momepy_LongestAxisLength:
    """
    Calculates the length of the longest axis of object.
    Axis is defined as a diameter of minimal circumscribed circle around the convex hull.
    It does not have to be fully inside an object.
    .. math::
        \\max \\left\\{d_{1}, d_{2}, \\ldots, d_{n}\\right\\}
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects to analyse
    Attributes
    ----------
    series : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    Examples
    --------
    >>> buildings['lal'] = momepy.LongestAxisLength(buildings).series
    >>> buildings.lal[0]
    40.2655616057102
    """

    def __init__(self, gdf):
        self.gdf = gdf
        hulls = gdf.geometry.convex_hull
        self.series = hulls.apply(lambda hull: _longest_axis(hull.exterior.coords))


class momepy_Elongation:
    """
    Calculates elongation of object seen as elongation of its minimum bounding rectangle.
    .. math::
        {{p - \\sqrt{p^2 - 16a}} \\over {4}} \\over {{{p} \\over {2}} - {{p - \\sqrt{p^2 - 16a}} \\over {4}}}
    where `a` is the area of the object and `p` its perimeter.
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects
    Attributes
    ----------
    e : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    References
    ----------
    Gil J, Montenegro N, Beirão JN, et al. (2012) On the Discovery of
    Urban Typologies: Data Mining the Multi-dimensional Character of
    Neighbourhoods. Urban Morphology 16(1): 27–40.
    Examples
    --------
    >>> buildings_df['elongation'] = momepy.Elongation(buildings_df).series
    >>> buildings_df['elongation'][0]
    0.9082437463675544
    """

    def __init__(self, gdf):
        self.gdf = gdf

        # TODO: vectorize minimum_rotated_rectangle after pygeos implementation
        bbox = gdf.geometry.apply(lambda g: g.minimum_rotated_rectangle)
        a = bbox.area
        p = bbox.length
        cond1 = p ** 2
        cond2 = 16 * a
        bigger = cond1 >= cond2
        sqrt = np.empty(len(a))
        sqrt[bigger] = cond1[bigger] - cond2[bigger]
        sqrt[~bigger] = 0

        # calculate both width/length and length/width
        elo1 = ((p - np.sqrt(sqrt)) / 4) / ((p / 2) - ((p - np.sqrt(sqrt)) / 4))
        elo2 = ((p + np.sqrt(sqrt)) / 4) / ((p / 2) - ((p + np.sqrt(sqrt)) / 4))

        # use the smaller one (e.g. shorter/longer)
        res = np.empty(len(a))
        res[elo1 <= elo2] = elo1[elo1 <= elo2]
        res[~(elo1 <= elo2)] = elo2[~(elo1 <= elo2)]

        self.series = pd.Series(res, index=gdf.index)


class momepy_Corners:
    """
    Calculates number of corners of each object in given geoDataFrame.
    Uses only external shape (shapely.geometry.exterior), courtyards are not included.
    .. math::
        \\sum corner
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects
    Attributes
    ----------
    series : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    Examples
    --------
    >>> buildings_df['corners'] = momepy.Corners(buildings_df).series
    100%|██████████| 144/144 [00:00<00:00, 1042.15it/s]
    >>> buildings_df.corners[0]
    24

    Notes:
    'Added distinction between Polygons and Multipolygons to avoid runtime errors in block feature calc.
    In addition, a new import: "from shapely import Polygon, Multipolygon" was added'
    Author: Felix
    Date: 11.02.2021
    """

    def __init__(self, gdf):
        self.gdf = gdf

        # define empty list for results
        results_list = []

        # calculate angle between points, return true or false if real corner
        def _true_angle(a, b, c):
            ba = a - b
            bc = c - b

            cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            angle = np.arccos(cosine_angle)

            if np.degrees(angle) <= 170:
                return True
            if np.degrees(angle) >= 190:
                return True
            return False

        # fill new column with the value of area, iterating over rows one by one
        for geom in gdf.geometry:
            # we distinguish between Polygons and Multiploygons, to avoid errors with
            # points = lis(geom.exteriors.coords) expression, as multipolygon has no exterior
            if isinstance(geom, Polygon):  # <<<< Modif

                corners = 0  # define empty variables
                points = list(geom.exterior.coords)  # get points of a shape
                stop = len(points) - 1  # define where to stop
                for i in np.arange(
                    len(points)
                ):  # for every point, calculate angle and add 1 if True angle
                    if i == 0:
                        continue
                    elif i == stop:
                        a = np.asarray(points[i - 1])
                        b = np.asarray(points[i])
                        c = np.asarray(points[1])

                        if _true_angle(a, b, c) is True:
                            corners = corners + 1
                        else:
                            continue

                    else:
                        a = np.asarray(points[i - 1])
                        b = np.asarray(points[i])
                        c = np.asarray(points[i + 1])

                        if _true_angle(a, b, c) is True:
                            corners = corners + 1
                        else:
                            continue
            # for MultiPolygons we use list(subgeom.exterior.coords) to avoid errors
            if isinstance(geom, MultiPolygon):  # <<<< Modif (all if loop added)

                corners = 0

                for subgeom in geom:

                    points = list(subgeom.exterior.coords)  # get points of a shape
                    stop = len(points) - 1  # define where to stop
                    for i in np.arange(
                        len(points)
                    ):  # for every point, calculate angle and add 1 if True angle
                        if i == 0:
                            continue
                        elif i == stop:
                            a = np.asarray(points[i - 1])
                            b = np.asarray(points[i])
                            c = np.asarray(points[1])

                            if _true_angle(a, b, c) is True:
                                corners = corners + 1
                            else:
                                continue

                        else:
                            a = np.asarray(points[i - 1])
                            b = np.asarray(points[i])
                            c = np.asarray(points[i + 1])

                            if _true_angle(a, b, c) is True:
                                corners = corners + 1
                            else:
                                continue

            results_list.append(corners)

        self.series = pd.Series(results_list, index=gdf.index)


class momepy_Convexeity:
    """
    Calculates convexeity index of each object in given geoDataFrame.
    .. math::
        area \\over \\textit{convex hull area}
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects
    areas : str, list, np.array, pd.Series (default None)
        the name of the dataframe column, np.array, or pd.Series where is stored area value. If set to None, function will calculate areas
        during the process without saving them separately.
    Attributes
    ----------
    series : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    areas : Series
        Series containing used area values
    References
    ----------
    Dibble, J. (2016) Urban Morphometrics: Towards a Quantitative Science of Urban
    Form. University of Strathclyde.
    Examples
    --------
    >>> buildings_df['convexeity'] = momepy.Convexeity(buildings_df).series
    >>> buildings_df.convexeity[0]
    0.8151964258521672
    """

    def __init__(self, gdf, areas=None):
        self.gdf = gdf

        gdf = gdf.copy()

        if areas is None:
            areas = gdf.geometry.area
        if not isinstance(areas, str):
            gdf["mm_a"] = areas
            areas = "mm_a"
        self.areas = gdf[areas]
        self.series = gdf[areas] / gdf.geometry.convex_hull.area


class momepy_Orientation:
    """
    Calculate the orientation of object
    Captures the deviation of orientation from cardinal directions.
    Defined as an orientation of the longext axis of bounding rectangle in range 0 - 45.
    Orientation of LineStrings is represented by the orientation of line
    connecting first and last point of the segment.
    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing objects to analyse
    Attributes
    ----------
    series : Series
        Series containing resulting values
    gdf : GeoDataFrame
        original GeoDataFrame
    References
    ----------
    Schirmer PM and Axhausen KW (2015) A multiscale classiﬁcation of urban morphology.
    Journal of Transport and Land Use 9(1): 101–130. (adapted)
    Examples
    --------
    >>> buildings_df['orientation'] = momepy.Orientation(buildings_df).series
    100%|██████████| 144/144 [00:00<00:00, 630.54it/s]
    >>> buildings_df['orientation'][0]
    41.05146788287027
    """

    def __init__(self, gdf):
        self.gdf = gdf
        # define empty list for results
        results_list = []

        def _dist(a, b):
            return math.hypot(b[0] - a[0], b[1] - a[1])

        for geom in gdf.geometry:
            if geom.type in ["Polygon", "MultiPolygon", "LinearRing"]:
                # TODO: vectorize once minimum_rotated_rectangle is in geopandas from pygeos
                bbox = list(geom.minimum_rotated_rectangle.exterior.coords)
                axis1 = _dist(bbox[0], bbox[3])
                axis2 = _dist(bbox[0], bbox[1])

                if axis1 <= axis2:
                    az = _azimuth(bbox[0], bbox[1])
                else:
                    az = _azimuth(bbox[0], bbox[3])
            elif geom.type in ["LineString", "MultiLineString"]:
                coords = geom.coords
                az = _azimuth(coords[0], coords[-1])
            else:
                results_list.append(np.nan)

            if 90 > az >= 45:
                diff = az - 45
                az = az - 2 * diff
            elif 135 > az >= 90:
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            elif 181 > az >= 135:
                diff = az - 135
                az = az - 2 * diff
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            results_list.append(az)

        self.series = pd.Series(results_list, index=gdf.index)
