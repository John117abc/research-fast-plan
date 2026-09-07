"""Gate F0 corridor builder from a live CARLA world (used at F0-2/F0-4).

Selects a straight two-lane (current + legal left) Driving-lane segment on a
chosen Town. Produces C0 / CL centerline world points and a frozen segment
descriptor (cached to gate_f0/road_segment.json).
"""
import json
import math
import os

import carla


def _yaw(wp_a, wp_b):
    return math.atan2(wp_b.transform.location.y - wp_a.transform.location.y,
                      wp_b.transform.location.x - wp_a.transform.location.x)


def _same_dir(a, b):
    return a.lane_id * b.lane_id > 0


def find_straight_segment(world, min_len=120.0, step=2.0, max_dev=1.5,
                          sample_cap=60000, seg_cache="gate_f0/road_segment.json"):
    """Return segment descriptor for first long straight two-lane Driving segment."""
    amap = world.get_map()
    try:
        wps = amap.generate_waypoints(step)
    except Exception:
        wps = []
    count = 0
    for start in wps:
        count += 1
        if count > sample_cap:
            break
        if start.lane_type != carla.LaneType.Driving:
            continue
        left = start.get_left_lane()
        if left is None or left.lane_type != carla.LaneType.Driving or not _same_dir(start, left):
            continue
        pts = [start]
        wp = start
        for _ in range(int(min_len / step) + 80):
            nxt = wp.next(step)
            if not nxt:
                break
            nxt = nxt[0]
            if nxt.road_id != wp.road_id or nxt.lane_id != wp.lane_id:
                break
            pts.append(nxt)
            wp = nxt
        length = sum(pts[i].transform.location.distance(pts[i - 1].transform.location)
                     for i in range(1, len(pts)))
        if length < min_len:
            continue
        # straightness: max perpendicular distance of interior pts to end chord
        a = pts[0].transform.location
        b = pts[-1].transform.location
        ab = math.hypot(b.x - a.x, b.y - a.y)
        dev = 0.0
        if ab > 1e-6:
            for p in pts[1:-1]:
                loc = p.transform.location
                cross = abs((b.x - a.x) * (a.y - loc.y) - (a.x - loc.x) * (b.y - a.y))
                dev = max(dev, cross / ab)
        if dev > max_dev:
            continue
        start_wp = start
        p0 = start_wp.transform.location
        p1 = pts[1].transform.location if len(pts) > 1 else p0
        heading = math.atan2(p1.y - p0.y, p1.x - p0.x)
        seg = {"town": amap.name.split("/")[-1],
               "origin": [p0.x, p0.y], "heading_rad": heading,
               "length_m": length, "n": int(length),
               "c0": [], "cl": []}
        for k in range(int(length) + 1):
            wp = _waypoint_at(amap, start_wp, k)
            seg["c0"].append([wp.transform.location.x, wp.transform.location.y])
            lwp = wp.get_left_lane()
            if lwp is None or lwp.lane_type != carla.LaneType.Driving or not _same_dir(wp, lwp):
                lwp = wp
            seg["cl"].append([lwp.transform.location.x, lwp.transform.location.y])
        os.makedirs(os.path.dirname(seg_cache), exist_ok=True)
        with open(seg_cache, "w") as f:
            json.dump(seg, f, indent=1)
        return seg
    raise RuntimeError("no straight two-lane segment found")


def _waypoint_at(amap, start_wp, meters):
    wp = start_wp
    for _ in range(meters):
        nx = wp.next(1.0)
        if not nx:
            break
        wp = nx[0]
    return wp
