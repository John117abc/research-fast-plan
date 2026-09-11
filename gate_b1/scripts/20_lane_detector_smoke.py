#!/usr/bin/env python3
"""B1-0 Step 3: left-adjacent same-direction lane detection smoke (plant2).

usage: python gate_b1/scripts/20_lane_detector_smoke.py
"""
import csv
import glob
import os
import sys

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0/step3_lane_detector")

from adapters import waymo_adapter as wa  # noqa: E402


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for path in sorted(glob.glob(os.path.join(B1, "canonical", "*.json"))):
        c = wa.load_canonical(path)
        ego = wa.ego_state(c)
        el = wa.find_ego_lane(ego, c["lanes"])
        if el is None:
            rows.append({"scenario_id": c["scenario_id"], "ego_lane": None,
                         "left_lane": None, "note": "no ego lane"})
            continue
        ll = wa.find_left_lane(ego, el, c["lanes"])
        rows.append({
            "scenario_id": c["scenario_id"],
            "ego_lane_id": el["lane"]["id"], "ego_lat": round(el["lat"], 3),
            "ego_head_diff_deg": round(abs(wa.wrap(el["heading"] - ego["heading"])) * 57.2958, 2),
            "ego_lane_has_conn": bool(el["lane"]["entry_lanes"] or el["lane"]["exit_lanes"]),
            "left_lane_id": ll["lane"]["id"] if ll else None,
            "left_lane_lat": round(ll["lat"], 3) if ll else None,
            "lane_width": round(ll["lane_width"], 3) if ll else None,
            "left_head_diff_deg": round(abs(wa.wrap(ll["heading"] - ego["heading"])) * 57.2958, 2) if ll else None,
            "left_lane_has_conn": bool(ll["lane"]["entry_lanes"] or ll["lane"]["exit_lanes"]) if ll else None,
            "ok": bool(ll is not None and 2.0 <= ll["lat"] <= 6.0),
        })
        print(c["scenario_id"], "ego_lat", round(el["lat"], 2),
              "left_lat", round(ll["lat"], 2) if ll else None,
              "W", round(ll["lane_width"], 2) if ll else None)
    with open(os.path.join(OUT, "lane_detector_smoke.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n_ok = sum(1 for r in rows if r.get("ok"))
    print("left-lane detected: %d/%d" % (n_ok, len(rows)))


if __name__ == "__main__":
    main()
