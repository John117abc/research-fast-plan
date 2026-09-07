"""Shared geometry helpers for Gate F1 (frozen Town12 segment)."""
import json
import math

import carla

W = None
SEG = None
_GEO = None


def load_seg(path="gate_f0/road_segment.json"):
    global SEG
    SEG = json.load(open(path))
    return SEG


def geo():
    global _GEO
    if _GEO is None:
        ox, oy = SEG["origin"]
        th = SEG["heading_rad"]
        _GEO = (ox, oy, (math.cos(th), math.sin(th)), (-math.sin(th), math.cos(th)))
    return _GEO


def lane_width():
    if len(SEG["c0"]) < 60:
        return 3.5
    n = 0.0
    for i in range(0, 60, 2):
        a, b = SEG["c0"][i], SEG["cl"][i]
        n += math.hypot(a[0] - b[0], a[1] - b[1])
    return n / 30.0


def world_from_local(s, lat):
    ox, oy, u, n = geo()
    return (ox + s * u[0] + lat * n[0], oy + s * u[1] + lat * n[1])


def local(x, y):
    ox, oy, u, n = geo()
    dx, dy = x - ox, y - oy
    return dx * u[0] + dy * u[1], dx * n[0] + dy * n[1]


def heading_deg():
    return math.degrees(SEG["heading_rad"])


def seg_point(amap, s, lat=0.0):
    """World x,y,z,yaw at segment position s (lat along c0=0, cl=+W)."""
    x, y = world_from_local(s, lat)
    wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                           lane_type=carla.LaneType.Driving)
    z = wp.transform.location.z if wp else 0.3
    return x, y, z, heading_deg()


def cl_seg_point(amap, s):
    """World x,y,z,yaw at actual left-lane centerline index s."""
    s = max(0.0, min(float(s), float(len(SEG["cl"]) - 1)))
    x, y = SEG["cl"][int(round(s))]
    wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                           lane_type=carla.LaneType.Driving)
    z = wp.transform.location.z if wp else 0.3
    return x, y, z, heading_deg()
