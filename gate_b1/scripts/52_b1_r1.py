#!/usr/bin/env python3
"""B1 Step 7 R1^8s computation (plant2) for selected states.

usage: python gate_b1/scripts/52_b1_r1.py
writes gate_b1/results/b1/{r1_signatures.csv, r1_health.json}
"""
import csv
import json
import os
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
B0 = os.path.join(ROOT, "gate_b0")
sys.path.insert(0, ROOT); sys.path.insert(0, B0); sys.path.insert(0, B1)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402
from adapters import waymo_adapter as wa  # noqa: E402

OUT = os.path.join(B1, "results/b1")
SEL = os.path.join(B1, "selected")
N8 = 16
COLS8 = ["%s_%s_t%d" % (b, u, k) for u in ACTION_IDS for b in ("V0", "VL") for k in range(1, N8 + 1)]


def _ratio(p, pf):
    if p is None or pf is None or p <= 0 or pf <= 0:
        return 0.0
    return min(max(p / pf, 0.0), 1.0)


def compute_r1(v0, W, slots, free):
    cor = StraightCorridor(cr.COR_LEN, W)
    occ = cr.build_occ(slots, 0.0, n_steps=N8)
    occf = cr.build_occ(free, 0.0, n_steps=N8)
    out = {}
    for a in ACTIONS:
        r = cr.run_probe_curves((0.0, v0, 0, 0.0), a["ax"], a["lateral"], occ, cor, n_steps=N8)
        rf = cr.run_probe_curves((0.0, v0, 0, 0.0), a["ax"], a["lateral"], occf, cor, n_steps=N8)
        for k in range(N8):
            out["V0_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["p0"][k], rf["p0"][k]), 4)
            out["VL_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["pL"][k], rf["pL"][k]), 4)
    return out


def main():
    sel = list(csv.DictReader(open(os.path.join(OUT, "selected_states.csv"))))
    rows, bad = [], 0
    for r in sel:
        c = wa.normalize_compact(json.load(open(os.path.join(SEL, r["file"]))))
        ego = wa.ego_state(c, 0)
        cur = wa.find_current_lane_official(ego, c["lanes"])
        nb, _ = wa.official_left_neighbor(ego, cur["lane"], cur["i_sdc"], c["lanes"])
        W = nb["lateral"]
        inter = wa.interaction_actor_ids(c, ego, W, native_step=1)
        slots = wa.build_slots(c, ego, native_step=1)
        free = wa.build_slots(c, ego, exclude_ids=list(inter.keys()), native_step=1)
        sig = compute_r1(ego["speed"], W, slots, free)
        arr = np.array([sig[k] for k in COLS8])
        if not np.isfinite(arr).all():
            bad += 1
            continue
        rows.append({"state_id": r["scenario_id"], "file": r["file"],
                     "primary_mechanism": r["primary_mechanism"],
                     "auxiliary": r["auxiliary"], "lane_width": r["lane_width"],
                     "ego_speed": r["ego_speed"], "n_interaction": len(inter), **sig})
        print("done", r["scenario_id"])
    with open(os.path.join(OUT, "r1_signatures.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"n_states": len(rows), "n_bad": bad,
               "V_min": round(float(min(float(r[k]) for r in rows for k in COLS8)), 4),
               "V_max": round(float(max(float(r[k]) for r in rows for k in COLS8)), 4)},
              open(os.path.join(OUT, "r1_health.json"), "w"), indent=1)
    print("wrote r1_signatures.csv", len(rows))


if __name__ == "__main__":
    main()
