#!/usr/bin/env python3
"""Gate B0-R2 step 2: R1 pair construction (no manual selection).

usage: python gate_b0/scripts/12_r2_pairs.py
writes gate_b0/results/r2/{r2_all_pairs.csv, r2_candidate_equivalent_pairs.csv,
r2_same_mechanism_matched_pairs.csv, r2_pair_summary.json}
"""
import csv
import json
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

OUT = os.path.join(B0, "results/r2")
CFG = common.cfg()
G = CFG["gates"]["discovery"]  # same frozen thresholds


def main():
    os.makedirs(OUT, exist_ok=True)
    states = {s["state_id"]: s for s in common.list_states()}
    rows = list(csv.DictReader(open(os.path.join(B0, "results/discovery/r1_signatures.csv"))))
    ids = [r["state_id"] for r in rows]
    X = np.array([[float(r[c]) for c in COLS] for r in rows])
    meta = {r["state_id"]: {"coarse": r["coarse_mechanism"], "fine": r["fine_mechanism"],
                            "group": r["param_group_id"], "speed": states[r["state_id"]]["ego_speed"]}
            for r in rows}

    pairs = []
    n = len(ids)
    for a in range(n):
        for b in range(a + 1, n):
            i, j = ids[a], ids[b]
            dm = float(np.mean(np.abs(X[a] - X[b])))
            pairs.append({
                "state_i": i, "state_j": j,
                "coarse_i": meta[i]["coarse"], "coarse_j": meta[j]["coarse"],
                "fine_i": meta[i]["fine"], "fine_j": meta[j]["fine"],
                "group_i": meta[i]["group"], "group_j": meta[j]["group"],
                "same_coarse": int(meta[i]["coarse"] == meta[j]["coarse"]),
                "same_fine": int(meta[i]["fine"] == meta[j]["fine"]),
                "same_param_group": int(meta[i]["group"] == meta[j]["group"]),
                "ego_speed_diff": round(abs(meta[i]["speed"] - meta[j]["speed"]), 4),
                "d0_mean": round(dm, 6),
            })
    cross = [p for p in pairs if p["coarse_i"] != p["coarse_j"]]
    thr = float(np.percentile([p["d0_mean"] for p in cross], G["bottom_frac"] * 100))

    by_i = {}
    for p in cross:
        by_i.setdefault(p["state_i"], []).append((p["d0_mean"], p["state_j"]))
        by_i.setdefault(p["state_j"], []).append((p["d0_mean"], p["state_i"]))
    nn = {k: min(v)[1] for k, v in by_i.items()}

    peq = []
    for p in cross:
        i, j = p["state_i"], p["state_j"]
        if nn.get(i) == j and nn.get(j) == i \
                and p["same_param_group"] == 0 and p["d0_mean"] <= thr:
            q = dict(p)
            q["pair_id"] = "%s__%s" % (i, j)
            q["pair_type"] = "cross_candidate"
            peq.append(q)

    same = [p for p in pairs if p["same_coarse"] == 1 and p["same_param_group"] == 0]
    matched = []
    for q in peq:
        cand = sorted(same, key=lambda p: (abs(p["d0_mean"] - q["d0_mean"]),
                                           p["ego_speed_diff"]))
        if cand:
            m = dict(cand[0])
            m["pair_id"] = "match__%s" % q["pair_id"]
            m["matched_to"] = q["pair_id"]
            m["pair_type"] = "same_matched"
            matched.append(m)

    fine_pairs = len(set(tuple(sorted([p["fine_i"], p["fine_j"]])) for p in peq))
    coarse_combos = len(set(tuple(sorted([p["coarse_i"], p["coarse_j"]])) for p in peq))
    d0s = [p["d0_mean"] for p in peq]
    summary = {
        "n_states": len(ids), "n_pairs": len(pairs), "n_cross_pairs": len(cross),
        "bottom_frac": G["bottom_frac"], "d0_threshold": thr,
        "n_peq": len(peq), "n_matched": len(matched),
        "n_fine_mechanism_pairs": fine_pairs, "n_coarse_combos": coarse_combos,
        "peq_d0_min": min(d0s) if d0s else None,
        "peq_d0_median": float(np.median(d0s)) if d0s else None,
        "peq_d0_max": max(d0s) if d0s else None,
        "g1_ok": (len(peq) >= G["peq_min"] and fine_pairs >= G["fine_pair_min"]
                  and coarse_combos >= G["coarse_combo_min"]),
    }
    _write(os.path.join(OUT, "r2_all_pairs.csv"), pairs)
    _write(os.path.join(OUT, "r2_candidate_equivalent_pairs.csv"), peq)
    _write(os.path.join(OUT, "r2_same_mechanism_matched_pairs.csv"), matched)
    json.dump(summary, open(os.path.join(OUT, "r2_pair_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


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
