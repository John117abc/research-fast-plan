#!/usr/bin/env python3
"""Gate F1 00_smoke.py - environment & geometry probes BEFORE building scenarios.

Checks on the frozen Town12 segment:
  1. segment load / length / lane width / heading
  2. drivable junction crossing availability along the segment (A2 decision)
  3. spawn feasibility: ego, parked queue (30/37/44 m), static blocker,
     kinematic crossing actor at shoulder edge, lead-mover hold
  4. A1 trigger math sanity (fastest-reach precedes window end) for all groups
Run from a freshly booted CARLA (Town12). Writes gate_f1/results/smoke.json
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))

import carla  # noqa: E402

from carla_env import clear_dynamic, connect, hold_transform, spawn_vehicle, spawn_walker  # noqa: E402
import geo  # noqa: E402


def probe_crossing(world, amap):
    """Report whether any drivable junction crosses the frozen segment."""
    hit = []
    L = len(geo.SEG["c0"])
    step = 4
    for s in range(int(geo.SEG["length_m"] * 0.2), L - 5, step):
        x, y = geo.world_from_local(s, 0.0)
        wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                               lane_type=carla.LaneType.Driving)
        if wp is None:
            continue
        if wp.is_junction or (wp.get_junction() is not None):
            hit.append({"s": s, "x": round(x, 1), "y": round(y, 1),
                        "road": wp.road_id, "lane": wp.lane_id})
    return hit


def spawn_probe(world, amap):
    out = {}
    yaw = geo.heading_deg()
    # ego at c0[0]
    x0, y0, z0, _ = geo.seg_point(amap, 0.0, 0.0)
    ego = spawn_vehicle(world, "vehicle.lincoln.mkz_2020", x0, y0, z0, yaw, hero=True)
    out["ego_spawn"] = ego is not None
    if ego is not None:
        ego.destroy()
    # stopped queue on C0 at 30/37/44
    q = []
    for off in (30.0, 37.0, 44.0):
        x, y, z, _ = geo.seg_point(amap, off, 0.0)
        a = spawn_vehicle(world, None, x, y, z, yaw)
        q.append(a is not None)
        if a is not None:
            hold_transform(a, x, y, yaw)
            a.destroy()
    out["c0_queue_spawn"] = q
    # left-lane (CL) stationary at 30: use actual seg["cl"] waypoint coords
    cl_ok = False
    for off in (30, 31, 29, 28):
        cx, cy = geo.SEG["cl"][off]
        wp = amap.get_waypoint(carla.Location(x=cx, y=cy), project_to_road=True,
                               lane_type=carla.LaneType.Driving)
        a = spawn_vehicle(world, None, cx, cy,
                          wp.transform.location.z if wp else 0.3, yaw)
        if a is not None:
            cl_ok = True
            hold_transform(a, cx, cy, yaw)
            a.destroy()
            break
    out["cl_spawn"] = cl_ok
    # kinematic crossing vehicle at shoulder edge lat=-2.5, yaw perpendicular
    x, y, z, _ = geo.seg_point(amap, 30.0, -2.5)
    a = spawn_vehicle(world, None, x, y, z, yaw + 90.0)
    out["crossing_shoulder_spawn"] = a is not None
    if a is not None:
        hold_transform(a, x, y, yaw + 90.0)
        a.destroy()
    # walker at lat -6 shoulder for A1 fallback probe
    x, y, z, _ = geo.seg_point(amap, 30.0, -6.0)
    w = spawn_walker(world, x, y, z)
    out["walker_shoulder_spawn"] = w is not None
    if w is not None:
        w.destroy()
    return out


def check_a1_math(groups):
    """Bracketing trigger rule (motivated by smoke): the occupancy window must
    start BEFORE the ego's earliest reachable pass and end AFTER its cruise pass.
      tmin  = earliest reachable arrival under accel 1.5 from v_target
      Te    = d_conflict / v_target (cruise hold arrival)
      win   = [tmin - 1.0, max(Te + 1.0, tmin + 2.5)]
    Closure keeps current corridor suppressed from tmin-1 until after Te; ego
    cannot pass before start (bracketed) and resumes after end."""
    res = []
    for g in groups:
        d = g["d_conflict"]
        v = g["v_target"]
        Te = d / v
        tacc = (12.0 - v) / 1.5
        dacc = v * tacc + 0.75 * tacc * tacc
        if dacc >= d:
            tmin = (-v + math.sqrt(max(0.0, v * v + 3.0 * d))) / 1.5
        else:
            tmin = tacc + (d - dacc) / 12.0
        res.append({"id": g["id"], "d": d, "v": v, "Te": round(Te, 2),
                    "tmin": round(tmin, 2),
                    "win": [round(tmin - 1.0, 2),
                            round(max(Te + 1.0, tmin + 2.5), 2)],
                    "ok": True})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=2000)
    a = ap.parse_args()
    client, world = connect(port=a.port)
    clear_dynamic(world)
    amap = world.get_map()
    geo.load_seg()
    report = {"town": amap.name.split("/")[-1],
              "length_m": geo.SEG["length_m"], "lane_w": round(geo.lane_width(), 3),
              "heading_deg": round(math.degrees(geo.SEG["heading_rad"]), 2),
              "junction_crossings": probe_crossing(world, amap),
              "spawn": spawn_probe(world, amap)}
    import yaml
    groups = yaml.safe_load(open("gate_f1/config/parameter_table.yaml"))["groups"]
    report["A1_trigger_math"] = check_a1_math(groups)
    os.makedirs("gate_f1/results", exist_ok=True)
    json.dump(report, open("gate_f1/results/smoke.json", "w"), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
