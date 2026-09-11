#!/usr/bin/env python3
"""B0-C1 step 2: cross-mechanism pairs + same-mechanism matched controls +
action/pair-level closure (confirmatory).

usage: python gate_b0/scripts/24_c1_pairs_closure.py
"""
import csv
import os
import sys

import numpy as np

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from consequence.r1_signature import COLS  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/confirmatory")


def main():
    lvl = list(csv.DictReader(open(os.path.join(OUT, "r1_signatures.csv"))))
    X0 = {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in lvl}
    meta = {r["state_id"]: {"coarse": r["coarse_mechanism"], "fine": r["fine_mechanism"],
                            "group": r["param_group_id"]} for r in lvl}
    speed = {r["state_id"]: float(r["ego_speed"]) for r in lvl}
    srows = list(csv.DictReader(open(os.path.join(OUT, "successor_r1_signatures.csv"))))
    X1 = {}
    for r in srows:
        X1.setdefault(r["state_id"], {})[r["probe_action"]] = (
            np.array([float(r[c]) for c in COLS]) if int(r["successor_valid"]) == 1 else None)

    ids = sorted(X0)
    all_pairs = []
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            d0 = float(np.mean(np.abs(X0[i] - X0[j])))
            all_pairs.append({"state_i": i, "state_j": j, "coarse_i": meta[i]["coarse"],
                              "coarse_j": meta[j]["coarse"], "fine_i": meta[i]["fine"],
                              "fine_j": meta[j]["fine"], "group_i": meta[i]["group"],
                              "group_j": meta[j]["group"],
                              "same_param_group": int(meta[i]["group"] == meta[j]["group"]),
                              "ego_speed_diff": round(abs(speed[i] - speed[j]), 4),
                              "d0_mean": round(d0, 6)})
    action_rows, pair_rows = [], []

    def closure(p, ptype):
        i, j = p["state_i"], p["state_j"]
        d1s, valid_only, feas = [], [], []
        for u in ACTION_IDS:
            vi, vj = X1[i][u], X1[j][u]
            if vi is not None and vj is not None:
                d = float(np.mean(np.abs(vi - vj)))
                d1s.append(d); valid_only.append(d); feas.append(1)
                bv, bi, ov = 1, 0, 0
            elif vi is None and vj is None:
                d1s.append(0.0); feas.append(1); bv, bi, ov = 0, 1, 0
            else:
                d1s.append(1.0); feas.append(0); bv, bi, ov = 0, 0, 1
            action_rows.append({"pair_id": "%s__%s" % (i, j), "pair_type": ptype,
                                "state_i": i, "state_j": j, "probe_action": u,
                                "d0_mean": p["d0_mean"], "d1_action": round(d1s[-1], 6),
                                "feasibility_agree": feas[-1], "both_valid": bv,
                                "both_infeasible": bi, "one_valid": ov})
        return {"pair_id": "%s__%s" % (i, j), "pair_type": ptype, "state_i": i, "state_j": j,
                "coarse_i": p["coarse_i"], "coarse_j": p["coarse_j"],
                "fine_i": p["fine_i"], "fine_j": p["fine_j"],
                "same_param_group": p["same_param_group"],
                "ego_speed_diff": p["ego_speed_diff"], "d0_mean": p["d0_mean"],
                "d1_mean": round(float(np.mean(d1s)), 6),
                "d1_validonly": round(float(np.mean(valid_only)), 6) if valid_only else None,
                "feasibility_agree": round(float(np.mean(feas)), 6),
                "n_valid_actions": len(valid_only)}

    cross = [p for p in all_pairs if p["coarse_i"] != p["coarse_j"]]
    same = [p for p in all_pairs if p["coarse_i"] == p["coarse_j"]]
    for p in cross:
        pair_rows.append(closure(p, "cross"))
    same_d0 = np.array([p["d0_mean"] for p in same])
    cross_d0 = np.array([p["d0_mean"] for p in cross])
    same_group = np.array([p["same_param_group"] for p in same])
    D = np.abs(same_d0[None, :] - cross_d0[:, None])
    D[:, same_group == 1] = np.inf
    nearest = np.argmin(D, axis=1)
    for k, p in enumerate(cross):
        m = dict(same[int(nearest[k])]); m["pair_type"] = "same_matched"
        pair_rows.append(closure(m, "same_matched"))

    _write(os.path.join(OUT, "cross_mechanism_pairs.csv"),
           [r for r in pair_rows if r["pair_type"] == "cross"])
    _write(os.path.join(OUT, "same_mechanism_matched_pairs.csv"),
           [r for r in pair_rows if r["pair_type"] == "same_matched"])
    _write(os.path.join(OUT, "action_level_closure.csv"), action_rows)
    _write(os.path.join(OUT, "pair_level_closure.csv"), pair_rows)
    print("cross %d matched %d action rows %d" % (len(cross), len(cross), len(action_rows)))


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
