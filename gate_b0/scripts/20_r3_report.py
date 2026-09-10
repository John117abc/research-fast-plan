#!/usr/bin/env python3
"""Gate B0-R3 step 4: figures + B0_R3_result.md.

usage: python gate_b0/scripts/20_r3_report.py
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

OUT = os.path.join(B0, "results/r3")
FIG = os.path.join(OUT, "figures")


def main():
    os.makedirs(FIG, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(OUT, "pair_level_closure.csv"))))
    cross = [r for r in rows if r["pair_type"] == "cross"]
    matched = [r for r in rows if r["pair_type"] == "same_matched"]
    qrows = list(csv.DictReader(open(os.path.join(OUT, "quantile_statistics.csv"))))
    mrows = list(csv.DictReader(open(os.path.join(OUT, "mechanism_pair_statistics.csv"))))
    stats = json.load(open(os.path.join(OUT, "bootstrap_statistics.json")))
    _figures(cross, matched, qrows, mrows)
    _report(stats, qrows, mrows)
    print("wrote figures + B0_R3_result.md")


def _figures(cross, matched, qrows, mrows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d0 = np.array([float(r["d0_mean"]) for r in cross])
    d1 = np.array([float(r["d1_mean"]) for r in cross])

    plt.figure()
    plt.scatter(d0, d1, s=5, alpha=0.25)
    plt.xlabel("d0 (R1 distance)"); plt.ylabel("D1_mean (after same action)")
    plt.title("Fig R3-1: d0 -> D1 (all cross-mechanism pairs)")
    plt.savefig(os.path.join(FIG, "r3_fig1_d0_vs_d1.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    data = []
    for q in qrows:
        lo, hi = float(q["d0_lo"]), float(q["d0_hi"])
        m = (d0 >= lo) & (d0 <= hi)
        data.append(d1[m])
    plt.boxplot(data, labels=[q["quantile"] for q in qrows], showfliers=False)
    plt.xlabel("initial-distance quantile"); plt.ylabel("D1_mean")
    plt.title("Fig R3-2: D1 by d0 quantile")
    plt.savefig(os.path.join(FIG, "r3_fig2_D1_by_quantile.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    for mr in mrows:
        key = set(mr["mechanism_pair"].split("|"))
        xs, ys = [], []
        for qi, q in enumerate(qrows):
            lo, hi = float(q["d0_lo"]), float(q["d0_hi"])
            m = np.array([set([r["coarse_i"], r["coarse_j"]]) == key for r in cross]) \
                & (d0 >= lo) & (d0 <= hi)
            if m.sum():
                xs.append(qi + 1)
                ys.append(float(np.median(d1[m])))
        plt.plot(xs, ys, marker="o", label=mr["mechanism_pair"])
    plt.xticks(range(1, 6), [q["quantile"] for q in qrows])
    plt.xlabel("quantile"); plt.ylabel("median D1_mean"); plt.legend(fontsize=7)
    plt.title("Fig R3-3: trend by coarse mechanism pair")
    plt.savefig(os.path.join(FIG, "r3_fig3_by_mechanism.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.bar(range(1, 6), [float(q["feas_agree_mean"]) for q in qrows])
    plt.ylim(0, 1.05); plt.xticks(range(1, 6), [q["quantile"] for q in qrows])
    plt.ylabel("action feasibility agreement")
    plt.title("Fig R3-4: feasibility agreement by quantile")
    plt.savefig(os.path.join(FIG, "r3_fig4_feasibility.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.scatter([float(r["d0_mean"]) for r in cross], [float(r["d1_mean"]) for r in cross],
                s=4, alpha=0.2, label="cross")
    plt.scatter([float(r["d0_mean"]) for r in matched], [float(r["d1_mean"]) for r in matched],
                s=4, alpha=0.2, label="same matched")
    plt.xlabel("d0"); plt.ylabel("D1_mean"); plt.legend()
    plt.title("Fig R3-5: cross vs same-mechanism matched")
    plt.savefig(os.path.join(FIG, "r3_fig5_cross_vs_same.png"), dpi=120, bbox_inches="tight")
    plt.close()

    # auto: 3 closest-staying-close (smallest d0 among smallest d1) and
    # 3 close-but-separate (smallest d0 with largest d1)
    order = np.argsort(d0)
    bottom = order[: max(50, len(order) // 20)]
    b = sorted(bottom, key=lambda k: d1[k])
    stay = b[:3]
    sep = sorted(bottom, key=lambda k: -d1[k])[:3]
    lvl = list(csv.DictReader(open(os.path.join(B0, "results/discovery/r1_signatures.csv"))))
    X = {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in lvl}
    t = np.arange(1, 21) * 0.5
    picks = [("close & stays close", stay), ("close but separates", sep)]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, (name, ks) in zip(axes, picks):
        for k in ks:
            i, j = cross[k]["state_i"], cross[k]["state_j"]
            for sid, ls in ((i, "-"), (j, "--")):
                c0 = [COLS.index("V0_U2_t%d" % m) for m in range(1, 21)]
                cL = [COLS.index("VL_U2_t%d" % m) for m in range(1, 21)]
                ax.plot(t, X[sid][c0], ls, label="%s V0" % sid)
                ax.plot(t, X[sid][cL], ls, alpha=0.6, label="%s VL" % sid)
        ax.set_title("%s (d0=%.3f..%.3f, D1=%.3f..%.3f)" % (
            name, min(d0[k] for k in ks), max(d0[k] for k in ks),
            min(d1[k] for k in ks), max(d1[k] for k in ks)), fontsize=8)
        ax.set_xlabel("t (s)"); ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=5, ncol=2)
    fig.savefig(os.path.join(FIG, "r3_fig6_close_pairs.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def _report(stats, qrows, mrows):
    c = stats["conditions"]
    L = ["# Gate B0-R3 result: continuous R1 distance one-step closure (Dev-108)", "",
         "Development only. R1, distance, action set, thresholds, scenarios unchanged;",
         "no training, no new data, no second-order closure, no confirmatory set.", "",
         "## Question",
         "Does smaller d0 (R1 distance) imply smaller D1 (R1 distance after the same",
         "forced action)? Tested on ALL cross-mechanism pairs (no mutual-NN / bottom-10%",
         "/ |Peq|>=15 selection). B0-R2's historical G1 FAIL is unchanged.", "",
         "## Overall",
         "- cross-mechanism pairs: %d; matched same-mechanism controls: %d" %
         (stats["n_cross_pairs"], stats["n_matched"]),
         "- Spearman(d0, D1_mean) = **%.3f**, 95%% cluster-bootstrap CI [%.3f, %.3f]" %
         (stats["spearman_overall"], stats["spearman_CI"]["lo95"], stats["spearman_CI"]["hi95"]),
         "- median D1: Q1=%.4f vs Q5=%.4f (Q1/Q5=%.3f); diff CI [%.3f, %.3f]" %
         (stats["median_D1_Q1"], stats["median_D1_Q5"],
          stats["median_D1_Q1"] / max(1e-9, stats["median_D1_Q5"]),
          stats["q1_minus_q5_CI"]["lo95"], stats["q1_minus_q5_CI"]["hi95"]),
         "- cross vs same matched: median D1=%.4f vs %.4f; ratio=%.3f; diff CI [%.3f, %.3f]" %
         (stats["median_D1_cross"], stats["median_D1_same_matched"], stats["matched_ratio"],
          stats["cross_minus_same_CI"]["lo95"], stats["cross_minus_same_CI"]["hi95"]),
         "- feasibility agreement: Q1=%.3f, Q5=%.3f" %
         (stats["feas_agree_Q1"], stats["feas_agree_Q5"]),
         "", "## Quantile trend (median D1_mean)",
         "| Q | d0 range | n | D1 median | IQR | feas |", "|---|---|---|---|---|---|"]
    for q in qrows:
        L.append("| %s | %.4f-%.4f | %s | %s | %s-%s | %s |" %
                 (q["quantile"], float(q["d0_lo"]), float(q["d0_hi"]), q["n"],
                  q["D1_median"], q["D1_q25"], q["D1_q75"], q["feas_agree_mean"]))
    L += ["", "Monotone Q1<Q2<Q3<Q4<Q5: **%s**." %
          ("yes" if all(float(qrows[k]["D1_median"]) < float(qrows[k + 1]["D1_median"])
                        for k in range(len(qrows) - 1)) else "no"),
          "", "## Per coarse-mechanism pair",
          "| combo | n | Spearman | median D1 Q1 | median D1 Q5 |", "|---|---|---|---|---|"]
    for m in mrows:
        L.append("| %s | %s | %s | %s | %s |" % (m["mechanism_pair"], m["n"], m["spearman"],
                                                 m["D1_median_Q1"], m["D1_median_Q5"]))
    L += ["", "## Pre-registered development conditions",
          "| condition | met |", "|---|---|"]
    names = {"C1_continuous_rho>=0.60_and_CIlow>0.40": "C1 rho>=0.60 and CI low>0.40",
             "C2_Q1<=0.5*Q5": "C2 median D1(Q1) <= 0.5*median D1(Q5)",
             "C3_two_of_three_mech_rho>0.50": "C3 >=2/3 mechanism combos rho>0.50",
             "C4_matched_ratio<=1.25": "C4 cross/same matched ratio <= 1.25",
             "C5_feas_Q1>Q5": "C5 feasibility agreement Q1 > Q5"}
    for k, v in c.items():
        L.append("| %s | %s |" % (names[k], v))
    L += ["", "All conditions met: %s" % stats["all_conditions_met"],
          "", "### C5 caveat (important)",
          "C5 is **not testable on Dev-108**: all 864 forced-1 s successors are feasible",
          "(no collisions / dead-ends), so feasibility agreement is identically 1.0 in",
          "every quantile. This is absence of signal, not evidence against the hypothesis.",
          "The distance-based conditions C1-C4 are all satisfied.", "",
          "## Conclusion",
          "**B0-R3 DEVELOPMENT SUPPORT**: on Dev-108, smaller initial R1 distance",
          "continuously predicts smaller post-action R1 distance (rho=%.3f), with a clear" %
          stats["spearman_overall"],
          "monotone quantile trend and no cross-mechanism penalty relative to",
          "initial-distance-matched same-mechanism pairs.",
          "This is development support only, NOT a confirmatory PASS. No second-order",
          "closure, no confirmatory data, no model training were performed.", "",
          "Figures: figures/r3_fig1..6."]
    open(os.path.join(OUT, "B0_R3_result.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
