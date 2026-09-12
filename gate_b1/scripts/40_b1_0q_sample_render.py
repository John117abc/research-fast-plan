#!/usr/bin/env python3
"""B1-0Q: sample 20/mechanism (fixed seed) + render blind QC contact sheets.

Rendering uses ONLY trajectories/relative position/speed/heading/lane geometry/
future/evidence (no R1, no kNN). One contact sheet per mechanism for visual QC.

usage: python gate_b1/scripts/40_b1_0q_sample_render.py --seed 100 --per 20
"""
import argparse
import csv
import json
import math
import os
import random
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
STEP4 = os.path.join(B1, "results/b1_0/step4_mechanism")
OUT = os.path.join(B1, "results/b1_0q")
JSON_DIR = "/mnt/2T_HDD/WaymoDatabase/data_json/training"
IDX0, HZ, STEP = 10, 80, 5
MECHS = ["M1_lead_slow_stop", "M2_vehicle_crossing", "M3_vru_crossing",
         "M4_cut_in", "M5_merge", "M6_temp_occupancy"]


def series(js, idx0=IDX0):
    o = js["objects"][js["metadata"]["sdc_track_index"]]
    p = o["position"][idx0]
    h = o["heading"][idx0]
    u = np.array([math.cos(h), math.sin(h)])
    n = np.array([math.sin(h), -math.cos(h)])
    actors = []
    for a in js["objects"]:
        if a is o:
            continue
        lon, lat, t = [], [], []
        for k in range(0, HZ + 1, STEP):
            fi = idx0 + k
            if fi >= len(a["position"]) or not a["valid"][fi]:
                continue
            dxy = np.array([a["position"][fi]["x"] - p["x"], a["position"][fi]["y"] - p["y"]])
            lon.append(float(dxy @ u)); lat.append(float(dxy @ n)); t.append(k * 0.1)
        if len(lon) >= 2:
            actors.append({"type": a.get("type", "vehicle"), "lon": np.array(lon),
                           "lat": np.array(lat), "t": np.array(t)})
    lanes = []
    for r in js["roads"]:
        if r["type"] != "lane":
            continue
        g = np.array([[q["x"], q["y"]] for q in r["geometry"]])
        dxy = g - np.array([p["x"], p["y"]])
        lanes.append({"lon": dxy @ u, "lat": dxy @ n})
    return actors, lanes


def render(ax, js, row):
    actors, lanes = series(js)
    for L in lanes:
        m = (L["lon"] > -20) & (L["lon"] < 70) & (np.abs(L["lat"]) < 15)
        if m.sum() > 1:
            ax.plot(L["lon"][m], L["lat"][m], color="0.75", lw=0.7, zorder=1)
    colors = {"vehicle": "tab:blue", "pedestrian": "tab:red", "cyclist": "tab:orange"}
    for a in actors:
        ax.plot(a["lon"], a["lat"], color=colors.get(a["type"], "k"), alpha=0.5, lw=0.8)
        ax.scatter(a["lon"][0], a["lat"][0], s=8, color=colors.get(a["type"], "k"))
    ax.scatter([0], [0], marker=">", s=40, color="green", zorder=5)
    ax.set_xlim(-15, 70); ax.set_ylim(-12, 12)
    ax.axhline(0, color="g", lw=0.5, alpha=0.4)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("%s\n%s" % (row["scenario_id"][:8], row["primary_mechanism"].split("_")[0]),
                 fontsize=6)
    ev = json.loads(row["evidence"]) if row["evidence"] else {}
    ax.text(-14, 9, json.dumps(ev)[:60], fontsize=5, color="0.3")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--per", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(STEP4, "mechanism_detections.csv"))))
    rng = random.Random(a.seed)
    sampled = []
    for mech in MECHS:
        sel = [r for r in rows if r["primary_mechanism"] == mech]
        rng.shuffle(sel)
        sel = sel[: a.per]
        for r in sel:
            sampled.append(r)
        print(mech, "sampled", len(sel), "of", sum(1 for x in rows if x["primary_mechanism"] == mech))
    with open(os.path.join(OUT, "sample_list.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_id", "mechanism", "file", "scenario_id",
                                           "ego_speed", "evidence"])
        w.writeheader()
        for i, r in enumerate(sampled):
            w.writerow({"sample_id": "S%03d" % i, "mechanism": r["primary_mechanism"],
                        "file": r["file"], "scenario_id": r["scenario_id"],
                        "ego_speed": r["ego_speed"], "evidence": r["evidence"]})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for mech in MECHS:
        sel = [r for r in sampled if r["primary_mechanism"] == mech]
        if not sel:
            continue
        ncol, nrow = 5, math.ceil(len(sel) / 5)
        fig, axes = plt.subplots(nrow, ncol, figsize=(3.0 * ncol, 2.2 * nrow))
        axes = np.atleast_1d(axes).ravel()
        for ax, r in zip(axes, sel):
            js = json.load(open(os.path.join(JSON_DIR, r["file"])))
            render(ax, js, r)
        for ax in axes[len(sel):]:
            ax.axis("off")
        fig.suptitle("B1-0Q blind QC: %s (n=%d)  green=> ego, x=lon, y=left" % (mech, len(sel)))
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        fig.savefig(os.path.join(OUT, "images", "sheet_%s.png" % mech), dpi=130)
        plt.close(fig)
    print("wrote", os.path.join(OUT, "images"))


if __name__ == "__main__":
    main()
