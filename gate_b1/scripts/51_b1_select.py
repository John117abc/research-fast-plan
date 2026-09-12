#!/usr/bin/env python3
"""B1 Step 7 selection (plant2): strict order + mechanism-stratified sampling.

Order: SDC valid -> current lane valid -> official left_neighbors valid at SDC
index -> left neighbor same-direction/geometry ok -> 8 s future complete ->
M1-M6 detection -> stratified sample. No fabricating left lanes.

usage: python gate_b1/scripts/51_b1_select.py --per-cap 80 --seed 100
"""
import argparse
import csv
import glob
import json
import math
import os
import random
import shutil
import sys
from collections import Counter

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
IN = os.path.join(B1, "canonical_b1")
OUT = os.path.join(B1, "results/b1")
SEL = os.path.join(B1, "selected")
PRIORITY = ["M1_lead_slow_stop", "M2_vehicle_crossing", "M3_vru_crossing",
            "M4_cut_in", "M5_merge", "M6_temp_occupancy"]
from adapters import waymo_adapter as wa  # noqa: E402


def detect(ego_spd, actors):
    tags, ev = [], {}
    for a in actors:
        lon, lat, spd = a["lon"], a["lat"], a["spd"]
        same = (np.abs(lat) < 1.8) & (lon > 3) & (lon < 60)
        if same.sum() >= 3 and (spd[same][-1] < 1.0 or (spd[same][0] - spd[same][-1]) > 2.0) \
                and spd[same].min() < max(1.0, 0.6 * ego_spd):
            tags.append("M1_lead_slow_stop"); ev["M1"] = round(float(spd[same].min()), 2)
        cross = (np.abs(lat) < 1.8) & (lon > -5) & (lon < 45)
        if cross.any() and (lat.max() - lat.min()) > 4.0 and lon.min() < 10:
            if a["type"] in ("pedestrian", "cyclist"):
                tags.append("M3_vru_crossing"); ev["M3"] = round(float(lat.max() - lat.min()), 2)
            elif a["type"] == "vehicle":
                tags.append("M2_vehicle_crossing"); ev["M2"] = round(float(lat.max() - lat.min()), 2)
        if abs(lat[0]) > 2.5 and (np.abs(lat) < 1.5).any() and lon.max() > 5 and lon[-1] > lon[0]:
            tags.append("M4_cut_in"); ev["M4"] = [round(float(lat[0]), 2)]
        if lon[0] < 0 and (np.abs(lat) < 1.5).any() and lon[-1] > 3:
            tags.append("M5_merge"); ev["M5"] = [round(float(lon[0]), 2), round(float(lon[-1]), 2)]
        if (np.abs(lat[0]) < 1.8) and lon[0] > 5 and (np.abs(lat) > 3.0).any():
            tags.append("M6_temp_occupancy"); ev["M6"] = round(float(lat[-1]), 2)
    tags = list(dict.fromkeys(tags))
    return next((t for t in PRIORITY if t in tags), "M0_none"), tags, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cap", type=int, default=80)
    ap.add_argument("--seed", type=int, default=100)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True); os.makedirs(SEL, exist_ok=True)
    reasons = Counter()
    accepted = []
    for path in sorted(glob.glob(os.path.join(IN, "*.json"))):
        c = wa.normalize_compact(json.load(open(path)))
        ego = wa.ego_state(c, 0)
        if not c["ego"]["frames"][0]["valid"]:
            reasons["sdc_invalid"] += 1; continue
        if len(c["ego"]["frames"]) < 17 or not all(f["valid"] for f in c["ego"]["frames"]):
            reasons["future_incomplete"] += 1; continue
        cur = wa.find_current_lane_official(ego, c["lanes"])
        if cur is None:
            reasons["no_current_lane"] += 1; continue
        nb, _ = wa.official_left_neighbor(ego, cur["lane"], cur["i_sdc"], c["lanes"])
        if nb is None:
            reasons["no_valid_left_neighbor"] += 1; continue
        # actor series in ego frame (0.5 s native)
        u = np.array([math.cos(ego["heading"]), math.sin(ego["heading"])])
        n = np.array([math.sin(ego["heading"]), -math.cos(ego["heading"])])
        actors = []
        for act in c["actors"]:
            lon, lat, spd = [], [], []
            for k, f in enumerate(act["frames"]):
                if not f["valid"]:
                    continue
                dxy = np.array([f["x"] - ego["x"], f["y"] - ego["y"]])
                lon.append(float(dxy @ u)); lat.append(float(dxy @ n))
                spd.append(math.hypot(f["vx"], f["vy"]))
            if len(lon) >= 4:
                actors.append({"type": act["type"], "lon": np.array(lon),
                               "lat": np.array(lat), "spd": np.array(spd)})
        primary, tags, ev = detect(ego["speed"], actors)
        if primary == "M0_none":
            reasons["m0_none"] += 1; continue
        reasons["accepted"] += 1
        accepted.append({"scenario_id": c["scenario_id"], "file": os.path.basename(path),
                         "primary_mechanism": primary, "auxiliary": ";".join(tags),
                         "lane_width": round(nb["lateral"], 3), "ego_speed": round(ego["speed"], 2),
                         "evidence": json.dumps(ev)})
    # stratified sample
    rng = random.Random(a.seed)
    by = {}
    for r in accepted:
        by.setdefault(r["primary_mechanism"], []).append(r)
    sel = []
    for m in PRIORITY:
        lst = by.get(m, []); rng.shuffle(lst)
        sel.extend(lst[: a.per_cap])
    for r in sel:
        shutil.copy(os.path.join(IN, r["file"]), os.path.join(SEL, r["file"]))
    with open(os.path.join(OUT, "selected_states.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sel[0].keys()))
        w.writeheader(); w.writerows(sel)
    dist = Counter(r["primary_mechanism"] for r in sel)
    json.dump({"n_accepted": len(accepted), "n_selected": len(sel),
               "selection_reasons": dict(reasons), "selected_distribution": dict(dist)},
              open(os.path.join(OUT, "selection_summary.json"), "w"), indent=1)
    print(json.dumps({"n_accepted": len(accepted), "n_selected": len(sel),
                      "selected_distribution": dict(dist), "reasons": dict(reasons)}, indent=1))


if __name__ == "__main__":
    main()
