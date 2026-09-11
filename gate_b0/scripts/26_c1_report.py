#!/usr/bin/env python3
"""B0-C1 step 4: figures + B0_C1_result.md.

usage: python gate_b0/scripts/26_c1_report.py
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

OUT = os.path.join(B0, "results/confirmatory")
FIG = os.path.join(OUT, "figures")


def main():
    os.makedirs(FIG, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(OUT, "pair_level_closure.csv"))))
    cross = [r for r in rows if r["pair_type"] == "cross"]
    matched = [r for r in rows if r["pair_type"] == "same_matched"]
    qrows = list(csv.DictReader(open(os.path.join(OUT, "quantile_statistics.csv"))))
    mrows = list(csv.DictReader(open(os.path.join(OUT, "mechanism_pair_statistics.csv"))))
    stats = json.load(open(os.path.join(OUT, "bootstrap_statistics.json")))
    eff = list(csv.DictReader(open(os.path.join(OUT, "action_effect_audit.csv"))))
    _figures(cross, matched, qrows, mrows, eff)
    _report(stats, qrows, mrows, eff)
    print("wrote figures + B0_C1_result.md")


def _figures(cross, matched, qrows, mrows, eff):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d0 = np.array([float(r["d0_mean"]) for r in cross])
    d1 = np.array([float(r["d1_mean"]) for r in cross])
    plt.figure(); plt.scatter(d0, d1, s=6, alpha=0.25)
    plt.xlabel("d0"); plt.ylabel("D1_mean"); plt.title("C1 Fig1: d0 -> D1 (cross-mechanism)")
    plt.savefig(os.path.join(FIG, "c1_fig1_d0_vs_d1.png"), dpi=120, bbox_inches="tight"); plt.close()

    plt.figure(); data = []
    for q in qrows:
        lo, hi = float(q["d0_lo"]), float(q["d0_hi"])
        data.append(d1[(d0 >= lo) & (d0 <= hi)])
    plt.boxplot(data, labels=[q["quantile"] for q in qrows], showfliers=False)
    plt.xlabel("quantile"); plt.ylabel("D1_mean"); plt.title("C1 Fig2: D1 by quantile")
    plt.savefig(os.path.join(FIG, "c1_fig2_D1_by_quantile.png"), dpi=120, bbox_inches="tight"); plt.close()

    plt.figure()
    for mr in mrows:
        key = set(mr["mechanism_pair"].split("|")); xs, ys = [], []
        for qi, q in enumerate(qrows):
            lo, hi = float(q["d0_lo"]), float(q["d0_hi"])
            m = np.array([set([r["coarse_i"], r["coarse_j"]]) == key for r in cross]) \
                & (d0 >= lo) & (d0 <= hi)
            if m.sum():
                xs.append(qi + 1); ys.append(float(np.median(d1[m])))
        plt.plot(xs, ys, marker="o", label=mr["mechanism_pair"])
    plt.xticks(range(1, 6), [q["quantile"] for q in qrows]); plt.legend(fontsize=7)
    plt.xlabel("quantile"); plt.ylabel("median D1"); plt.title("C1 Fig3: by coarse mechanism pair")
    plt.savefig(os.path.join(FIG, "c1_fig3_by_mechanism.png"), dpi=120, bbox_inches="tight"); plt.close()

    plt.figure()
    plt.scatter([float(r["d0_mean"]) for r in cross], [float(r["d1_mean"]) for r in cross],
                s=4, alpha=0.2, label="cross")
    plt.scatter([float(r["d0_mean"]) for r in matched], [float(r["d1_mean"]) for r in matched],
                s=4, alpha=0.2, label="same matched")
    plt.xlabel("d0"); plt.ylabel("D1_mean"); plt.legend(); plt.title("C1 Fig4: cross vs same matched")
    plt.savefig(os.path.join(FIG, "c1_fig4_cross_vs_same.png"), dpi=120, bbox_inches="tight"); plt.close()

    plt.figure()
    plt.hist([float(r["mean_pairwise_dist"]) for r in eff], bins=20)
    plt.xlabel("mean successor distance across different actions")
    plt.title("C1 Fig5: action effect (audit B)")
    plt.savefig(os.path.join(FIG, "c1_fig5_action_effect.png"), dpi=120, bbox_inches="tight"); plt.close()

    order = np.argsort(d0); bottom = order[: max(20, len(order) // 20)]
    stay = sorted(bottom, key=lambda k: d1[k])[:3]
    sep = sorted(bottom, key=lambda k: -d1[k])[:3]
    lvl = list(csv.DictReader(open(os.path.join(OUT, "r1_signatures.csv"))))
    X = {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in lvl}
    t = np.arange(1, 21) * 0.5
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, (name, ks) in zip(axes, [("close & stays close", stay), ("close but separates", sep)]):
        for k in ks:
            i, j = cross[k]["state_i"], cross[k]["state_j"]
            for sid, ls in ((i, "-"), (j, "--")):
                ax.plot(t, X[sid][[COLS.index("V0_U2_t%d" % m) for m in range(1, 21)]], ls, label="%s V0" % sid)
                ax.plot(t, X[sid][[COLS.index("VL_U2_t%d" % m) for m in range(1, 21)]], ls, alpha=0.6, label="%s VL" % sid)
        ax.set_title(name, fontsize=9); ax.set_xlabel("t (s)"); ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=5, ncol=2)
    fig.savefig(os.path.join(FIG, "c1_fig6_close_pairs.png"), dpi=120, bbox_inches="tight"); plt.close(fig)


def _report(stats, qrows, mrows, eff):
    c = stats["conditions"]
    ef = np.array([float(r["mean_pairwise_dist"]) for r in eff])
    L = ["# B0-C1 confirmatory result (independent CARLA states)", "",
         "Frozen R1 / distance / action set / stats; 72 NEW states (9 cells x 8);",
         "all cross-mechanism pairs; state-level cluster bootstrap (10000, seed 100).",
         "C5 dropped from the main Gate before unblinding (Dev-108 had 864/864 feasible).", "",
         "## Gate verdict",
         "| condition | met |", "|---|---|",
         "| C1 rho>=0.60 and CI low>0.40 | %s |" % c["C1_continuous_rho>=0.60_and_CIlow>0.40"],
         "| C2 median D1(Q1) <= 0.5*median D1(Q5) | %s |" % c["C2_Q1<=0.5*Q5"],
         "| C3 >=2/3 mechanism combos rho>0.50 | %s |" % c["C3_two_of_three_mech_rho>0.50"],
         "| C4 cross/same matched ratio <= 1.25 | %s |" % c["C4_matched_ratio<=1.25"],
         "| **overall confirmatory** | **%s** |" % stats["overall_pass"], "",
         "## Headline numbers",
         "- overall Spearman(d0,D1_mean) = **%.3f**, 95%% CI [%.3f, %.3f]" %
         (stats["spearman_overall"], stats["spearman_CI"]["lo95"], stats["spearman_CI"]["hi95"]),
         "- median D1: Q1=%.4f vs Q5=%.4f (ratio=%.3f); diff CI [%.3f, %.3f]" %
         (stats["median_D1_Q1"], stats["median_D1_Q5"],
          stats["median_D1_Q1"] / max(1e-9, stats["median_D1_Q5"]),
          stats["q1_minus_q5_CI"]["lo95"], stats["q1_minus_q5_CI"]["hi95"]),
         "- cross vs same matched median D1: %.4f vs %.4f (ratio=%.3f); diff CI [%.3f, %.3f]" %
         (stats["median_D1_cross"], stats["median_D1_same_matched"], stats["matched_ratio"],
          stats["cross_minus_same_CI"]["lo95"], stats["cross_minus_same_CI"]["hi95"]),
         "- feasibility agreement mean = %.3f (C5 not a Gate)" % stats["feasibility_agree_mean"],
         "", "## Quantile trend", "| Q | d0 range | n | D1 median | IQR |", "|---|---|---|---|---|"]
    for q in qrows:
        L.append("| %s | %.4f-%.4f | %s | %s | %s-%s |" %
                 (q["quantile"], float(q["d0_lo"]), float(q["d0_hi"]), q["n"],
                  q["D1_median"], q["D1_q25"], q["D1_q75"]))
    L += ["", "Monotone: **%s**." %
          ("yes" if all(float(qrows[k]["D1_median"]) < float(qrows[k + 1]["D1_median"])
                        for k in range(len(qrows) - 1)) else "no"),
          "", "## Per coarse-mechanism pair", "| combo | n | Spearman |", "|---|---|---|"]
    for m in mrows:
        L.append("| %s | %s | %s |" % (m["mechanism_pair"], m["n"], m["spearman"]))
    L += ["", "## Pre-registered audits",
          "- Audit A (non-overlap d0 0.5-3s vs d1 8-11s): Spearman = %.3f" % stats["nonoverlap_spearman"],
          "- Audit B (action effect): within-state successor distance across different",
          "  actions mean=%.4f min=%.4f (0 would mean no action signal)." %
          (stats["action_effect_mean"], stats["action_effect_min"]),
          "", "## Conclusion"]
    if stats["overall_pass"]:
        L += ["**B0-C1 CONFIRMATORY PASS**: on 72 independent CARLA states the frozen R1",
              "continuous distance reproduces the one-step behavioral-consistency relation",
              "across physical mechanisms."]
    else:
        L += ["**B0-C1 CONFIRMATORY FAIL**: at least one of C1-C4 did not hold; the",
              "Dev-108 result does NOT carry over as a confirmed result."]
    L += ["", "Limits: this supports *one-step behavioral consistency of the R1 distance*",
          "only. It does NOT prove a final Driving Relation, nor end-to-end generalization.",
          "No second-order closure, no Waymo/PlanT, no model training. Figures: figures/."]
    open(os.path.join(OUT, "B0_C1_result.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
