#!/usr/bin/env python3
"""Gate F0 pilot offline analysis.

For each recorded run ndjson: pick a decision frame, rebuild target-actor GT
occupancy over the next 8 s in corridor-local coords, run the feasible engine
and output P0/PL(2/4/6/8), G0/GL, and a Progress Frontier figure.
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
HSTEPS = [int(h / DT) for h in (2, 4, 6, 8)]
SEG = json.load(open("gate_f0/road_segment.json"))
ox, oy = SEG["origin"]
th = SEG["heading_rad"]
u = (math.cos(th), math.sin(th))
n = (-math.sin(th), math.cos(th))
# lane width = mean separation c0<->cl over first 60 m
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


def analyze(path):
    rows = load(path)
    if len(rows) < 2:
        return None
    meta = rows[0]["scenario"]
    case = meta["case"]
    tgt = meta["target_actor_ids"][0] if meta.get("target_actor_ids") else None
    # decision frame
    def ego_s(r):
        e = r["ego"]["transform"]
        return local(e["x"], e["y"])[0]
    dec = None
    if case == "static_blocker":
        L = meta["L"]
        cands = [r for r in rows
                 if r["ego"]["speed_mps"] > 2.0 and 6.0 < (L - ego_s(r)) < 14.0]
        if cands:
            dec = max(cands, key=lambda r: r["sim_t"])  # latest still-moving, imminent
        else:
            cands = [r for r in rows if r["ego"]["speed_mps"] > 1.5 and
                     4.0 < (L - ego_s(r)) < 16.0]
            dec = max(cands, key=lambda r: r["sim_t"]) if cands else None
            if dec is None:
                for r in rows:
                    if r["ego"]["speed_mps"] > 1.0 and (L - ego_s(r)) > 4:
                        dec = r
    else:
        # decision just as ego starts stopping for the crossing (mid closure)
        moved = False
        for r in rows:
            if r["ego"]["speed_mps"] > 3.0:
                moved = True
            if moved and r["ego"]["speed_mps"] < 1.8 and ego_s(r) < meta["Lc"]:
                dec = r
                break
        if dec is None:
            Lc = meta["Lc"]
            for r in rows:
                gap = Lc - ego_s(r)
                if 8.0 < gap < 18.0 and r["ego"]["speed_mps"] > 1.2:
                    dec = r
                    break
    if dec is None:
        # fallback: earliest frame with speed>1 and still >4m ahead
        for r in rows:
            if r["ego"]["speed_mps"] > 1.5 and ( (meta.get('L', meta.get('Lc', 50)) if case=='static_blocker' else meta.get('Lc')) - ego_s(r)) > 4:
                dec = r
                break
    if dec is None:
        dec = rows[len(rows) // 3]
    t_dec = dec["sim_t"]
    v0 = dec["ego"]["speed_mps"]
    s_dec = ego_s(dec)
    hl, hw = halfs(dec, tgt) if tgt else (0.4, 0.4)
    # occupancy grid
    n_occ = []
    s_arr, lat_arr = [], []
    for i in range(17):
        tt = t_dec + i * 0.5
        best = min(rows, key=lambda r: abs(r["sim_t"] - tt) if r["sim_t"] >= t_dec - 0.01 else 1e9)
        if abs(best["sim_t"] - tt) > 0.4 or tgt is None:
            s_arr.append(-1.0); lat_arr.append(30.0); continue
        hit = next((a for a in best["actors"] if a["actor_id"] == tgt), None)
        if hit is None:
            s_arr.append(-1.0); lat_arr.append(30.0)
        else:
            sx, ly = local(hit["transform"]["x"], hit["transform"]["y"])
            s_arr.append(sx - s_dec); lat_arr.append(ly)
    occ = OccupancyGT(16, DT)
    occ.add_actor(np.array(s_arr), np.array(lat_arr), hl, hw)
    cor = StraightCorridor(float(SEG["length_m"]), float(W))
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=max(v0, 0.5), accel_set=ACCEL,
                               dt=DT, v_max=VMAX, n_steps=16, horizons_steps=HSTEPS,
                               width=100, keep_per_bucket=20, margin=0.5, T_LC=3.0)
    G0 = (P0[-1] - P0[-2]) / 2.0
    GL = (PL[-1] - PL[-2]) / 2.0 if PL[-1] >= 0 and PL[-2] >= 0 else None
    return {"case": case, "seed": meta["seed"], "t_dec": t_dec, "v0": v0,
            "P0": P0, "PL": PL, "G0": G0, "GL": GL}


def main():
    import csv
    out = "gate_f0/results/pilot_summary.csv"
    rows = []
    for case in ("static_blocker", "temp_crossing"):
        for f in sorted(glob.glob(f"gate_f0/results/pilot/{case}/seed*.ndjson")):
            r = analyze(f)
            if r is None:
                continue
            rows.append({**r, "file": f})
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "seed", "file", "t_dec", "v0",
                                           "G0", "GL"] + [f"P0_{h}" for h in (2, 4, 6, 8)] +
                                           [f"PL_{h}" for h in (2, 4, 6, 8)])
        w.writeheader()
        for r in rows:
            row = {"case": r["case"], "seed": r["seed"], "file": r["file"],
                   "t_dec": round(r["t_dec"], 2), "v0": round(r["v0"], 2),
                   "G0": round(r["G0"], 3), "GL": round(r["GL"], 3) if r["GL"] is not None else ""}
            for i, h in enumerate((2, 4, 6, 8)):
                row[f"P0_{h}"] = round(r["P0"][i], 2)
                row[f"PL_{h}"] = round(r["PL"][i], 2) if r["PL"][i] >= 0 else ""
            w.writerow(row)
    print("wrote", out, len(rows), "runs")
    for r in rows:
        print(f"{r['case']:14s} seed{r['seed']} v0={r['v0']:.1f} "
              f"P0={[round(x,1) for x in r['P0']]} PL={[round(x,1) if x>=0 else None for x in r['PL']]} "
              f"G0={r['G0']:.2f} GL={r['GL'] if r['GL'] is None else round(r['GL'],2)}")


if __name__ == "__main__":
    main()
