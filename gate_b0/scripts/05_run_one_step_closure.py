#!/usr/bin/env python3
"""Gate B0-5: one-step behavioral closure using precomputed successor signatures.

usage: python gate_b0/scripts/05_run_one_step_closure.py
writes:
  results/discovery/closure_action_level.csv
  results/discovery/closure_pair_summary.csv
"""
import csv
import json
import os
import sys

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from consequence import relation_distance as rd  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/discovery")


def main():
    succ = json.load(open(os.path.join(OUT, "successors.json")))
    pairs = list(csv.DictReader(open(os.path.join(OUT, "all_pairs.csv"))))
    action_rows, summary_rows = [], []
    for p in pairs:
        i, j = p["state_i"], p["state_j"]
        common_actions, d1s = [], []
        for a in ACTION_IDS:
            si = succ[i][a]
            sj = succ[j][a]
            if not si["successor_valid"] or not sj["successor_valid"]:
                continue
            d = rd.d_mean({"M": si["M"], "V": si["V"]},
                          {"M": sj["M"], "V": sj["V"]})
            common_actions.append(a)
            d1s.append(d)
            action_rows.append({"pair_id": "%s__%s" % (i, j), "state_i": i, "state_j": j,
                                "coarse_i": p["coarse_i"], "coarse_j": p["coarse_j"],
                                "fine_i": p["fine_i"], "fine_j": p["fine_j"],
                                "d0_mean": p["d0_mean"], "d0_max": p["d0_max"],
                                "probe_action": a, "successor_valid_i": 1,
                                "successor_valid_j": 1,
                                "d1_action_mean": round(d, 6), "d1_action_max": round(d, 6)})
        if not d1s:
            continue
        d1_mean = sum(d1s) / len(d1s)
        summary_rows.append({
            "pair_id": "%s__%s" % (i, j), "state_i": i, "state_j": j,
            "coarse_i": p["coarse_i"], "coarse_j": p["coarse_j"],
            "same_coarse": p["same_coarse"],
            "d0_mean": float(p["d0_mean"]), "d0_max": float(p["d0_max"]),
            "d1_mean": round(d1_mean, 6), "d1_max": round(max(d1s), 6),
            "closure_drift": round(d1_mean - float(p["d0_mean"]), 6),
            "n_common_actions": len(common_actions),
            "pair_type": "same" if p["same_coarse"] == "1" else "cross",
        })
    _write(os.path.join(OUT, "closure_action_level.csv"), action_rows)
    _write(os.path.join(OUT, "closure_pair_summary.csv"), summary_rows)
    print("pairs with closure:", len(summary_rows), "action rows:", len(action_rows))


def _write(path, rows):
    if not rows:
        open(path, "w").write("")
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
