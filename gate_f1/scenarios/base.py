"""Gate F1 scenario base: shared CARLA scene helpers + motion laws.

Design contract (PROTOCOL.md):
  - CARLA only generates the physical future (no planner opinions).
  - Ego = LanePID driving C0 (never actually changes lane; CL feasibility is
    evaluated offline by the frozen engine).
  - Props are moved deterministically (static holds / kinematic law of trel)
    so a run is fully reproducible from its parameter group.
  - t0 = scenario-active start: first recorded frame after ego holds
    |v - v_target| < 0.5 for >=1.0 s. Kinematic laws use trel = t - t0.
"""
import math

import carla

import geo
from carla_env import hold_transform, spawn_vehicle, spawn_walker

CROSS_SPEED = 1.6          # lateral m/s used by A1/A2 crossing props
QUEUE_OFFSETS = (0, 7, 14) # stopped queue spacing behind first stopped vehicle


def move_along(amap, actor, axis, s, speed_override=None, yaw=None):
    """Teleport actor to segment position s on c0 (axis='c0') or cl list.

    Deterministic kinematic motion: map s (m) to nearest stored centerline
    point, place actor there with forward yaw. Returns current s used.
    """
    s = max(0.0, min(s, float(len(geo.SEG[axis])) - 1.0))
    idx = int(round(s))
    x, y = geo.SEG[axis][idx]
    wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                           lane_type=carla.LaneType.Driving)
    z = wp.transform.location.z if wp else 0.3
    rot = actor.get_transform().rotation
    hold_transform(actor, x, y, yaw if yaw is not None else rot.yaw)
    return s


def spawn_on(world, amap, code, axis, s, yaw_off=0.0):
    """Spawn vehicle/walker by scene role code at segment position s."""
    yaw = geo.heading_deg() + yaw_off
    x, y, z, _ = geo.seg_point(amap, s, 0.0) if axis == "c0" else geo.cl_seg_point(s)
    if code.startswith("walker"):
        return spawn_walker(world, x, y, z, bpname=code.split(":", 1)[1]
                            if ":" in code else "walker.pedestrian.0002")
    bp = None if code == "anycar" else code
    return spawn_vehicle(world, bp, x, y, z, yaw)


def lane_blocked(prop, ego_s, ego_lat_half=1.9):
    """True if prop center sits inside C0 occupancy band ahead of ego."""
    return prop.get("lat", 0.0) is not None and abs(prop.get("lat", 0.0)) < ego_lat_half
