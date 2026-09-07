#!/usr/bin/env python3
"""Gate F0 pilot runner (CARLA async; timestamps recorded -> offline resample).

usage: f0_pilot.py --case temp_crossing|static_blocker --seed N [--seconds 12] [--port 2000]

Freezes the Town12 road segment on first use (gate_f0/road_segment.json), spawns
ego + scripted actors (no TM), drives ego with Lane-PID, and records full GT at
each server tick into gate_f0/results/pilot/<case>/seed<N>.ndjson
"""
import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import carla  # noqa: E402

from feasible.corridor_map import find_straight_segment  # noqa: E402
from ego.lane_pid_ego import LanePIDEgo  # noqa: E402
from recorder import world_recorder  # noqa: E402

SEG_CACHE = "gate_f0/road_segment.json"
MAX_ITER = 3000


def seg_geo(seg):
    ox, oy = seg["origin"]
    th = seg["heading_rad"]
    u = (math.cos(th), math.sin(th))
    n = (-math.sin(th), math.cos(th))
    return ox, oy, u, n


def world_from_local(seg, s, lat):
    ox, oy, u, n = seg_geo(seg)
    return (ox + s * u[0] + lat * n[0], oy + s * u[1] + lat * n[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=["temp_crossing", "static_blocker"], required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--port", type=int, default=2000)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out_dir = f"gate_f0/results/pilot/{a.case}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/seed{a.seed}.ndjson"

    client = carla.Client("localhost", a.port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name.split("/")[-1] != "Town12":
        world = client.load_world("Town12")
    amap = world.get_map()
    for _ in range(10):
        world.wait_for_tick()
    world.set_weather(carla.WeatherParameters.ClearNoon)
    world.apply_settings(carla.WorldSettings(synchronous_mode=False))

    # clear any leftover dynamic actors (scripted F0 world, no TM background)
    for actor in list(world.get_actors().filter("*vehicle*")) + \
                  list(world.get_actors().filter("*walker*")):
        try:
            if actor.is_alive:
                actor.destroy()
        except Exception:
            pass
    for _ in range(5):
        world.wait_for_tick()

    if os.path.isfile(SEG_CACHE):
        seg = json.load(open(SEG_CACHE))
    else:
        seg = find_straight_segment(world, min_len=120.0)
    ox, oy, u, n = seg_geo(seg)
    heading_deg = math.degrees(seg["heading_rad"])

    bp_lib = world.get_blueprint_library()
    ego_bp = bp_lib.filter("vehicle.lincoln.mkz_2020")[0]
    ego_bp.set_attribute("role_name", "hero")
    spawn_s = 0
    ego = None
    for idx in (0, 1, 2):
        ex, ey = seg["c0"][idx]
        e_wp = amap.get_waypoint(carla.Location(x=ex, y=ey), project_to_road=True,
                                 lane_type=carla.LaneType.Driving)
        ego = world.try_spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=ex, y=ey, z=e_wp.transform.location.z if e_wp else 0.5),
            carla.Rotation(yaw=heading_deg)))
        if ego is not None:
            break
    if ego is None:
        raise RuntimeError("ego spawn failed")
    ego.apply_control(carla.VehicleControl())
    actors = [ego]
    target_ids = []

    def hold(act, x, y, yaw=None):
        rot = act.get_transform().rotation
        act.set_transform(carla.Transform(
            carla.Location(x=x, y=y, z=act.get_transform().location.z),
            carla.Rotation(yaw=yaw if yaw is not None else rot.yaw)))

    scenario = {}
    if a.case == "static_blocker":
        scenario["L"] = rng.uniform(40.0, 55.0)
        blk = None
        for bpname in ("vehicle.tesla.model3", "vehicle.mini.cooper_s",
                       "vehicle.dodge.charger_police", "vehicle.audi.tt",
                       "vehicle.lincoln.mkz_2020"):
            bps = bp_lib.filter(bpname)
            if not bps:
                continue
            bp = bps[0]
            idxs = [int(scenario["L"]), int(scenario["L"]) + 1, int(scenario["L"]) - 1]
            for idx in idxs:
                bx, by = seg["c0"][idx]
                b_wp = amap.get_waypoint(carla.Location(x=bx, y=by), project_to_road=True,
                                         lane_type=carla.LaneType.Driving)
                blk = world.try_spawn_actor(bp, carla.Transform(
                    carla.Location(x=bx, y=by, z=b_wp.transform.location.z if b_wp else 0.3),
                    carla.Rotation(yaw=heading_deg)))
                if blk is not None:
                    break
            if blk is not None:
                break
        if blk is None:
            raise RuntimeError("blocker spawn failed")
        scenario["block_xy"] = [bx, by]
        actors.append(blk)
        target_ids.append(blk.id)
    else:
        scenario["Lc"] = rng.uniform(28.0, 40.0)
        scenario["Tc"] = rng.uniform(3.0, 4.0)
        scenario["Ts"] = None               # set at runtime after ego warm-up
        scenario["_hi_start"] = None
        wl = None
        bp = bp_lib.filter("walker.pedestrian.0002")[0]
        for lat0 in (-6.0, -7.0, 6.0):
            wx0, wy0 = world_from_local(seg, scenario["Lc"], lat0)
            w_wp = amap.get_waypoint(carla.Location(x=wx0, y=wy0), project_to_road=True)
            wl = world.try_spawn_actor(bp, carla.Transform(
                carla.Location(x=wx0, y=wy0,
                               z=w_wp.transform.location.z if w_wp else 0.2)))
            if wl is not None:
                break
        if wl is None:
            raise RuntimeError("walker spawn failed")
        actors.append(wl)
        target_ids.append(wl.id)

    scenario_meta = {"case": a.case, "seed": a.seed, "target_actor_ids": target_ids,
                     "L": scenario.get("L"), "Lc": scenario.get("Lc"),
                     "Ts": scenario.get("Ts"), "Tc": scenario.get("Tc")}

    controller = LanePIDEgo(kp_v=1.2, max_accel=4.0)
    nominal = 9.0 if a.case == "temp_crossing" else 8.0
    corr_path = [[p[0], p[1]] for p in seg["c0"]]
    t0 = None
    iter_n = 0
    with open(out_path, "w") as f:
        while True:
            world.wait_for_tick()
            snap = world.get_snapshot()
            t = snap.timestamp.elapsed_seconds
            if t0 is None:
                t0 = t
            tau = t - t0
            iter_n += 1
            if tau > a.seconds or iter_n > MAX_ITER:
                break
            # ego current state (used by scenario + control)
            e_loc = ego.get_transform().location
            s_ego = (e_loc.x - ox) * u[0] + (e_loc.y - oy) * u[1]
            v_now = math.hypot(ego.get_velocity().x, ego.get_velocity().y)
            # scenario dynamics
            if a.case == "static_blocker":
                hold(blk, scenario["block_xy"][0], scenario["block_xy"][1], heading_deg)
                blk.set_target_velocity(carla.Vector3D(0, 0, 0))
                front_s = scenario["L"]
            else:
                # warm-up gate: trigger crossing only after ego v>=4 sustained >=1 s
                Ts = scenario["Ts"]
                if Ts is None:
                    if v_now >= 4.0:
                        if scenario.get("_hi_start") is None:
                            scenario["_hi_start"] = tau
                        elif tau - scenario["_hi_start"] >= 1.0:
                            scenario["Ts"] = tau
                            Ts = tau
                    else:
                        scenario["_hi_start"] = None
                    if Ts is None and tau > 7.0:      # fallback late trigger
                        scenario["Ts"] = tau
                        Ts = tau
                if Ts is None:
                    # hold pedestrian far off-lane while warming up
                    fx, fy = world_from_local(seg, scenario["Lc"], -6.0)
                    hold(wl, fx, fy, heading_deg)
                    wl.set_target_velocity(carla.Vector3D(0, 0, 0))
                    front_s = None
                else:
                    phase = (tau - Ts) / scenario["Tc"]
                    if 0.0 <= phase <= 1.0:
                        lat = -3.0 + 6.0 * phase
                        wx, wy = world_from_local(seg, scenario["Lc"], lat)
                        hold(wl, wx, wy, heading_deg)
                        wl.set_target_velocity(carla.Vector3D(0, 0, 0))
                        front_s = scenario["Lc"]      # block current corridor
                    else:
                        fx, fy = world_from_local(seg, scenario["Lc"], -6.0)
                        hold(wl, fx, fy, heading_deg)
                        wl.set_target_velocity(carla.Vector3D(0, 0, 0))
                        front_s = None
            # ego control
            target_spd = nominal
            if front_s is not None and (front_s - s_ego) < 14.0:
                target_spd = min(target_spd, max(0.0, (front_s - s_ego - 2.0) * 0.7))
            ctrl = controller.step(ego.get_transform(), v_now, target_spd, corr_path)
            ego.apply_control(ctrl)
            rec = world_recorder.record_one(world, ego, actors[1:], scenario_meta)
            rec["sim_t"] = tau
            f.write(json.dumps(rec) + "\n")

    for act in actors:
        if act.is_alive:
            act.destroy()
    print("wrote", out_path, "iters", iter_n, "targets", target_ids)


if __name__ == "__main__":
    main()
