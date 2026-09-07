#!/usr/bin/env python3
"""Gate F0 - offline Synthetic TemporaryBarrier (A archetype, no CARLA).

Frozen Town12 corridor geometry. A full-lane barrier occupies C0 at conflict
distance s_c during [Ts, Te] (relative to decision t0); otherwise clear.
Checks P0(t): growth -> plateau (closure) -> resumed growth, at H=10 s.
Sweeps closure duration x conflict distance (+Ts/v0 cells).
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
FINE = [0.5 * (k + 1) for k in range(N)]


def shape_metrics(P):
    inc = [P[k] - P[k - 1] for k in range(1, len(P))]
    best_len, best_start, cur_len, cur_start = 0, -1, 0, 0
    for k, d in enumerate(inc):
        if P[k] >= 0 and d < 0.4:
            if cur_len == 0:
                cur_start = k
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
    plateau = None
    if best_len >= 3:
        plateau = round(best_len * DT, 2)
    return plateau


def run(s_c, Ts, Te, v0=6.0):
    occ = OccupancyGT(N, DT)
    s_arr, lat_arr = [], []
    for i in range(N + 1):
        t = i * DT
        if Ts <= t <= Te:
            s_arr.append(float(s_c))
            lat_arr.append(0.0)
        else:
            s_arr.append(-1.0)
            lat_arr.append(30.0)
    occ.add_actor(np.array(s_arr), np.array(lat_arr), 2.0, 1.0)
    cor = StraightCorridor(200.0, float(W))
    steps = [int(h / DT) for h in FINE]
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=v0, accel_set=(-4, -2, 0, 1.5),
                               dt=DT, v_max=12.0, n_steps=N, horizons_steps=steps,
                               width=100, keep_per_bucket=20, margin=0.5, T_LC=3.0)
    plateau = shape_metrics(P0)
    # metrics
    def p(h):
        return P0[int(h / DT) - 1]
    return {"P0": P0, "plateau": plateau,
            "P6": p(6), "P8": p(8), "P10": p(10),
            "G810": (p(10) - p(8)) / 2.0}


def main():
    combos = []
    for s_c in (20, 30, 40):
        for dur in (2, 3, 4):
            combos.append({"s_c": s_c, "Ts": 1.0, "dur": dur, "v0": 6.0})
    combos += [{"s_c": 40, "Ts": 0.6, "dur": 3, "v0": 6.0},
               {"s_c": 40, "Ts": 1.4, "dur": 3, "v0": 6.0},
               {"s_c": 30, "Ts": 1.0, "dur": 3, "v0": 4.0},
               {"s_c": 30, "Ts": 1.0, "dur": 3, "v0": 8.0}]
    rows = []
    for c in combos:
        r = run(c["s_c"], c["Ts"], c["Ts"] + c["dur"], c["v0"])
        growth0 = r["P0"][int(c["Ts"] / DT)] > 0.5   # moved before closure
        resumed = r["G810"] is not None and r["G810"] > 0.5 and r["P10"] > r["P8"]
        rows.append({"s_c": c["s_c"], "Ts": c["Ts"], "dur": c["dur"], "v0": c["v0"],
                     "plateau_sec": r["plateau"], "P6": round(r["P6"], 1),
                     "P8": round(r["P8"], 1), "P10": round(r["P10"], 1),
                     "G810": round(r["G810"], 2),
                     "closure_pattern": bool(r["plateau"] and resumed)})
    import csv
    with open("gate_f0/results/synthetic_A_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{'s_c':>4} {'Ts':>4} {'dur':>4} {'v0':>4} | {'plateau':>8} {'P6':>5} {'P8':>5} {'P10':>6} {'G810':>6} {'closure':>8}")
    for r in rows:
        print(f"{r['s_c']:>4} {r['Ts']:>4.1f} {r['dur']:>4} {r['v0']:>4} | "
              f"{str(r['plateau_sec']):>8} {r['P6']:>5} {r['P8']:>5} {r['P10']:>6} "
              f"{r['G810']:>6} {r['closure_pattern']!s:>8}")
    n_closure = sum(1 for r in rows if r["closure_pattern"])
    print(f"\nclosure_pattern count: {n_closure}/{len(rows)}  (wrote synthetic_A_summary.csv)")


if __name__ == "__main__":
    main()
