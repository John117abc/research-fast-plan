#!/usr/bin/env python3
"""Gate B0-R3 step 3: quantile trends, per-mechanism Spearman, cluster bootstrap.

usage: python gate_b0/scripts/19_r3_stats.py
writes results/r3/{quantile_statistics.csv, mechanism_pair_statistics.csv,
bootstrap_statistics.json}
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

OUT = os.path.join(B0, "results/r3")
SEED = 100
NBOOT = 10000
CUTS = [0, 10, 25, 50, 75, 100]


def rankdata(a):
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return ranks


def spearman(x, y):
    if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def main():
    rows = list(csv.DictReader(open(os.path.join(OUT, "pair_level_closure.csv"))))
    cross = [r for r in rows if r["pair_type"] == "cross"]
    matched = [r for r in rows if r["pair_type"] == "same_matched"]
    ids = sorted({r["state_i"] for r in rows} | {r["state_j"] for r in rows})
    sidx = {s: k for k, s in enumerate(ids)}
    c_d0 = np.array([float(r["d0_mean"]) for r in cross])
    c_d1 = np.array([float(r["d1_mean"]) for r in cross])
    c_fa = np.array([float(r["feasibility_agree"]) for r in cross])
    c_i = np.array([sidx[r["state_i"]] for r in cross])
    c_j = np.array([sidx[r["state_j"]] for r in cross])
    m_d0 = np.array([float(r["d0_mean"]) for r in matched])
    m_d1 = np.array([float(r["d1_mean"]) for r in matched])
    m_i = np.array([sidx[r["state_i"]] for r in matched])
    m_j = np.array([sidx[r["state_j"]] for r in matched])

    rho_all = spearman(c_d0, c_d1)
    qcuts = np.percentile(c_d0, CUTS)
    qmask = {}
    q_rows = []
    for q in range(5):
        lo, hi = qcuts[q], qcuts[q + 1]
        m = (c_d0 >= lo) & (c_d0 <= hi if q == 4 else c_d0 < hi)
        qmask["Q%d" % (q + 1)] = m
        d = c_d1[m]
        q_rows.append({"quantile": "Q%d" % (q + 1), "d0_lo": round(float(lo), 5),
                       "d0_hi": round(float(hi), 5), "n": int(m.sum()),
                       "D1_median": round(float(np.median(d)), 5),
                       "D1_q25": round(float(np.percentile(d, 25)), 5),
                       "D1_q75": round(float(np.percentile(d, 75)), 5),
                       "D1_mean": round(float(np.mean(d)), 5),
                       "feas_agree_mean": round(float(np.mean(c_fa[m])), 4)})
    _write(os.path.join(OUT, "quantile_statistics.csv"), q_rows)

    mech_rows = []
    for combo in [("cross", "lead"), ("block_or_occupancy", "cross"),
                  ("block_or_occupancy", "lead")]:
        key = set(combo)
        m = np.array([set([r["coarse_i"], r["coarse_j"]]) == key for r in cross])
        rho = spearman(c_d0[m], c_d1[m])
        q1 = c_d1[m & qmask["Q1"]]
        q5 = c_d1[m & qmask["Q5"]]
        mech_rows.append({"mechanism_pair": "|".join(sorted(combo)), "n": int(m.sum()),
                          "spearman": round(rho, 4) if rho == rho else None,
                          "D1_median_Q1": round(float(np.median(q1)), 5) if len(q1) else None,
                          "D1_median_Q5": round(float(np.median(q5)), 5) if len(q5) else None})
    _write(os.path.join(OUT, "mechanism_pair_statistics.csv"), mech_rows)

    # cluster bootstrap by state_id
    rng = np.random.default_rng(SEED)
    n = len(ids)
    boot = {"rho": [], "q1q5": [], "cross_same": [], "fa_q1q5": []}
    for _ in range(NBOOT):
        present = np.zeros(n, bool)
        present[rng.integers(0, n, n)] = True
        cm = present[c_i] & present[c_j]
        if cm.sum() >= 3:
            boot["rho"].append(spearman(c_d0[cm], c_d1[cm]))
            mm = cm & qmask["Q1"]
            q1 = c_d1[mm]
            m5 = cm & qmask["Q5"]
            q5 = c_d1[m5]
            if len(q1) and len(q5):
                boot["q1q5"].append(float(np.median(q1) - np.median(q5)))
                boot["fa_q1q5"].append(float(np.mean(c_fa[mm]) - np.mean(c_fa[m5])))
        mm = present[m_i] & present[m_j]
        if cm.sum() and mm.sum():
            boot["cross_same"].append(float(np.median(c_d1[cm]) - np.median(m_d1[mm])))

    def ci(v):
        v = [x for x in v if x == x]
        if not v:
            return None
        return {"median": round(float(np.median(v)), 5),
                "lo95": round(float(np.percentile(v, 2.5)), 5),
                "hi95": round(float(np.percentile(v, 97.5)), 5), "n": len(v)}

    med_q1 = float(np.median(c_d1[qmask["Q1"]]))
    med_q5 = float(np.median(c_d1[qmask["Q5"]]))
    med_cross = float(np.median(c_d1))
    med_same = float(np.median(m_d1))
    fa_q1 = float(np.mean(c_fa[qmask["Q1"]]))
    fa_q5 = float(np.mean(c_fa[qmask["Q5"]]))
    rho_ci = ci(boot["rho"])
    ratio_matched = med_cross / (med_same + 1e-12)
    conds = {
        "C1_continuous_rho>=0.60_and_CIlow>0.40":
            bool(rho_all >= 0.60 and rho_ci and rho_ci["lo95"] > 0.40),
        "C2_Q1<=0.5*Q5": bool(med_q1 <= 0.5 * med_q5),
        "C3_two_of_three_mech_rho>0.50":
            bool(sum(1 for r in mech_rows if r["spearman"] is not None and r["spearman"] > 0.50) >= 2),
        "C4_matched_ratio<=1.25": bool(ratio_matched <= 1.25),
        "C5_feas_Q1>Q5": bool(fa_q1 > fa_q5),
    }
    out = {
        "n_cross_pairs": len(cross), "n_matched": len(matched),
        "spearman_overall": round(rho_all, 4), "spearman_CI": rho_ci,
        "median_D1_Q1": round(med_q1, 5), "median_D1_Q5": round(med_q5, 5),
        "q1_minus_q5_CI": ci(boot["q1q5"]),
        "median_D1_cross": round(med_cross, 5), "median_D1_same_matched": round(med_same, 5),
        "cross_minus_same_CI": ci(boot["cross_same"]),
        "matched_ratio": round(ratio_matched, 4),
        "feas_agree_Q1": round(fa_q1, 4), "feas_agree_Q5": round(fa_q5, 4),
        "feas_q1_minus_q5_CI": ci(boot["fa_q1q5"]),
        "conditions": conds,
        "all_conditions_met": bool(all(conds.values())),
        "note": "DEVELOPMENT support only; not a confirmatory PASS.",
    }
    json.dump(out, open(os.path.join(OUT, "bootstrap_statistics.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


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
