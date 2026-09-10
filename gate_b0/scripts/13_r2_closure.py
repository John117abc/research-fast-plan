#!/usr/bin/env python3
"""Gate B0-R2 step 3: one-step closure on R1 + frozen Gate stats.

usage: python gate_b0/scripts/13_r2_closure.py
writes gate_b0/results/r2/{r2_closure_action_level.csv, r2_closure_pair_summary.csv,
r2_gate_stats.json}
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
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/r2")
CFG = common.cfg()
G = CFG["gates"]["discovery"]
SEED = CFG["stats"]["seed"]
NBOOT = CFG["stats"]["bootstrap"]


def vec(d):
    return np.array([float(d[c]) for c in COLS])


def main():
    succ = json.load(open(os.path.join(OUT, "r1_successors.json")))
    allp = list(csv.DictReader(open(os.path.join(OUT, "r2_all_pairs.csv"))))
    action_rows, pair_rows = [], []
    for p in allp:
        i, j = p["state_i"], p["state_j"]
        d0 = float(p["d0_mean"])
        d1s, used = [], []
        for a in ACTION_IDS:
            si, sj = succ[i][a], succ[j][a]
            if not si["valid"] or not sj["valid"]:
                continue
            d = float(np.mean(np.abs(vec(si["r1"]) - vec(sj["r1"]))))
            d1s.append(d)
            used.append(a)
            action_rows.append({"pair_id": "%s__%s" % (i, j), "state_i": i, "state_j": j,
                                "coarse_i": p["coarse_i"], "coarse_j": p["coarse_j"],
                                "fine_i": p["fine_i"], "fine_j": p["fine_j"],
                                "d0_mean": d0, "probe_action": a,
                                "successor_valid_i": 1, "successor_valid_j": 1,
                                "d1_action_mean": round(d, 6), "d1_action_max": round(d, 6)})
        if not d1s:
            continue
        d1m = float(np.mean(d1s))
        pair_rows.append({
            "pair_id": "%s__%s" % (i, j), "state_i": i, "state_j": j,
            "coarse_i": p["coarse_i"], "coarse_j": p["coarse_j"],
            "same_coarse": p["same_coarse"], "d0_mean": d0,
            "d1_mean": round(d1m, 6), "d1_max": round(float(max(d1s)), 6),
            "closure_drift": round(d1m - d0, 6), "n_common_actions": len(used),
            "pair_type": "same" if p["same_coarse"] == "1" else "cross",
        })
    _write(os.path.join(OUT, "r2_closure_action_level.csv"), action_rows)
    _write(os.path.join(OUT, "r2_closure_pair_summary.csv"), pair_rows)

    d1 = {r["pair_id"]: float(r["d1_mean"]) for r in pair_rows}
    d1max = {r["pair_id"]: float(r["d1_max"]) for r in pair_rows}
    cross = [r for r in pair_rows if r["pair_type"] == "cross"]
    same = [r for r in pair_rows if r["pair_type"] == "same"]
    peq = list(csv.DictReader(open(os.path.join(OUT, "r2_candidate_equivalent_pairs.csv"))))
    matched = list(csv.DictReader(open(os.path.join(OUT, "r2_same_mechanism_matched_pairs.csv"))))
    peq_ids = [p["pair_id"] for p in peq if p["pair_id"] in d1]
    peq_d1 = [d1[k] for k in peq_ids]
    cross_d1 = [float(r["d1_mean"]) for r in cross]
    med = lambda x: float(np.median(x)) if len(x) else float("nan")
    med_peq, med_cross = med(peq_d1), med(cross_d1)
    rng = np.random.default_rng(SEED)
    boot = [med(list(rng.choice(cross_d1, size=max(1, len(peq_d1)), replace=True)))
            for _ in range(NBOOT)] if cross_d1 and peq_d1 else []
    pval = float(np.mean([b <= med_peq for b in boot])) if boot else 1.0
    med_peq_max = med([d1max[k] for k in peq_ids])
    med_cross_max = med([float(r["d1_max"]) for r in cross])

    matched_ids = ["%s__%s" % (m["state_i"], m["state_j"]) for m in matched]
    matched_ids = [k for k in matched_ids if k in d1]
    med_matched = med([d1[k] for k in matched_ids])
    rho = med_peq / (med_matched + 1e-9) if matched_ids else float("nan")

    same_sorted = sorted(same, key=lambda r: -float(r["d0_mean"]))
    n25 = max(1, int(round(0.25 * len(same_sorted))))
    psd = same_sorted[:n25]
    med_psd = med([float(r["d1_mean"]) for r in psd])

    g1 = json.load(open(os.path.join(OUT, "r2_pair_summary.json")))
    gates = {
        "G1_candidate_equivalence": bool(g1["g1_ok"]),
        "G2_one_step_closure": bool(peq_d1 and med_peq <= G["g2_ratio"] * med_cross
                                    and pval < G["g2_p"] and med_peq_max < med_cross_max),
        "G3_no_extra_mech_loss": bool(matched_ids and rho <= G["g3_rho"]),
        "G4_keeps_separation": bool(peq_d1 and med_psd >= G["g4_ratio"] * med_peq),
    }
    stats = {
        "n_peq": len(peq_ids), "n_matched": len(matched_ids),
        "median_D1mean_peq": med_peq, "median_D1mean_random_cross": med_cross,
        "g2_ratio_obs": (med_peq / med_cross) if med_cross else None,
        "median_D1max_peq": med_peq_max, "median_D1max_random_cross": med_cross_max,
        "g2_pvalue": pval, "median_D1mean_matched": med_matched, "g3_rho": rho,
        "median_D1mean_same_diff_top25": med_psd,
        "g4_ratio_obs": (med_psd / med_peq) if med_peq else None,
        "gates": gates, "overall_pass": bool(all(gates.values())),
    }
    json.dump(stats, open(os.path.join(OUT, "r2_gate_stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))


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
