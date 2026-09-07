#!/usr/bin/env python3
"""Gate F3 row recorder (mirrors gate_f1 run_one virtual-clock logic, but a row
comes from gate_f3/data/params_F3.yaml via factory.make_f3).

usage: f3_run_one.py --cell cross_stall_occ --row 1 [--port 2000]
writes gate_f3/data/raw/<mech>/<cell>/row<row>.ndjson
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "gate_f1", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "gate_f1", "scenarios"))

import yaml  # noqa: E402

import carla  # noqa: E402

from carla_env import clear_dynamic, connect, spawn_vehicle  # noqa: E402
import geo  # noqa: E402
from factory import make_f3  # noqa: E402
from recorder import world_recorder  # noqa: E402

DT_V = 0.05
RAMP_A = 1.5
STOP_GAP = 3.0
BRAKE_A = -2.5
MAX_ITER = 4000
MECH = {"cross_clear": "cross", "cross_stall": "cross",
        "cross_stall_occ": "cross", "lead_opt": "lead", "lead_nec": "lead",
        "lead_cont": "lead", "block_nec": "block", "block_cont": "block",
        "temp_opt": "temp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    ap.add_argument("--row", type=int, required=True)
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--seconds", type=float, default=12.0)
    a = ap.parse_args()
    geo.load_seg("gate_f0/road_segment.json")
    rows = yaml.safe_load(open("gate_f3/data/params_F3.yaml"))
    spec = rows[a.cell][a.row - 1]

    client, world = connect(port=a.port)
    clear_dynamic(world)
    amap = world.get_map()
    x0, y0, z0, yaw = geo.seg_point(amap, 0.0, 0.0)
    ego = spawn_vehicle(world, "vehicle.lincoln.mkz_2020", x0, y0, z0, yaw, hero=True)
    if ego is None:
        raise RuntimeError("ego spawn failed")
    scene = make_f3(world, amap, spec)
    nominal = scene.v_target
    ox = math.cos(geo.SEG["heading_rad"])
    oy = math.sin(geo.SEG["heading_rad"])

    def place_ego(s, speed):
        s = max(0.0, min(s, float(len(geo.SEG["c0"]) - 2)))
        idx = int(round(s))
        x, y = geo.SEG["c0"][idx]
        wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                               lane_type=carla.LaneType.Driving)
        z = wp.transform.location.z if wp else z0
        ego.set_transform(carla.Transform(carla.Location(x=x, y=y, z=z),
                                          carla.Rotation(yaw=yaw)))
        ego.set_target_velocity(carla.Vector3D(speed * ox, speed * oy, 0.0))

    def ego_front(ego_s):
        best = None
        for p in scene.props:
            loc = p["actor"].get_location()
            sx, ly = geo.local(loc.x, loc.y)
            if abs(ly) < 2.2 and sx > ego_s - 2.0:
                if best is None or sx < best:
                    best = sx
        return best

    mech = MECH[a.cell]
    out_dir = f"gate_f3/data/raw/{mech}/{a.cell}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/row{a.row}.ndjson"
    meta = {"cell": a.cell, "mech": mech, "row": a.row, "spec": spec,
            "v_target": nominal}
    ego_s, v_e, t0, hold0, tsim, iter_n = 0.0, 0.0, None, None, 0.0, 0
    with open(out_path, "w") as f:
        while True:
            world.wait_for_tick()
            tsim += DT_V
            iter_n += 1
            if t0 is None and tsim > 30.0:
                raise RuntimeError("ego never stabilized")
            if t0 is None:
                front = ego_front(ego_s)
                scene.step(amap, 0.0)
                gap = None if front is None else front - ego_s
                v_des = nominal
                if gap is not None and gap < 20.0:
                    v_des = min(v_des, max(0.0, math.sqrt(
                        max(0.0, 2 * BRAKE_A * (gap - STOP_GAP)))))
                if v_des > v_e:
                    v_e = min(v_des, v_e + RAMP_A * DT_V)
                elif v_des < v_e:
                    v_e = max(v_des, v_e + BRAKE_A * DT_V)
                ego_s += v_e * DT_V
                place_ego(ego_s, v_e)
                clear = front is None or gap > 12.0
                if v_e >= nominal - 0.2 and clear:
                    if hold0 is None:
                        hold0 = tsim
                    elif tsim - hold0 >= 1.0:
                        t0 = tsim
                        meta["ego_s0"] = round(ego_s, 2)
                else:
                    hold0 = None
            else:
                trel = tsim - t0
                if trel > a.seconds or iter_n > MAX_ITER:
                    break
                scene.step(amap, trel)
                front = ego_front(ego_s)
                gap = None if front is None else front - ego_s
                v_des = nominal
                if gap is not None and gap < 20.0:
                    v_des = min(v_des, max(0.0, math.sqrt(
                        max(0.0, 2 * BRAKE_A * (gap - STOP_GAP)))))
                if v_des > v_e:
                    v_e = min(v_des, v_e + RAMP_A * DT_V)
                elif v_des < v_e:
                    v_e = max(v_des, v_e + BRAKE_A * DT_V)
                ego_s += v_e * DT_V
                place_ego(ego_s, v_e)
                rec = world_recorder.record_one(world, ego, scene.props_actors(), meta)
                rec["sim_t"] = round(trel, 3)
                rec["ego_s"] = round(ego_s, 3)
                f.write(json.dumps(rec) + "\n")
    scene.destroy()
    if ego.is_alive:
        ego.destroy()
    print("wrote", out_path, "iters", iter_n)


if __name__ == "__main__":
    main()
