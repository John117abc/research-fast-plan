#!/usr/bin/env python3
"""B0-C1 step 3: quantiles, per-mechanism Spearman, cluster bootstrap (C1-C4),
plus the two pre-registered audits (non-overlap, action effect).

usage: python gate_b0/scripts/25_c1_stats.py
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

OUT = os.path.join(B0, "results/confirmatory")
SEED = 100
NBOOT = 10000
CUTS = [0, 10, 25, 50, 75, 100]
SEG = {"early": list(range(1, 7)), "mid": list(range(7, 14)), "late": list(range(14, 21))}


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
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def load_vecs(path):
    rows = list(csv.DictReader(open(path)))
    return {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in rows}


def load_succ():
    rows = list(csv.DictReader(open(os.path.join(OUT, "successor_r1_signatures.csv"))))
    out = {}
    for r in rows:
        if int(r["successor_valid"]) == 1:
            out.setdefault(r["state_id"], {})[r["probe_action"]] = (
                np.array([float(r[c]) for c in COLS]))
    return out


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
        mech_rows.append({"mechanism_pair": "|".join(sorted(combo)), "n": int(m.sum()),
                          "spearman": round(rho, 4) if rho == rho else None,
                          "D1_median_Q1": round(float(np.median(c_d1[m & qmask["Q1"]])), 5) if (m & qmask["Q1"]).sum() else None,
                          "D1_median_Q5": round(float(np.median(c_d1[m & qmask["Q5"]])), 5) if (m & qmask["Q5"]).sum() else None})
    _write(os.path.join(OUT, "mechanism_pair_statistics.csv"), mech_rows)

    rng = np.random.default_rng(SEED)
    n = len(ids)
    boot = {"rho": [], "q1q5": [], "cross_same": []}
    for _ in range(NBOOT):
        present = np.zeros(n, bool)
        present[rng.integers(0, n, n)] = True
        cm = present[c_i] & present[c_j]
        if cm.sum() >= 3:
            boot["rho"].append(spearman(c_d0[cm], c_d1[cm]))
            q1 = c_d1[cm & qmask["Q1"]]
            q5 = c_d1[cm & qmask["Q5"]]
            if len(q1) and len(q5):
                boot["q1q5"].append(float(np.median(q1) - np.median(q5)))
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
    ratio = med_cross / (med_same + 1e-12)
    rho_ci = ci(boot["rho"])
    conds = {
        "C1_continuous_rho>=0.60_and_CIlow>0.40":
            bool(rho_all >= 0.60 and rho_ci and rho_ci["lo95"] > 0.40),
        "C2_Q1<=0.5*Q5": bool(med_q1 <= 0.5 * med_q5),
        "C3_two_of_three_mech_rho>0.50":
            bool(sum(1 for r in mech_rows if r["spearman"] is not None and r["spearman"] > 0.50) >= 2),
        "C4_matched_ratio<=1.25": bool(ratio <= 1.25),
    }

    # Audit A: non-overlap d0(0.5-3) vs d1(8-11)
    X0 = load_vecs(os.path.join(OUT, "r1_signatures.csv"))
    X1 = load_succ()
    def segd(v1, v2, ks):
        idx = [COLS.index("%s_%s_t%d" % (b, u, k)) for u in ACTION_IDS for b in ("V0", "VL") for k in ks]
        return float(np.mean(np.abs(v1[idx] - v2[idx])))
    d0e, d1l = [], []
    for r in cross:
        i, j = r["state_i"], r["state_j"]
        d0e.append(segd(X0[i], X0[j], SEG["early"]))
        ds = [segd(X1[i][u], X1[j][u], SEG["late"]) for u in ACTION_IDS if u in X1[i] and u in X1[j]]
        d1l.append(float(np.mean(ds)) if ds else np.nan)
    d0e, d1l = np.array(d0e), np.array(d1l)
    ok = ~np.isnan(d1l)
    rho_nonoverlap = spearman(d0e[ok], d1l[ok])
    _write(os.path.join(OUT, "nonoverlap_audit.csv"),
           [{"diagnostic": "d0(0.5-3s) vs d1(8-11s)", "spearman": round(rho_nonoverlap, 4),
             "n": int(ok.sum())}])

    # Audit B: action effect
    eff_rows = []
    for sid, acts in X1.items():
        keys = [u for u in ACTION_IDS if u in acts]
        ds = [float(np.mean(np.abs(acts[keys[a]] - acts[keys[b]])))
              for a in range(len(keys)) for b in range(a + 1, len(keys))]
        eff_rows.append({"state_id": sid, "mean_pairwise_dist": round(float(np.mean(ds)), 5),
                         "min_pairwise_dist": round(float(np.min(ds)), 5),
                         "max_pairwise_dist": round(float(np.max(ds)), 5)})
    _write(os.path.join(OUT, "action_effect_audit.csv"), eff_rows)
    eff = np.array([r["mean_pairwise_dist"] for r in eff_rows])

    out = {
        "n_cross_pairs": len(cross), "n_matched": len(matched),
        "spearman_overall": round(rho_all, 4), "spearman_CI": rho_ci,
        "median_D1_Q1": round(med_q1, 5), "median_D1_Q5": round(med_q5, 5),
        "q1_minus_q5_CI": ci(boot["q1q5"]),
        "median_D1_cross": round(med_cross, 5), "median_D1_same_matched": round(med_same, 5),
        "cross_minus_same_CI": ci(boot["cross_same"]), "matched_ratio": round(ratio, 4),
        "feasibility_agree_mean": round(float(np.mean(c_fa)), 4),
        "nonoverlap_spearman": round(rho_nonoverlap, 4),
        "action_effect_mean": round(float(np.mean(eff)), 5),
        "action_effect_min": round(float(np.min(eff)), 5),
        "conditions": conds, "overall_pass": bool(all(conds.values())),
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
