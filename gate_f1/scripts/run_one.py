#!/usr/bin/env python3
"""Gate F1 single-run recorder (kinematic deterministic ego).

usage: run_one.py --scene A1 --group 3 [--port 2000] [--seconds 12]
Frozen flow: fresh Town12 -> clear -> spawn ego (hero, C0) ->
  ego accelerated kinematically to v_target on clear road (>=25 m clear) and
  held there >=1.0 s  ->  t0 (scenario start, records begin) ->
  scene kinematic laws on trel  ->  20 Hz ndjson.
NOTE: ego is scripted-kinematic (ramp -> cruise -> gap-brake before obstacles);
CARLA PID physics proved non-repeatable for low/mid speed in this env. The FROZEN
engine reads only the ego initial state (v0,s0) plus recorded actor occupancy.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scenarios"))

import carla  # noqa: E402

from carla_env import clear_dynamic, connect, spawn_vehicle  # noqa: E402
import geo  # noqa: E402
from factory import make  # noqa: E402
from recorder import world_recorder  # noqa: E402

DT = 0.05
RAMP_A = 1.5          # kinematic ego longitudinal ramp accel
STOP_GAP = 3.0        # stop distance behind obstacle
BRAKE_A = -2.5        # kinematic brake decel
MAX_ITER = 4000


def ego_front(scene, amap, ego_s):
    """Nearest prop ahead inside C0 band (|lat|<2.2), for ego braking law."""
    best = None
    for p in scene.props:
        a = p["actor"]
        loc = a.get_location()
        sx, ly = geo.local(loc.x, loc.y)
        if abs(ly) < 2.2 and sx > ego_s - 2.0:
            if best is None or sx < best:
                best = sx
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True,
                    choices=["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2",
                             "G1", "G2", "G3"])
    ap.add_argument("--group", type=int, required=True)
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--seconds", type=float, default=12.0)
    a = ap.parse_args()
    geo.load_seg("gate_f0/road_segment.json")

    client, world = connect(port=a.port)
    clear_dynamic(world)
    amap = world.get_map()

    x0, y0, z0, yaw = geo.seg_point(amap, 0.0, 0.0)
    ego = spawn_vehicle(world, "vehicle.lincoln.mkz_2020", x0, y0, z0, yaw, hero=True)
    if ego is None:
        raise RuntimeError("ego spawn failed")
    scene = make(a.scene, world, amap, a.group)
    nominal = scene.v_target
    ox = math.cos(geo.SEG["heading_rad"])
    oy = math.sin(geo.SEG["heading_rad"])

    def place_ego(ego_s, speed):
        s = max(0.0, min(ego_s, float(len(geo.SEG["c0"]) - 2)))
        idx = int(round(s))
        x, y = geo.SEG["c0"][idx]
        wp = amap.get_waypoint(carla.Location(x=x, y=y), project_to_road=True,
                               lane_type=carla.LaneType.Driving)
        z = wp.transform.location.z if wp else z0
        ego.set_transform(carla.Transform(carla.Location(x=x, y=y, z=z),
                                          carla.Rotation(yaw=yaw)))
        ego.set_target_velocity(carla.Vector3D(speed * ox, speed * oy, 0.0))

    def s_to_c0(s):
        return s

    # VIRTUAL CLOCK: ego and every scene law advance by a fixed internal dt so
    # that ego position and prop laws share one self-consistent time base,
    # independent of CARLA snapshot cadence. CARLA ticks are used only to pace.
    DT_V = 0.05
    ego_s, v_e = 0.0, 0.0
    t_hold0 = None
    t0 = None
    tsim = 0.0
    iter_n = 0
    out_dir = f"gate_f1/results/{a.scene}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/run{a.group}.ndjson"
    meta = {"scene": a.scene, "group": a.group, "t0": None, "v_target": nominal,
            "params": scene.meta if hasattr(scene, "meta") else {}}

    def tick_ego(front_s, dt):
        nonlocal ego_s, v_e
        if dt <= 0:
            return v_e
        if front_s is None:
            gap = None
        else:
            gap = front_s - ego_s
        v_des = nominal
        if gap is not None and gap < 20.0:
            v_des = min(v_des, max(0.0, math.sqrt(max(0.0, 2 * (-BRAKE_A) *
                                                     (gap - STOP_GAP)))))
        if v_des > v_e:
            v_e = min(v_des, v_e + RAMP_A * dt)
        elif v_des < v_e:
            v_e = max(v_des, v_e + BRAKE_A * dt)
        ego_s += v_e * dt
        place_ego(ego_s, v_e)
        return v_e

    with open(out_path, "w") as f:
        while True:
            world.wait_for_tick()
            tsim += DT_V
            iter_n += 1
            if t0 is None and tsim > 30.0:
                raise RuntimeError("ego never stabilized")
            if t0 is None:
                front0 = ego_front(scene, amap, ego_s)
                scene.step(amap, 0.0)
                tick_ego(front0, DT_V)
                clear = front0 is None or (front0 - ego_s) > 12.0
                if v_e >= nominal - 0.2 and clear:
                    if t_hold0 is None:
                        t_hold0 = tsim
                    elif tsim - t_hold0 >= 1.0:
                        t0 = tsim
                        meta["t0"] = round(t0, 3)
                        meta["v0"] = round(v_e, 3)
                        meta["ego_s0"] = round(ego_s, 2)
                        if hasattr(scene, "arm"):
                            scene.arm(ego_s, v_e)
                else:
                    t_hold0 = None
            else:
                trel = tsim - t0
                if trel > a.seconds or iter_n > MAX_ITER:
                    break
                scene.step(amap, trel)
                front = ego_front(scene, amap, ego_s)
                tick_ego(front, DT_V)
                rec = world_recorder.record_one(world, ego, scene.props_actors(), meta)
                rec["sim_t"] = round(trel, 3)
                rec["ego_s"] = round(ego_s, 3)
                f.write(json.dumps(rec) + "\n")
    scene.destroy()
    if ego.is_alive:
        ego.destroy()
    print("wrote", out_path, "iters", iter_n, "meta", json.dumps(meta))


if __name__ == "__main__":
    main()
