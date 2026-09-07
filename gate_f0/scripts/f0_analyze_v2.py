#!/usr/bin/env python3
"""Gate F0 pilot analysis v2 (frozen semantics).

Decision rule (frozen, case-agnostic "scenario trigger"): the first recorded
frame in which ego is moving (v>1.5) with the scenario target already present.

Frame semantics:
  t0 -> ego s0 = 0 ; all actor occupancy rebuilt relative (s - s_dec).
  Occupancy sampled at k*0.5 s up to 10 s; only future transitions are
  collision-checked (engine checks occupancy from first expansion on).
Margins apply only to future expansion.
Outputs per run: P0(t),PL(t) at 0.5..10 s and windowed G (4-6,6-8,8-10).
"""
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from feasible.engine import StraightCorridor, OccupancyGT, compute_frontiers  # noqa: E402

DT = 0.5
ACCEL = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
HMAX = 10.0
N = int(HMAX / DT)                 # 20
H_WIN = [4, 6, 8, 10]
FINE = [h / 2 for h in range(1, int(HMAX * 2) + 1)]  # 0.5..10 step .5
SEG = json.load(open("gate_f0/road_segment.json"))
ox, oy = SEG["origin"]
th = SEG["heading_rad"]
u = (math.cos(th), math.sin(th))
n = (-math.sin(th), math.cos(th))
W = float(np.mean([math.hypot(SEG["c0"][i][0] - SEG["cl"][i][0],
                              SEG["c0"][i][1] - SEG["cl"][i][1])
                   for i in range(0, 60, 2)]))


def local(x, y):
    dx, dy = x - ox, y - oy
    return dx * u[0] + dy * u[1], dx * n[0] + dy * n[1]


def load(path):
    rows = []
    for line in open(path):
        rows.append(json.loads(line))
    rows.sort(key=lambda r: r["sim_t"])
    return rows


def halfs(row, actor_id):
    for a in row["actors"]:
        if a["actor_id"] == actor_id:
            e = a["bbox"]["extent"]
            return float(e[0]), float(e[1])
    return 0.4, 0.4


def reach_time(D, v0, a=1.5, vmax=VMAX):
    if D <= 0:
        return 0.0
    tacc = max(0.0, (vmax - v0) / a)
    dacc = v0 * tacc + 0.5 * a * tacc * tacc
    if dacc >= D:
        return (-v0 + math.sqrt(max(0.0, v0 * v0 + 2 * a * D))) / a
    return tacc + (D - dacc) / vmax


def in_lane_times(rows, tgt, t0, horizon=8.0):
    """(start, end) absolute times within (t0,t0+horizon) target is in-lane."""
    starts, ends = [], []
    for r in rows:
        t = r["sim_t"]
        if t <= t0 or t > t0 + horizon:
            continue
        hit = next((a for a in r["actors"] if a["actor_id"] == tgt), None)
        if hit is None:
            continue
        _, ly = local(hit["transform"]["x"], hit["transform"]["y"])
        if abs(ly) < 2.2:
            starts.append(t)
            ends.append(t)
    if not starts:
        return None
    return (min(starts), max(ends))


def shape_metrics(P):
    """Detect a stall plateau in fine P0 series then resumed growth."""
    inc = [P[k] - P[k - 1] for k in range(1, len(P))]  # per 0.5 s
    best_len, best_start = 0, -1
    cur_len = cur_start = 0
    for k, d in enumerate(inc):
        if P[k] >= 0 and d < 0.4:           # <0.8 m/s stall
            if cur_len == 0:
                cur_start = k
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
    plateau = None
    resumed = None
    if best_len >= 3 and best_start >= 0:   # >=1.5 s plateau
        e = best_start + best_len
        plateau = round(best_len * DT, 2)
        # resumed slope right after plateau end (per 0.5 s)
        if e < len(P) - 1 and P[e] >= 0 and P[e + 1] >= 0:
            resumed = round((P[e + 1] - P[e]) / DT, 2)
    return {"plateau_sec": plateau, "resumed_slope": resumed}


def pick(rows, t_target):
    best = min(rows, key=lambda r: abs(r["sim_t"] - t_target))
    return best if abs(best["sim_t"] - t_target) < 0.4 else None


def ego_s_of(r):
    e = r["ego"]["transform"]
    return local(e["x"], e["y"])[0]


