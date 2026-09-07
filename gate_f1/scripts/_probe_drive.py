#!/usr/bin/env python3
"""Ego drive ceiling probe: full-throttle run on empty segment."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))
sys.path.insert(0, "gate_f0")

import carla

from carla_env import clear_dynamic, connect, spawn_vehicle
import geo
from ego.lane_pid_ego import LanePIDEgo


def main():
    geo.load_seg("gate_f0/road_segment.json")
    client, world = connect()
    clear_dynamic(world)
    amap = world.get_map()
    x0, y0, z0, yaw = geo.seg_point(amap, 0.0, 0.0)
    ego = spawn_vehicle(world, "vehicle.lincoln.mkz_2020", x0, y0, z0, yaw, hero=True)
    corr = [[p[0], p[1]] for p in geo.SEG["c0"]]
    steer = LanePIDEgo()
    t = 0.0
    for _ in range(200):
        world.wait_for_tick()
        v = math.hypot(ego.get_velocity().x, ego.get_velocity().y)
        if int(t) % 1 == 0 and v >= 0:
            pass
        t = world.get_snapshot().timestamp.elapsed_seconds
        if t > 1 and int(t * 10) % 10 == 0:
            print(f"t={t:.1f} v={v:.2f}", flush=True)
        c = carla.VehicleControl()
        c.throttle = 1.0 if v < 9.0 else 0.2
        c.steer = steer.steer(ego.get_transform(), corr)
        ego.apply_control(c)
        if t > 15:
            break
    v = math.hypot(ego.get_velocity().x, ego.get_velocity().y)
    print("CEILING v=", round(v, 2))
    ego.destroy()


if __name__ == "__main__":
    main()
