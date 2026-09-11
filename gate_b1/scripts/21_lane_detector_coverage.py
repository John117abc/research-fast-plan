#!/usr/bin/env python3
"""B1-0 Step 3b: left-lane detection coverage on a random JSON sample (plant2).

Estimates what fraction of data_json/training states have current lane + a clean
left-adjacent same-direction driving lane, and records exclusion reasons.

usage: python gate_b1/scripts/21_lane_detector_coverage.py --n 500 --seed 0
"""
import argparse
import csv
import glob
import json
import os
import random
import sys
from collections import Counter

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0/step3_lane_detector")
JSON_DIR = "/mnt/2T_HDD/WaymoDatabase/data_json/training"

from adapters import waymo_adapter as wa  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    random.Random(a.seed).shuffle(files)
    files = files[: a.n]
    rows, reasons = [], Counter()
    for f in files:
        js = json.load(open(f))
        ego = wa.ego_state_from_json(js)
        lanes = wa.json_lanes(js)
        if not ego.get("valid", True):
            reasons["sdc_invalid"] += 1
            continue
        el = wa.find_ego_lane(ego, lanes)
        if el is None:
            reasons["no_ego_lane"] += 1
            continue
        ll = wa.find_left_lane(ego, el, lanes)
        if ll is None:
            reasons["no_left_lane"] += 1
            continue
        reasons["ok"] += 1
        rows.append({"file": os.path.basename(f), "scenario_id": js["scenario_id"],
                     "ego_lane_id": el["lane"]["id"], "ego_lat": round(el["lat"], 3),
                     "left_lane_id": ll["lane"]["id"], "left_lat": round(ll["lat"], 3),
                     "lane_width": round(ll["lane_width"], 3),
                     "ego_speed": round(ego["speed"], 3)})
    with open(os.path.join(OUT, "lane_coverage_sample.csv"), "w", newline="") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    summ = {"n_sampled": len(files), "reasons": dict(reasons),
            "coverage": round(reasons["ok"] / max(1, len(files)), 4)}
    json.dump(summ, open(os.path.join(OUT, "lane_coverage_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