def analyze(path):
    rows = load(path)
    if len(rows) < 2:
        return None
    meta = rows[0]["scenario"]
    case = meta["case"]
    tgt = meta["target_actor_ids"][0] if meta.get("target_actor_ids") else None

    def ego_s(r):
        e = r["ego"]["transform"]
        return local(e["x"], e["y"])[0]

    # unified frozen decision rule: interaction-onset.
    # Decision = first frame where the ego's earliest reachable pass time
    # (t_min to the target's conflict longitude) precedes the end of the target's
    # future in-lane occupancy window within the horizon (i.e. it starts to matter).
    dec = None
    last_relevant = None
    for r in rows:
        if r["ego"]["speed_mps"] < 1.0:      # decisionable frames only (ego still has control)
            continue
        t = r["sim_t"]
        D = abs((meta.get("L") or meta.get("Lc")) - ego_s_of(r))
        tmin = reach_time(D, max(r["ego"]["speed_mps"], 0.5))
        if case == "static_blocker":
            if tmin < 8.0:
                dec = r
                break
        else:
            win = in_lane_times(rows, tgt, t, 8.0)
            if win is not None:
                bs, be = win
                if bs < t + tmin < be:
                    dec = r
                    break
        last_relevant = r
    if dec is None:
        dec = last_relevant if last_relevant is not None else rows[len(rows) // 4]
    t_dec = dec["sim_t"]
    v0 = max(dec["ego"]["speed_mps"], 0.5)
    s_dec = ego_s(dec)
    hl, hw = halfs(dec, tgt) if tgt else (0.4, 0.4)

    # relative occupancy over [0 .. HMAX]
    s_arr, lat_arr = [], []
    for i in range(N + 1):
        tt = t_dec + i * DT
        best = pick(rows, tt)
        if best is None or tgt is None:
            s_arr.append(-1.0); lat_arr.append(30.0)
            continue
        hit = next((a for a in best["actors"] if a["actor_id"] == tgt), None)
        if hit is None:
            s_arr.append(-1.0); lat_arr.append(30.0)
        else:
            sx, ly = local(hit["transform"]["x"], hit["transform"]["y"])
            s_arr.append(sx - s_dec)
            lat_arr.append(ly)
    occ = OccupancyGT(N, DT)
    occ.add_actor(np.array(s_arr), np.array(lat_arr), hl, hw)

    cor = StraightCorridor(max(float(SEG["length_m"]) - s_dec, 60.0), float(W))
    # fine frontiers for plotting & windowed G
    fine_steps = [int(h / DT) for h in FINE]
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=v0, accel_set=ACCEL,
                               dt=DT, v_max=VMAX, n_steps=N,
                               horizons_steps=fine_steps, width=100,
                               keep_per_bucket=20, margin=0.5, T_LC=3.0)

    def G_from(idx_a, idx_b):
        a_idx = int((idx_b - 1) / 2)  # mapping below
        return None

    def g(a_h, b_h):
        ia, ib = int(a_h / DT) - 1, int(b_h / DT) - 1
        if P0[ia] < 0 or P0[ib] < 0:
            return None
        return (P0[ib] - P0[ia]) / (b_h - a_h)

    return {"case": case, "seed": meta["seed"], "t_dec": t_dec, "v0": v0,
            "P0": P0, "PL": PL,
            "G46": g(4, 6), "G68": g(6, 8), "G810": g(8, 10),
            "P0_8": P0[int(8 / DT) - 1], "PL_8": PL[int(8 / DT) - 1],
            "P0_10": P0[int(10 / DT) - 1], "PL_10": PL[int(10 / DT) - 1],
            **shape_metrics(P0)}


def main():
    import csv
    rows = []
    for case in ("static_blocker", "temp_crossing"):
        for f in sorted(glob.glob(f"gate_f0/results/pilot/{case}/seed*.ndjson")):
            r = analyze(f)
            if r:
                rows.append({**r, "file": f})
    # drop P0/PL huge arrays from csv, keep fine series in a side json
    slim = []
    for r in rows:
        slim.append({k: v for k, v in r.items()
                     if k not in ("P0", "PL")})
    with open("gate_f0/results/pilot_summary_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(slim[0].keys()))
        w.writeheader()
        for s in slim:
            s = dict(s)
            s["G46"] = round(s["G46"], 3) if s["G46"] is not None else ""
            s["G68"] = round(s["G68"], 3) if s["G68"] is not None else ""
            s["G810"] = round(s["G810"], 3) if s["G810"] is not None else ""
            for k in ("P0_8", "PL_8", "P0_10", "PL_10"):
                s[k] = round(s[k], 2)
            w.writerow(s)
    # fine series dump
    with open("gate_f0/results/pilot_frontiers_v2.json", "w") as fh:
        json.dump([{"case": r["case"], "seed": r["seed"],
                    "t": FINE, "P0": [round(x, 2) for x in r["P0"]],
                    "PL": [round(x, 2) if x >= 0 else None for x in r["PL"]]}
                   for r in rows], fh, indent=1)
    print(f"wrote pilot_summary_v2.csv ({len(rows)}) and pilot_frontiers_v2.json")
    for r in rows:
        print(f"{r['case']:14s} s{r['seed']} v0={r['v0']:.1f} "
              f"G4-6={r['G46']} G6-8={r['G68']} G8-10={r['G810']} "
              f"P0_10={r['P0_10']:.1f} PL_10={r['PL_10']:.1f}")


if __name__ == "__main__":
    main()
