#!/usr/bin/env python3
"""B1-0 Step 3 (official left_neighbors version): left-lane recovery smoke.

Uses the official WOMD lane topology (lane.left_neighbors + self/neighbor index
ranges). No shifted/fabricated lane. A neighbor is eligible only if in-range,
truly on the left, same direction, and has future coverage; otherwise the state
is excluded with reason no_valid_left_neighbor.

usage: python gate_b1/scripts/20_lane_detector_smoke.py
"""
import csv
import glob
import json
import os
import sys

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0/step3_lane_detector")
from adapters import waymo_adapter as wa  # noqa: E402


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, cand_audit = [], {}
    n_ok = n_excl = n_err = 0
    for path in sorted(glob.glob(os.path.join(B1, "canonical", "*.json"))):
        c = wa.load_canonical(path)
        ego = wa.ego_state(c)
        cur = wa.find_current_lane_official(ego, c["lanes"])
        if cur is None:
            rows.append({"scenario_id": c["scenario_id"], "exclude_reason": "no_current_lane",
                         "ok": False})
            n_excl += 1
            continue
        nb, cands = wa.official_left_neighbor(ego, cur["lane"], cur["i_sdc"], c["lanes"])
        cand_audit[c["scenario_id"]] = {
            "current_lane_id": cur["lane"]["id"], "i_sdc": cur["i_sdc"],
            "candidates": [{k: v for k, v in cd.items() if k != "segment"} for cd in cands]}
        if nb is None:
            reasons = [cd.get("reason", "ineligible") for cd in cands]
            rows.append({"scenario_id": c["scenario_id"], "exclude_reason": "no_valid_left_neighbor",
                         "current_lane_id": cur["lane"]["id"], "i_sdc": cur["i_sdc"],
                         "n_candidates": len(cands), "candidate_reasons": ";".join(reasons),
                         "ok": False})
            n_excl += 1
            continue
        left_ok = bool(nb["on_left"] and nb["lateral"] > 0)
        dir_ok = bool(nb["same_direction"])
        if not (left_ok and dir_ok):
            n_err += 1
        rows.append({"scenario_id": c["scenario_id"], "exclude_reason": "",
                     "current_lane_id": cur["lane"]["id"], "i_sdc": cur["i_sdc"],
                     "n_candidates": len(cands),
                     "left_lane_id": nb["feature_id"],
                     "left_lateral": round(nb["lateral"], 3),
                     "left_heading_diff_deg": round(nb["heading_diff_deg"], 2),
                     "coverage_ahead": round(nb["coverage_ahead"], 1),
                     "self_range": str(nb["self_range"]),
                     "neighbor_range": str(nb["neighbor_range"]),
                     "on_left": left_ok, "same_direction": dir_ok,
                     "ok": bool(left_ok and dir_ok)})
        n_ok += 1
        print(c["scenario_id"], "cur", cur["lane"]["id"], "-> left", nb["feature_id"],
              "lat", round(nb["lateral"], 2), "dh", round(nb["heading_diff_deg"], 1),
              "cov", round(nb["coverage_ahead"], 1))
    fields = ["scenario_id", "exclude_reason", "current_lane_id", "i_sdc", "n_candidates",
              "candidate_reasons", "left_lane_id", "left_lateral",
              "left_heading_diff_deg", "coverage_ahead", "self_range",
              "neighbor_range", "on_left", "same_direction", "ok"]
    with open(os.path.join(OUT, "left_neighbor_smoke.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    json.dump(cand_audit, open(os.path.join(OUT, "left_neighbor_candidates.json"), "w"))
    summ = {"n_states": len(rows), "n_with_left_neighbor": n_ok, "n_excluded": n_excl,
            "coverage": round(n_ok / max(1, len(rows)), 4),
            "n_left_or_direction_errors": n_err,
            "PASS": bool(n_err == 0 and n_ok > 0)}
    json.dump(summ, open(os.path.join(OUT, "left_neighbor_smoke_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
