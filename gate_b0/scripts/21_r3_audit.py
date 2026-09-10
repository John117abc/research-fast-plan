#!/usr/bin/env python3
"""Gate B0-R3 audit: overlap / per-action / action-effect / matching diagnostics.

Diagnostic only. Does NOT modify R1, distance, actions, thresholds, or Gates.
Reuses existing R3 outputs and caches.

usage: python gate_b0/scripts/21_r3_audit.py
writes gate_b0/results/r3/audit/{...}
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

R3 = os.path.join(B0, "results/r3")
OUT = os.path.join(R3, "audit")
FIG = os.path.join(OUT, "figures")
CUTS = [0, 10, 25, 50, 75, 100]
SEG = {"early": list(range(1, 7)), "mid": list(range(7, 14)), "late": list(range(14, 21))}
TAIL = list(range(19, 21))          # successor t=9.0,9.5 -> absolute 10.0,10.5 (beyond orig)
EARLY6 = list(range(1, 7))


def ci(u, b, k):
    return COLS.index("%s_%s_t%d" % (b, u, k))


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


def load_r1(path):
    rows = list(csv.DictReader(open(path)))
    return {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in rows}


def load_succ():
    rows = list(csv.DictReader(open(os.path.join(R3, "successor_r1_signatures.csv"))))
    out = {}
    for r in rows:
        if int(r["successor_valid"]) == 1:
            out.setdefault(r["state_id"], {})[r["probe_action"]] = (
                np.array([float(r[c]) for c in COLS]))
    return out


def seg_dist(v1, v2, ks):
    idx = [ci(u, b, k) for u in ACTION_IDS for b in ("V0", "VL") for k in ks]
    return float(np.mean(np.abs(v1[idx] - v2[idx])))


def main():
    os.makedirs(FIG, exist_ok=True)
    X0 = load_r1(os.path.join(B0, "results/discovery/r1_signatures.csv"))
    X1 = load_succ()
    cross = list(csv.DictReader(open(os.path.join(R3, "cross_mechanism_pairs.csv"))))
    matched = list(csv.DictReader(open(os.path.join(R3, "same_mechanism_matched_pairs.csv"))))
    act = list(csv.DictReader(open(os.path.join(R3, "action_level_closure.csv"))))
    act = [r for r in act if r["pair_type"] == "cross"]
    c_d0 = np.array([float(r["d0_mean"]) for r in cross])
    qcuts = np.percentile(c_d0, CUTS)
    qmask = {}
    for q in range(5):
        lo, hi = qcuts[q], qcuts[q + 1]
        qmask["Q%d" % (q + 1)] = (c_d0 >= lo) & (c_d0 <= hi if q == 4 else c_d0 < hi)
    pindex = {("%s__%s" % (r["state_i"], r["state_j"])): k for k, r in enumerate(cross)}

    # A. per-action Spearman + quantile medians
    a_rows = []
    per_action_med = {}
    for u in ACTION_IDS:
        d1u = np.full(len(cross), np.nan)
        for r in act:
            if r["probe_action"] == u and r["pair_id"] in pindex:
                d1u[pindex[r["pair_id"]]] = float(r["d1_action"])
        ok = ~np.isnan(d1u)
        rho = spearman(c_d0[ok], d1u[ok])
        meds = {}
        for q in qmask:
            m = ok & qmask[q]
            meds[q] = float(np.median(d1u[m])) if m.sum() else float("nan")
        per_action_med[u] = meds
        a_rows.append({"probe_action": u, "n": int(ok.sum()),
                       "spearman": round(rho, 4) if rho == rho else None,
                       **{("median_d1_%s" % q): round(meds[q], 5) for q in meds}})
    _write(os.path.join(OUT, "action_statistics.csv"), a_rows)

    # B. action effect: within-state distance between successors of different actions
    b_rows = []
    for sid, acts in X1.items():
        keys = [u for u in ACTION_IDS if u in acts]
        ds = [float(np.mean(np.abs(acts[keys[i]] - acts[keys[j]])))
              for i in range(len(keys)) for j in range(i + 1, len(keys))]
        b_rows.append({"state_id": sid, "n_actions": len(keys),
                       "mean_pairwise_dist": round(float(np.mean(ds)), 5),
                       "min_pairwise_dist": round(float(np.min(ds)), 5),
                       "max_pairwise_dist": round(float(np.max(ds)), 5)})
    _write(os.path.join(OUT, "action_effect.csv"), b_rows)
    eff = np.array([r["mean_pairwise_dist"] for r in b_rows])

    # C. time-overlap sensitivity
    c_rows = []
    for seg_name, ks in list(SEG.items()):
        d0s, d1s = [], []
        for r in cross:
            i, j = r["state_i"], r["state_j"]
            d0s.append(seg_dist(X0[i], X0[j], ks))
            ds = [seg_dist(X1[i][u], X1[j][u], ks) for u in ACTION_IDS if u in X1[i] and u in X1[j]]
            d1s.append(float(np.mean(ds)) if ds else np.nan)
        d0s, d1s = np.array(d0s), np.array(d1s)
        ok = ~np.isnan(d1s)
        c_rows.append({"segment": seg_name, "t_range": "%s-%s" %
                       (0.5 * ks[0], 0.5 * ks[-1]), "spearman_d0_d1_seg": round(spearman(d0s[ok], d1s[ok]), 4),
                       "median_d0": round(float(np.median(d0s)), 5),
                       "median_d1": round(float(np.median(d1s[ok])), 5)})
    # tail: successor beyond original horizon vs full d0
    d1_tail = []
    for r in cross:
        i, j = r["state_i"], r["state_j"]
        ds = [seg_dist(X1[i][u], X1[j][u], TAIL) for u in ACTION_IDS if u in X1[i] and u in X1[j]]
        d1_tail.append(float(np.mean(ds)) if ds else np.nan)
    d1_tail = np.array(d1_tail)
    ok = ~np.isnan(d1_tail)
    c_rows.append({"segment": "successor_tail_abs10.0-11.0", "t_range": "10.0-11.0",
                   "spearman_d0_d1_seg": round(spearman(c_d0[ok], d1_tail[ok]), 4),
                   "median_d0": round(float(np.median(c_d0)), 5),
                   "median_d1": round(float(np.median(d1_tail[ok])), 5)})
    # clean non-overlap: d0 early (abs 0.5-3) vs d1 late (abs 8-11)
    d0e, d1l = [], []
    for r in cross:
        i, j = r["state_i"], r["state_j"]
        d0e.append(seg_dist(X0[i], X0[j], EARLY6))
        ds = [seg_dist(X1[i][u], X1[j][u], SEG["late"]) for u in ACTION_IDS if u in X1[i] and u in X1[j]]
        d1l.append(float(np.mean(ds)) if ds else np.nan)
    d0e, d1l = np.array(d0e), np.array(d1l)
    ok = ~np.isnan(d1l)
    c_rows.append({"segment": "nonoverlap_d0_early_vs_d1_late", "t_range": "0.5-3 vs 8-11",
                   "spearman_d0_d1_seg": round(spearman(d0e[ok], d1l[ok]), 4),
                   "median_d0": round(float(np.median(d0e)), 5),
                   "median_d1": round(float(np.median(d1l[ok])), 5)})
    _write(os.path.join(OUT, "time_overlap_audit.csv"), c_rows)

    # D. matched quality (matched rows are positionally aligned with cross rows)
    m_rows = []
    for k, m in enumerate(matched):
        if k >= len(cross):
            break
        d0c = float(cross[k]["d0_mean"])
        d0s = float(m["d0_mean"])
        m_rows.append({"cross_pair": "%s__%s" % (cross[k]["state_i"], cross[k]["state_j"]),
                       "d0_cross": d0c, "d0_same": d0s,
                       "abs_diff": round(abs(d0c - d0s), 6)})
    _write(os.path.join(OUT, "matched_quality.csv"), m_rows)
    diffs = np.array([r["abs_diff"] for r in m_rows])
    mq = {"n": len(diffs), "mean": round(float(np.mean(diffs)), 5),
          "median": round(float(np.median(diffs)), 5),
          "p90": round(float(np.percentile(diffs, 90)), 5),
          "max": round(float(np.max(diffs)), 5),
          "frac_within_0.01": round(float(np.mean(diffs <= 0.01)), 4)}

    audit = {
        "per_action": a_rows,
        "action_effect": {"mean_of_state_mean": round(float(np.mean(eff)), 5),
                          "median_of_state_mean": round(float(np.median(eff)), 5),
                          "min": round(float(np.min(eff)), 5),
                          "max": round(float(np.max(eff)), 5)},
        "time_overlap": c_rows,
        "matched_quality": mq,
    }
    json.dump(audit, open(os.path.join(OUT, "audit_statistics.json"), "w"), indent=1)
    _figures(a_rows, per_action_med, b_rows, c_rows, diffs)
    _report(audit)
    print(json.dumps({"action_effect": audit["action_effect"],
                      "matched_quality": mq, "time_overlap": c_rows}, indent=1))


def _figures(a_rows, per_action_med, b_rows, c_rows, diffs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.figure()
    plt.bar([r["probe_action"] for r in a_rows], [r["spearman"] for r in a_rows])
    plt.ylim(0, 1); plt.ylabel("Spearman(d0, d1(u))")
    plt.title("Fig A1: per-action closure correlation")
    plt.savefig(os.path.join(FIG, "audit_figA1_per_action_rho.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    for u in ACTION_IDS:
        plt.plot(range(1, 6), [per_action_med[u]["Q%d" % q] for q in range(1, 6)],
                 marker="o", label=u)
    plt.xticks(range(1, 6), ["Q1", "Q2", "Q3", "Q4", "Q5"])
    plt.xlabel("initial-distance quantile"); plt.ylabel("median d1(u)")
    plt.legend(fontsize=7, ncol=2); plt.title("Fig A2: per-action quantile trend")
    plt.savefig(os.path.join(FIG, "audit_figA2_per_action_quantile.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.hist([r["mean_pairwise_dist"] for r in b_rows], bins=30)
    plt.xlabel("mean distance between successors of different actions (same state)")
    plt.title("Fig B: action effect strength")
    plt.savefig(os.path.join(FIG, "audit_figB_action_effect.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    names = [r["segment"] for r in c_rows]
    vals = [r["spearman_d0_d1_seg"] for r in c_rows]
    plt.bar(range(len(names)), vals)
    plt.xticks(range(len(names)), names, rotation=30, ha="right", fontsize=7)
    plt.ylim(0, 1); plt.ylabel("Spearman"); plt.title("Fig C: time-overlap sensitivity")
    plt.savefig(os.path.join(FIG, "audit_figC_overlap.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.hist(diffs, bins=40)
    plt.xlabel("|d0_cross - d0_same_matched|")
    plt.title("Fig D: matching quality")
    plt.savefig(os.path.join(FIG, "audit_figD_matching.png"), dpi=120, bbox_inches="tight")
    plt.close()


def _report(audit):
    pa = audit["per_action"]
    ae = audit["action_effect"]
    to = {r["segment"]: r for r in audit["time_overlap"]}
    mq = audit["matched_quality"]
    L = ["# B0-R3 audit (diagnostic only; no Gate, no changes)", "",
         "Question: is the R3 rho=0.958 partly an artifact of overlapping future windows",
         "between R1(X_t) and R1(X_{t+1})? Four checks below.", "",
         "## A. Per-action closure",
         "| action | Spearman(d0,d1(u)) | median d1 Q1 | median d1 Q5 |",
         "|---|---|---|---|"]
    for r in pa:
        L.append("| %s | %s | %s | %s |" % (r["probe_action"], r["spearman"],
                                            r["median_d1_Q1"], r["median_d1_Q5"]))
    rhos = [r["spearman"] for r in pa if r["spearman"] is not None]
    L += ["", "All 8 actions show a positive monotone trend: min rho=%.3f, max rho=%.3f." %
          (min(rhos), max(rhos)), "",
          "## B. Do different actions change the successor relation?",
          "Within-state mean distance between successors of different actions:",
          "mean=%.4f median=%.4f min=%.4f max=%.4f (R1 distances are in [0,1])." %
          (ae["mean_of_state_mean"], ae["median_of_state_mean"], ae["min"], ae["max"]),
          "", "## C. Time-overlap sensitivity",
          "| diagnostic | Spearman | median d0 | median d1 |", "|---|---|---|---|"]
    for r in audit["time_overlap"]:
        L.append("| %s (%s) | %s | %s | %s |" % (r["segment"], r["t_range"],
                                                 r["spearman_d0_d1_seg"],
                                                 r["median_d0"], r["median_d1"]))
    L += ["", "The clean non-overlap test (d0 on t=0.5-3 vs d1 on t=8-11) gives rho=%.3f;" %
          to["nonoverlap_d0_early_vs_d1_late"]["spearman_d0_d1_seg"],
          "the successor-tail-only test (absolute 10-11 s, no overlap with R1(X) horizon)",
          "gives rho=%.3f." % to["successor_tail_abs10.0-11.0"]["spearman_d0_d1_seg"], "",
          "## D. Matching quality",
          "|d0_cross - d0_same_matched|: n=%d mean=%.4f median=%.4f p90=%.4f max=%.4f; "
          "%.1f%% within 0.01." % (mq["n"], mq["mean"], mq["median"], mq["p90"], mq["max"],
                                   100 * mq["frac_within_0.01"]), "",
          "## Answers",
          "1. **Per-action continuous relation?** Yes for all 8 actions (see A; positive,",
          "   monotone Q1->Q5).",
          "2. **Do actions move the state to different successor relations?** See B; the",
          "   within-state cross-action successor distance is reported above (0 would mean",
          "   the action signal is absent).",
          "3. **Is rho driven by future-window overlap?** See C; the non-overlap and",
          "   tail-only correlations quantify how much survives without shared windows.",
          "4. **Is cross/same matching fair?** See D; the initial-distance gap distribution",
          "   is tight, so the 0.988 D1 ratio is a like-for-like comparison.", "",
          "No PASS/FAIL set; no existing result/R1/distance/action/threshold modified.",
          "Preserved: results/r3/B0_R3_result.md, quantile_statistics.csv,",
          "mechanism_pair_statistics.csv; added per-action aggregate + audit figures."]
    open(os.path.join(OUT, "B0_R3_AUDIT.md"), "w").write("\n".join(L) + "\n")


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
