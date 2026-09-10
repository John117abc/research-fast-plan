#!/usr/bin/env python3
"""Gate B0-4: automatic pair construction (no manual pair selection).

usage: python gate_b0/scripts/04_build_pairs.py
writes under results/discovery:
  all_pairs.csv, candidate_equivalent_pairs.csv,
  same_mechanism_matched_pairs.csv, pair_build_summary.json
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
from consequence import relation_distance as rd  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/discovery")
CFG = common.cfg()
G = CFG["gates"]["discovery"]


def load_signatures():
    states = {s["state_id"]: s for s in common.list_states()}
    sigs, meta = {}, {}
    for r in csv.DictReader(open(os.path.join(OUT, "signatures.csv"))):
        sid = r["state_id"]
        sigs[sid] = {"M": [int(r["M_%s" % a]) for a in ACTION_IDS],
                     "V": [float(r["V_%s" % a]) for a in ACTION_IDS]}
        meta[sid] = {"coarse": r["coarse_mechanism"], "fine": r["fine_mechanism"],
                     "group": r["param_group_id"], "speed": states[sid]["ego_speed"]}
    return sigs, meta


def main():
    sigs, meta = load_signatures()
    ids = sorted(sigs)
    pairs = []
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            dm = rd.d_mean(sigs[i], sigs[j])
            dx = rd.d_max(sigs[i], sigs[j])
            pairs.append({
                "state_i": i, "state_j": j,
                "coarse_i": meta[i]["coarse"], "coarse_j": meta[j]["coarse"],
                "fine_i": meta[i]["fine"], "fine_j": meta[j]["fine"],
                "group_i": meta[i]["group"], "group_j": meta[j]["group"],
                "same_coarse": int(meta[i]["coarse"] == meta[j]["coarse"]),
                "same_fine": int(meta[i]["fine"] == meta[j]["fine"]),
                "same_param_group": int(meta[i]["group"] == meta[j]["group"]),
                "ego_speed_diff": round(abs(meta[i]["speed"] - meta[j]["speed"]), 4),
                "d0_mean": round(dm, 6), "d0_max": round(dx, 6),
            })
    cross = [p for p in pairs if p["coarse_i"] != p["coarse_j"]]
    thr = float(np.percentile([p["d0_mean"] for p in cross], G["bottom_frac"] * 100))

    # mutual nearest neighbours in cross-mechanism space
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

    # same-mechanism, initial-distance matched controls
    same = [p for p in pairs if p["same_coarse"] == 1]
    matched = []
    for q in peq:
        best = None
        for p in same:
            if abs(p["d0_mean"] - q["d0_mean"]) > G["d0_match_tol"]:
                continue
            if p["ego_speed_diff"] > G["speed_match_tol"]:
                continue
            if best is None or abs(p["d0_mean"] - q["d0_mean"]) < abs(best["d0_mean"] - q["d0_mean"]):
                best = p
        if best is not None:
            m = dict(best)
            m["pair_id"] = "match__%s" % q["pair_id"]
            m["matched_to"] = q["pair_id"]
            m["pair_type"] = "same_matched"
            matched.append(m)

    fine_pairs = len(set(tuple(sorted([p["fine_i"], p["fine_j"]])) for p in peq))
    coarse_combos = len(set(tuple(sorted([p["coarse_i"], p["coarse_j"]])) for p in peq))
    summary = {
        "n_states": len(ids), "n_pairs": len(pairs), "n_cross_pairs": len(cross),
        "bottom_frac": G["bottom_frac"], "d0_threshold": thr,
        "n_peq": len(peq), "n_matched": len(matched),
        "n_fine_mechanism_pairs": fine_pairs, "n_coarse_combos": coarse_combos,
        "g1_ok": (len(peq) >= G["peq_min"] and fine_pairs >= G["fine_pair_min"]
                  and coarse_combos >= G["coarse_combo_min"]),
    }
    _write(os.path.join(OUT, "all_pairs.csv"), pairs)
    _write(os.path.join(OUT, "candidate_equivalent_pairs.csv"), peq)
    _write(os.path.join(OUT, "same_mechanism_matched_pairs.csv"), matched)
    json.dump(summary, open(os.path.join(OUT, "pair_build_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


def _write(path, rows):
    if not rows:
        open(path, "w").write("")
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
