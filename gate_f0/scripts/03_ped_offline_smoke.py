"""Gate F0-3 (smoke, non-formal): temporary-closure->reopen on an old PED window.

Uses route10 PedestrianCrossing snapshots: decision frame = ego approaching the
owned walker. Corridor approximated straight along ego heading at decision.
GT occupancy = owned walkers re-projected into that corridor over the next 8 s.
Runs the KEEP (P0) branch; expects a temporary dip then resumed growth (G0>0).
"""
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from feasible.engine import StraightCorridor, OccupancyGT, compute_frontiers  # noqa: E402

SNAP = "outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59"
SCNLOG = "outputs/gate6/scnlog_route10.jsonl"
INSTANCE = "PedestrianCrossing_5"

DT = 0.5
ACCEL = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
N = 16
HSTEPS = [int(x / DT) for x in (2, 4, 6, 8)]


def load_meta():
    rows = []
    for line in open(os.path.join(SNAP, "meta.jsonl")):
        rows.append(json.loads(line))
    rows.sort(key=lambda r: r["frame"])
    return rows


def main():
    events = [json.loads(l) for l in open(SCNLOG)]
    ev = next((e for e in events if e["config_name"] == INSTANCE), None)
    if ev is None:
        print("instance not found", INSTANCE); return
    ids = set(ev.get("actor_ids", []))
    ids.discard(None)
    meta = load_meta()

    def row_time(r):
        return r["frame"] / 20.0

    te = ev.get("game_time") or 0.0
    # decision frame: first frame in window where an owned walker is ahead & ego moving
    decision = None
    for r in meta:
        t = row_time(r)
        if t < te or t > te + 12:
            continue
        if r["ego_speed_mps"] < 1.0:
            continue
        for a in r["actors"]:
            if a["actor_id"] in ids and 5.0 < a["x"] < 45.0 and abs(a["y"]) < 5.0:
                decision = r
                break
        if decision is not None:
            break
    if decision is None:
        # fallback: any window frame with ego pos
        decision = next((r for r in meta if te <= row_time(r) <= te + 6), None)
    if decision is None:
        print("no decision frame"); return
    ex, ey = decision["ego_pos"][:2]
    yaw = math.radians(decision["ego_yaw"])
    u = (math.cos(yaw), math.sin(yaw))
    left = (-math.sin(yaw), math.cos(yaw))
    t0 = row_time(decision)
    v0 = max(decision["ego_speed_mps"], 1.0)
    print(f"decision t={t0:.1f}s frame={decision['frame']} ego_v0={v0:.1f} "
          f"walkers={sorted(ids)} pos=({ex:.1f},{ey:.1f})")

    # build occupancy: for each grid step i, nearest meta row at t0+i*0.5 after decision
    occ = OccupancyGT(N, DT)
    for wid in ids:
        s_arr, lat_arr = [], []
        for i in range(N + 1):
            target = t0 + i * 0.5
            best = None
            for r in meta:
                if row_time(r) < t0 - 0.05:
                    continue
                d = abs(row_time(r) - target)
                if best is None or d < best[0]:
                    best = (d, r)
            r = best[1] if best else None
            found = False
            if r is not None:
                px, py = r["ego_pos"][:2]
                yw = math.radians(r["ego_yaw"])
                uu = (math.cos(yw), math.sin(yw))
                ll = (-math.sin(yw), math.cos(yw))
                for a in r["actors"]:
                    if a["actor_id"] == wid:
                        wx = px + a["x"] * uu[0] + a["y"] * ll[0]
                        wy = py + a["x"] * uu[1] + a["y"] * ll[1]
                        dx, dy = wx - ex, wy - ey
                        s_arr.append(dx * u[0] + dy * u[1])
                        lat_arr.append(dx * left[0] + dy * left[1])
                        found = True
                        break
            if not found:
                s_arr.append(-1.0)
                lat_arr.append(30.0)
        occ.add_actor(np.array(s_arr), np.array(lat_arr), 0.4, 0.4)

    cor = StraightCorridor(160.0, 3.5)
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=v0, accel_set=ACCEL,
                               dt=DT, v_max=VMAX, n_steps=N, horizons_steps=HSTEPS,
                               width=100, keep_per_bucket=20, margin=0.5, T_LC=3.0)
    G0 = (P0[-1] - P0[-2]) / 2.0 if P0[-1] >= 0 and P0[-2] >= 0 else None
    print("P0(2,4,6,8)=", [round(x, 2) for x in P0], " G0=", round(G0, 3) if G0 is not None else None)
    reopen = G0 is not None and G0 > 0.05 and P0[-1] > P0[0]
    print("temporary-closure->reopen (G0>0.05 & P8>P2):", reopen)
    print("F0-3 smoke (informative):", "PASS" if reopen else "inspect")


if __name__ == "__main__":
    main()
