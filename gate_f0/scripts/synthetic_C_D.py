#!/usr/bin/env python3
"""Gate F0 synthetic C/D (offline) using the verified engine.

C: SlowLead + free left  -> both progress alive  (Lateral Optional)
D: static blocker C0 + left-lane dense stream (CL full occupancy over horizon)
                            -> both dead           (Contingency / wait)
Also recomputes A (temporary closure, current alive) and B (static+free left)
reference cells to complete the (G0,GL) quadrant table.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from feasible.engine import StraightCorridor, OccupancyGT, compute_frontiers  # noqa: E402

DT = 0.5
HMAX = 10.0
N = int(HMAX / DT)
SEG = json.load(open("gate_f0/road_segment.json"))
W = float(np.mean([math.hypot(SEG["c0"][i][0] - SEG["cl"][i][0],
                              SEG["c0"][i][1] - SEG["cl"][i][1])
                   for i in range(0, 60, 2)]))
EPS = 0.10


def run_with(actors, v0=6.0):
    """actors: list of (s_series_or_call, lat, half_len, half_wid, dynamic?)"""
    occ = OccupancyGT(N, DT)
    for (s_fn, lat, hl, hw) in actors:
        s_arr, lat_arr = [], []
        for i in range(N + 1):
            t = i * DT
            s = s_fn(t)
            s_arr.append(s)
            lat_arr.append(lat if s is not None else 30.0)
        occ.add_actor(np.array(s_arr, dtype=float),
                      np.array(lat_arr, dtype=float), hl, hw)
    cor = StraightCorridor(200.0, float(W))
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=v0, accel_set=(-4, -2, 0, 1.5),
                               dt=DT, v_max=12.0, n_steps=N,
                               horizons_steps=[int(x / DT) for x in (8, 10)],
                               width=100, keep_per_bucket=20, margin=0.5, T_LC=3.0)
    G0 = (P0[1] - P0[0]) / 2.0
    GL = (PL[1] - PL[0]) / 2.0 if (PL[0] >= 0 and PL[1] >= 0) else None
    return G0, GL


def const(s):      # static occupancy at s, present whole horizon
    return lambda t: float(s)


def moving(s0, v):  # lead moving at constant v
    return lambda t: float(s0) + v * t


def barrier(Ts, Te, s_c):  # temporary full-lane closure
    return lambda t: float(s_c) if Ts <= t <= Te else None


def main():
    cells = []
    # A reference (temporary closure, current alive) - s_c=30 dur4
    occA = [(barrier(1.0, 5.0, 30.0), 0.0, 2.0, 1.0)]
    g0A, gLA = run_with(occA)
    # B reference (static C0 blocker, free left)
    g0B, gLB = run_with([(const(30.0), 0.0, 2.0, 1.0)])
    # C: slow lead on C0 (moving 3 m/s from 22m) + free left
    for vlead, s0lead in ((3.0, 22.0), (2.5, 25.0), (4.0, 30.0)):
        occC = [(moving(s0lead, vlead), 0.0, 2.2, 1.0)]
        g0C, gLC = run_with(occC)
        cells.append(("C", dict(vlead=vlead, s0=s0lead), g0C, gLC))
    # D: static C0 blocker (30m) + CL dense stream wall whole horizon
    for cl_off in (W,):
        occD = [(const(30.0), 0.0, 2.0, 1.0),
                (const(8.0), cl_off, 100.0, 0.9)]
        g0D, gLD = run_with(occD)
        cells.append(("D", {"cl_wall": True}, g0D, gLD))
    # LongitudinalSufficient: temporary closure on current (alive) + CL blocked
    g0E, gLE = run_with([(barrier(1.0, 5.0, 30.0), 0.0, 2.0, 1.0),
                         (const(8.0), W, 100.0, 0.9)])

    import csv
    rows = []
    def add(tag, params, g0, gl):
        rows.append({"archetype": tag, "params": str(params),
                     "G0": round(g0, 3), "GL": round(gl, 3) if gl is not None else "",
                     "quadrant": quadrant(g0, gl)})
    add("A(temporary)", {"s_c": 30, "win": [1, 5]}, g0A, gLA)
    add("B(static+freeLeft)", {"s_c": 30}, g0B, gLB)
    add("A'longSuff(clWall)", {"s_c": 30, "cl": "blocked"}, g0E, gLE)
    for tag, p, g0, gl in cells:
        add(tag, p, g0, gl)
    with open("gate_f0/results/synthetic_C_D_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["archetype", "params", "G0", "GL", "quadrant"])
        w.writeheader()
        w.writerows(rows)
    print(f"{'archetype':24s} {'G0':>7} {'GL':>8}  quadrant")
    for r in rows:
        print(f"{r['archetype']:24s} {r['G0']:>7} {str(r['GL']):>8}  {r['quadrant']}")
    print("\nwrote synthetic_C_D_summary.csv")


def quadrant(g0, gl):
    a0 = g0 > EPS
    al = (gl is not None and gl > EPS)
    if a0 and not al:
        return "LongitudinalSufficient"
    if not a0 and al:
        return "LateralNecessary"
    if a0 and al:
        return "LateralOptional"
    return "Contingency/Wait"


if __name__ == "__main__":
    main()
