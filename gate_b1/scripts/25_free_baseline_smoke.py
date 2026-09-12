#!/usr/bin/env python3
"""B1-0 Step 5: interaction_actor_ids / free baseline smoke (plant2).

For states with an official left neighbor: interaction_actor_ids = actors whose
swept bbox intersects the current or left corridor band (same collision margin
0.5 / ego half-width 1.0). Free baseline removes ONLY these actors.

usage: python gate_b1/scripts/25_free_baseline_smoke.py
"""
import csv
import glob
import json
import os
import sys

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, B1)
OUT = os.path.join(B1, "results/b1_0/step5_free_baseline")
from adapters import waymo_adapter as wa  # noqa: E402


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for path in sorted(glob.glob(os.path.join(B1, "canonical", "*.json"))):
        c = wa.load_canonical(path)
        ego = wa.ego_state(c)
        cur = wa.find_current_lane_official(ego, c["lanes"])
        if cur is None:
            continue
        nb, _ = wa.official_left_neighbor(ego, cur["lane"], cur["i_sdc"], c["lanes"])
        if nb is None:
            continue
        W = nb["lateral"]
        inter = wa.interaction_actor_ids(c, ego, W)
        slots = wa.build_slots(c, ego)
        free_slots = wa.build_slots(c, ego, exclude_ids=list(inter.keys()))
        n_occ = sum(1 for f in slots if f)
        n_free_occ = sum(1 for f in free_slots if f)
        rows.append({"scenario_id": c["scenario_id"], "lane_width": round(W, 3),
                     "n_actors": len(c["actors"]), "n_interaction": len(inter),
                     "interaction_ids": ";".join(str(k) for k in inter),
                     "corridors": ";".join(sorted({cc for v in inter.values() for cc in v["corridor"]})),
                     "min_margin": round(min([v["min_margin"] for v in inter.values()], default=9.9), 3),
                     "n_occupied_frames": n_occ, "n_free_occupied_frames": n_free_occ,
                     "free_removed_only_interaction": bool(n_free_occ <= n_occ)})
        print(c["scenario_id"], "W", round(W, 2), "actors", len(c["actors"]),
              "interaction", len(inter), "free_frames", n_free_occ)
    with open(os.path.join(OUT, "free_baseline_smoke.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summ = {"n_states": len(rows),
            "mean_interaction": round(sum(r["n_interaction"] for r in rows) / max(1, len(rows)), 2),
            "max_interaction": max([r["n_interaction"] for r in rows], default=0),
            "all_removed_only_interaction": all(r["free_removed_only_interaction"] for r in rows)}
    json.dump(summ, open(os.path.join(OUT, "free_baseline_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
