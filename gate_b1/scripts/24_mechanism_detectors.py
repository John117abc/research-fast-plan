#!/usr/bin/env python3
"""B1-0 Step 4: M1-M7 mechanism detectors smoke (plant2, JSON discovery layer).

Detectors are reproducible geometric/kinematic rules over the 8 s future in the
ego frame. Waymo metadata is auxiliary only. primary_mechanism = highest
priority match; auxiliary_mechanism_tags = all matches; detector_evidence saved.
No manual labels; ~20 samples/mechanism are dumped for human QC only.

usage: python gate_b1/scripts/24_mechanism_detectors.py --n 1500 --seed 0
"""
import argparse
import csv
import glob
import json
import math
import os
import random
import sys
from collections import Counter

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0/step4_mechanism")
JSON_DIR = "/mnt/2T_HDD/WaymoDatabase/data_json/training"
IDX0, HZ, STEP = 10, 80, 5   # decision frame; 8 s at 10 Hz; sample every 0.5 s

PRIORITY = ["M1_lead_slow_stop", "M2_vehicle_crossing", "M3_vru_crossing",
            "M4_cut_in", "M5_merge", "M6_temp_occupancy"]


def ego_frame(js, idx0=IDX0):
    o = js["objects"][js["metadata"]["sdc_track_index"]]
    p = o["position"][idx0]
    h = o["heading"][idx0]
    u = np.array([math.cos(h), math.sin(h)])
    n = np.array([math.sin(h), -math.cos(h)])
    return o, p, h, u, n


def actor_series(js, o, p, u, n, idx0=IDX0):
    out = []
    for a in js["objects"]:
        if a is o:
            continue
        typ = a.get("type", "vehicle")
        lon, lat, spd, valid = [], [], [], []
        for k in range(0, HZ + 1, STEP):
            fi = idx0 + k
            if fi >= len(a["position"]):
                break
            if not a["valid"][fi]:
                continue
            dxy = np.array([a["position"][fi]["x"] - p["x"], a["position"][fi]["y"] - p["y"]])
            lon.append(float(dxy @ u))
            lat.append(float(dxy @ n))
            spd.append(math.hypot(a["velocity"][fi]["x"], a["velocity"][fi]["y"]))
            valid.append(k * 0.1)
        if len(lon) >= 4:
            out.append({"type": typ, "lon": np.array(lon), "lat": np.array(lat),
                        "spd": np.array(spd), "t": np.array(valid)})
    return out


def detect(ego_spd, actors):
    tags, ev = [], {}
    for a in actors:
        lon, lat, spd = a["lon"], a["lat"], a["spd"]
        ahead = lon > 3
        # M1 lead slow/stop (same lane ahead)
        same = (np.abs(lat) < 1.8) & ahead & (lon < 60)
        if same.sum() >= 3 and (spd[same][-1] < 1.0 or (spd[same][0] - spd[same][-1]) > 2.0) \
                and spd[same].min() < max(1.0, 0.6 * ego_spd):
            tags.append("M1_lead_slow_stop")
            ev["M1"] = {"min_spd": round(float(spd[same].min()), 2),
                        "dspd": round(float(spd[same][0] - spd[same][-1]), 2)}
        # crossing: lateral sweep across ego lane
        cross = (np.abs(lat) < 1.8) & (lon > -5) & (lon < 45)
        if cross.any() and (lat.max() - lat.min()) > 4.0 and lon.min() < 10:
            if a["type"] in ("pedestrian", "cyclist"):
                tags.append("M3_vru_crossing")
                ev["M3"] = {"lat_span": round(float(lat.max() - lat.min()), 2)}
            elif a["type"] == "vehicle":
                tags.append("M2_vehicle_crossing")
                ev["M2"] = {"lat_span": round(float(lat.max() - lat.min()), 2)}
        # cut-in: starts adjacent, enters ego lane ahead
        adj0 = abs(lat[0]) > 2.5
        if adj0 and (np.abs(lat) < 1.5).any() and lon.max() > 5 and lon[-1] > lon[0]:
            tags.append("M4_cut_in")
            ev["M4"] = {"lat0": round(float(lat[0]), 2), "lat_min": round(float(np.abs(lat).min()), 2)}
        # merge: from behind (lon<0) into ego lane ahead
        if lon[0] < 0 and (np.abs(lat) < 1.5).any() and lon[-1] > 3:
            tags.append("M5_merge")
            ev["M5"] = {"lon0": round(float(lon[0]), 2), "lon_end": round(float(lon[-1]), 2)}
        # temp occupancy: in-lane ahead then leaves
        inlane0 = (np.abs(lat[0]) < 1.8) and lon[0] > 5
        if inlane0 and (np.abs(lat) > 3.0).any():
            tags.append("M6_temp_occupancy")
            ev["M6"] = {"lat_end": round(float(lat[-1]), 2)}
    tags = list(dict.fromkeys(tags))
    primary = next((t for t in PRIORITY if t in tags), "M0_none")
    return primary, tags, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    random.Random(a.seed).shuffle(files)
    files = files[: a.n]
    rows = []
    for f in files:
        js = json.load(open(f))
        o, p, h, u, n = ego_frame(js)
        if not o["valid"][IDX0]:
            continue
        ego_spd = math.hypot(o["velocity"][IDX0]["x"], o["velocity"][IDX0]["y"])
        actors = actor_series(js, o, p, u, n)
        primary, tags, ev = detect(ego_spd, actors)
        rows.append({"file": os.path.basename(f), "scenario_id": js["scenario_id"],
                     "ego_speed": round(ego_spd, 2), "primary_mechanism": primary,
                     "auxiliary_mechanism_tags": ";".join(tags),
                     "n_actors": len(actors), "evidence": json.dumps(ev)})
    with open(os.path.join(OUT, "mechanism_detections.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    dist = Counter(r["primary_mechanism"] for r in rows)
    summ = {"n_states": len(rows), "primary_distribution": dict(dist),
            "coverage_non_none": round(sum(v for k, v in dist.items() if k != "M0_none") / max(1, len(rows)), 4)}
    json.dump(summ, open(os.path.join(OUT, "mechanism_distribution.json"), "w"), indent=1)
    # dump ~20 samples per primary mechanism for manual QC
    os.makedirs(os.path.join(OUT, "qc_samples"), exist_ok=True)
    for mech in PRIORITY + ["M0_none"]:
        sel = [r for r in rows if r["primary_mechanism"] == mech][:20]
        if sel:
            with open(os.path.join(OUT, "qc_samples", "%s.csv" % mech), "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(sel[0].keys()))
                w.writeheader()
                w.writerows(sel)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
