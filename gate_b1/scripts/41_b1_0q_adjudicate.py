#!/usr/bin/env python3
"""B1-0Q adjudication: independent evidence-based re-check of the 6 detectors.

Machine review only (uses trajectories/relative position/speed/heading/lane
geometry; NOT R1). For each sampled state an independent stricter rule decides
correct / wrong / ambiguous. Visualizations are kept for human confirmation.

usage: python gate_b1/scripts/41_b1_0q_adjudicate.py
"""
import csv
import json
import math
import os
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0q")
JSON_DIR = "/mnt/2T_HDD/WaymoDatabase/data_json/training"
IDX0, HZ, STEP = 10, 80, 5


def series(js):
    o = js["objects"][js["metadata"]["sdc_track_index"]]
    p = o["position"][IDX0]; h = o["heading"][IDX0]
    u = np.array([math.cos(h), math.sin(h)]); n = np.array([math.sin(h), -math.cos(h)])
    out = []
    for a in js["objects"]:
        if a is o:
            continue
        lon, lat, spd = [], [], []
        for k in range(0, HZ + 1, STEP):
            fi = IDX0 + k
            if fi >= len(a["position"]) or not a["valid"][fi]:
                continue
            dxy = np.array([a["position"][fi]["x"] - p["x"], a["position"][fi]["y"] - p["y"]])
            lon.append(float(dxy @ u)); lat.append(float(dxy @ n))
            spd.append(math.hypot(a["velocity"][fi]["x"], a["velocity"][fi]["y"]))
        if len(lon) >= 4:
            out.append({"type": a.get("type", "vehicle"), "lon": np.array(lon),
                        "lat": np.array(lat), "spd": np.array(spd)})
    return out


def rule(mech, ego_spd, actors):
    """Independent stricter check. Returns (verdict, reason)."""
    def near(v, thr, frac=0.25):
        return abs(v - thr) <= abs(thr) * frac
    for a in actors:
        lon, lat, spd = a["lon"], a["lat"], a["spd"]
        if mech == "M1_lead_slow_stop":
            same = (np.abs(lat) < 1.5) & (lon > 5) & (lon < 50)
            if same.sum() >= 3:
                stop = spd[same][-1] < 0.5
                drop = (spd[same][0] - spd[same][-1]) > 3.0
                if stop or drop:
                    return "correct", "lead same-lane stop/drop"
                if spd[same].min() < 1.0 or (spd[same][0] - spd[same][-1]) > 2.0:
                    return "ambiguous", "lead borderline slow"
        if mech in ("M2_vehicle_crossing", "M3_vru_crossing"):
            want = "vehicle" if mech.startswith("M2") else ("pedestrian", "cyclist")
            ok_type = a["type"] == want if isinstance(want, str) else a["type"] in want
            if ok_type:
                inlane = (np.abs(lat) < 1.8) & (lon > -5) & (lon < 45)
                if inlane.any() and (lat.max() - lat.min()) > 5.0:
                    return "correct", "lateral sweep across lane"
                if inlane.any() and (lat.max() - lat.min()) > 3.0:
                    return "ambiguous", "small lateral sweep"
        if mech == "M4_cut_in":
            if abs(lat[0]) > 2.0 and (np.abs(lat) < 1.0).any() and lon.max() > 5:
                return "correct", "adjacent -> ego lane ahead"
            if abs(lat[0]) > 1.5 and (np.abs(lat) < 1.5).any() and lon.max() > 5:
                return "ambiguous", "partial cut-in"
        if mech == "M5_merge":
            if lon[0] < -5 and lon[-1] > 5 and abs(lat[-1]) < 1.5:
                return "correct", "from behind into ego lane ahead"
            if lon[0] < 0 and lon[-1] > 3 and abs(lat[-1]) < 2.0:
                return "ambiguous", "weak merge"
        if mech == "M6_temp_occupancy":
            if abs(lat[0]) < 1.5 and lon[0] > 5 and (np.abs(lat) > 3.5).any():
                return "correct", "in-lane then leaves"
            if abs(lat[0]) < 2.0 and lon[0] > 5 and (np.abs(lat) > 2.5).any():
                return "ambiguous", "partial leave"
    return "wrong", "no actor satisfies independent rule"


def main():
    rows = list(csv.DictReader(open(os.path.join(OUT, "sample_list.csv"))))
    out, agg = [], {}
    for r in rows:
        js = json.load(open(os.path.join(JSON_DIR, r["file"])))
        o = js["objects"][js["metadata"]["sdc_track_index"]]
        ego_spd = math.hypot(o["velocity"][IDX0]["x"], o["velocity"][IDX0]["y"])
        v, reason = rule(r["mechanism"], ego_spd, series(js))
        out.append({**r, "verdict": v, "reason": reason})
        agg.setdefault(r["mechanism"], {"correct": 0, "wrong": 0, "ambiguous": 0})[v] += 1
    with open(os.path.join(OUT, "review_machine.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    stats = {}
    for mech, c in agg.items():
        denom = c["correct"] + c["wrong"]
        stats[mech] = {**c, "n_checked": sum(c.values()),
                       "clear_precision": round(c["correct"] / denom, 3) if denom else None}
    json.dump(stats, open(os.path.join(OUT, "qc_stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
