"""Gate F0 world recorder: 20 Hz full dynamic-actor GT recorder.

Works in CARLA synchronous mode (fixed_delta_seconds = 1/hz). One record per
tick: ego + all dynamic actors world pose/velocity/accel/bbox and lane ids.
Writes ndjson lines to out_path plus a meta header run.
"""
import json
import math
import os

import carla


def _vec(d):
    return [float(d.x), float(d.y), float(d.z)]


def _speed(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def _bbox(actor):
    e = actor.bounding_box.extent
    return {"center": [float(actor.bounding_box.location.x),
                       float(actor.bounding_box.location.y)],
            "extent": [float(e.x), float(e.y), float(e.z)]}


def actor_lane(world, actor):
    """best-effort lane id / road id at actor location."""
    try:
        wp = world.get_map().get_waypoint(actor.get_location(),
                                          project_to_road=True, lane_type=carla.LaneType.Driving)
        return {"road_id": wp.road_id, "lane_id": wp.lane_id,
                "lane_type": str(wp.lane_type)}
    except Exception:
        return {"road_id": None, "lane_id": None, "lane_type": None}


def record_one(world, ego, actors, scenario_meta, hz=20.0):
    """Build one record dict at current tick (synchronous)."""
    et = ego.get_transform()
    ev = ego.get_velocity()
    ea = ego.get_acceleration()
    rec = {
        "frame": int(world.get_snapshot().frame),
        "timestamp": world.get_snapshot().timestamp.elapsed_seconds,
        "ego": {
            "actor_id": ego.id,
            "type_id": ego.type_id,
            "transform": {"x": et.location.x, "y": et.location.y, "z": et.location.z,
                          "roll": et.rotation.roll, "pitch": et.rotation.pitch,
                          "yaw": et.rotation.yaw},
            "velocity": _vec(ev),
            "speed_mps": _speed(ev),
            "acceleration": _vec(ea),
            "bbox": _bbox(ego),
            **actor_lane(world, ego),
        },
        "actors": [],
        "scenario": scenario_meta,
    }
    for a in actors:
        if a.id == ego.id:
            continue
        t = a.get_transform()
        v = a.get_velocity()
        ac = a.get_acceleration()
        rec["actors"].append({
            "actor_id": a.id,
            "type": "vehicle" if a.type_id.startswith("vehicle") else
                    ("walker" if a.type_id.startswith("walker") else a.type_id),
            "type_id": a.type_id,
            "transform": {"x": t.location.x, "y": t.location.y, "z": t.location.z,
                          "roll": t.rotation.roll, "pitch": t.rotation.pitch,
                          "yaw": t.rotation.yaw},
            "velocity": _vec(v),
            "speed_mps": _speed(v),
            "acceleration": _vec(ac),
            "bbox": _bbox(a),
            **actor_lane(world, a),
        })
    return rec


def setup_sync(world, hz=20.0):
    world.apply_settings(carla.WorldSettings(
        synchronous_mode=True, fixed_delta_seconds=1.0 / hz))
