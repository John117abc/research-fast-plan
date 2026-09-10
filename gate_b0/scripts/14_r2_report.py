#!/usr/bin/env python3
"""Gate B0-R2 step 4: figures + B0_R2_result.md.

usage: python gate_b0/scripts/14_r2_report.py
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
FIG = os.path.join(OUT, "figures")


def _read(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    return list(csv.DictReader(open(path)))


def main():
    os.makedirs(FIG, exist_ok=True)
    allp = _read("r2_all_pairs.csv")
    peq = _read("r2_candidate_equivalent_pairs.csv")
    matched = _read("r2_same_mechanism_matched_pairs.csv")
    summ = _read("r2_closure_pair_summary.csv")
    stats = json.load(open(os.path.join(OUT, "r2_gate_stats.json")))
    psum = json.load(open(os.path.join(OUT, "r2_pair_summary.json")))
    d1 = {r["pair_id"]: float(r["d1_mean"]) for r in summ}
    d0 = {r["pair_id"]: float(r["d0_mean"]) for r in summ}
    _figures(allp, peq, matched, summ, d1, d0)
    _report(stats, psum, peq, d1, d0)
    print("wrote figures + B0_R2_result.md")


def _figures(allp, peq, matched, summ, d1, d0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cross = [r for r in summ if r["pair_type"] == "cross"]
    cross_d1 = [float(r["d1_mean"]) for r in cross]
    peq_d1 = [d1[p["pair_id"]] for p in peq if p["pair_id"] in d1]

    plt.figure()
    plt.hist(cross_d1, bins=40, alpha=0.6, density=True, label="random cross")
    if peq_d1:
        plt.hist(peq_d1, bins=min(12, max(3, len(peq_d1))), alpha=0.8, density=True, label="Peq")
    plt.xlabel("D1_mean"); plt.legend(); plt.title("Fig R2-1: D1_mean Peq vs random cross")
    plt.savefig(os.path.join(FIG, "r2_fig1_D1_peq_vs_random.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    for key, col in [("cross", "tab:blue"), ("same", "tab:orange")]:
        xs = [float(r["d0_mean"]) for r in summ if r["pair_type"] == key]
        ys = [float(r["d1_mean"]) for r in summ if r["pair_type"] == key]
        plt.scatter(xs, ys, s=6, alpha=0.3, c=col, label=key)
    if peq_d1:
        plt.scatter([d0[p["pair_id"]] for p in peq if p["pair_id"] in d1], peq_d1,
                    s=30, facecolors="none", edgecolors="red", label="Peq")
    plt.xlabel("d0_mean"); plt.ylabel("D1_mean"); plt.legend()
    plt.title("Fig R2-2: d0 -> D1")
    plt.savefig(os.path.join(FIG, "r2_fig2_d0_vs_d1.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    xs, ys = [], []
    for p in peq:
        k = "%s__%s" % (p["state_i"], p["state_j"])
        if k in d1:
            xs.append(d1[k])
    for m in matched:
        k = "%s__%s" % (m["state_i"], m["state_j"])
        if k in d1:
            ys.append(d1[k])
    for k in range(min(len(xs), len(ys))):
        plt.plot([0, 1], [xs[k], ys[k]], "o-", alpha=0.7)
    plt.xticks([0, 1], ["cross Peq", "same matched"]); plt.ylabel("D1_mean")
    plt.title("Fig R2-3: matched comparison")
    plt.savefig(os.path.join(FIG, "r2_fig3_matched.png"), dpi=120, bbox_inches="tight")
    plt.close()

    ranked = sorted([p for p in peq if p["pair_id"] in d1], key=lambda p: d1[p["pair_id"]])
    picks = ranked[:3] + ranked[-3:]
    plt.figure(figsize=(10, 4))
    labels = ["%s__%s" % (p["state_i"], p["state_j"]) for p in picks]
    plt.bar(range(len(picks)), [d0[p["pair_id"]] for p in picks], alpha=0.5, label="d0")
    plt.bar(range(len(picks)), [d1[p["pair_id"]] for p in picks], alpha=0.8, label="D1_mean")
    plt.xticks(range(len(picks)), labels, rotation=45, ha="right", fontsize=7)
    plt.legend(); plt.title("Fig R2-4: most stable (left 3) / most drifted (right 3)")
    plt.savefig(os.path.join(FIG, "r2_fig4_stable_drift.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(9, 4))
    groups = {}
    for r in cross:
        key = "|".join(sorted([r["coarse_i"], r["coarse_j"]]))
        groups.setdefault(key, []).append(float(r["d1_mean"]))
    keys = sorted(groups)
    plt.boxplot([groups[k] for k in keys], labels=keys, showfliers=False)
    if peq_d1:
        plt.scatter([1] * len(peq_d1), peq_d1, color="red", zorder=3, label="Peq")
    plt.xticks(rotation=20); plt.ylabel("D1_mean"); plt.legend()
    plt.title("Fig R2-5: closure by coarse mechanism pair")
    plt.savefig(os.path.join(FIG, "r2_fig5_by_coarse_pair.png"), dpi=120, bbox_inches="tight")
    plt.close()


def _report(stats, psum, peq, d1, d0):
    g = stats["gates"]
    L = ["# Gate B0-R2 result: R1 one-step behavioral closure (Dev-108)", "",
         "R1(X) = {V0^u(t), VL^u(t)}; distance = mean-abs over 320 values;",
         "one-step successors T(X,u) recomputed with full R1 at t0+1s.",
         "Frozen thresholds reused from B0 discovery. No training, no new data,",
         "no R0/action/distance changes.", "",
         "## Pair construction",
         "- |Peq| = %d (floor %d); fine-mechanism pairs = %d (floor %d); "
         "coarse combos = %d (floor %d)" %
         (psum["n_peq"], 15, psum["n_fine_mechanism_pairs"], 3,
          psum["n_coarse_combos"], 2),
         "- Peq d0: min=%.4f median=%.4f max=%.4f; bottom-10%% threshold=%.4f" %
         (psum["peq_d0_min"], psum["peq_d0_median"], psum["peq_d0_max"],
          psum["d0_threshold"]),
         "", "## Gate verdict",
         "| Gate | Result |", "|---|---|",
         "| G1 candidate equivalence | %s |" % g["G1_candidate_equivalence"],
         "| G2 closure vs random cross | %s |" % g["G2_one_step_closure"],
         "| G3 not worse than same-mech matched | %s |" % g["G3_no_extra_mech_loss"],
         "| G4 keeps same-mech-different separation | %s |" % g["G4_keeps_separation"],
         "| **overall** | **%s** |" % stats["overall_pass"], "",
         "## Numbers",
         "- median D1_mean: Peq=%.4f vs random-cross=%.4f (ratio=%s)" %
         (stats["median_D1mean_peq"], stats["median_D1mean_random_cross"],
          ("%.3f" % stats["g2_ratio_obs"]) if stats["g2_ratio_obs"] is not None else "na"),
         "- median D1_max: Peq=%.4f vs random-cross=%.4f" %
         (stats["median_D1max_peq"], stats["median_D1max_random_cross"]),
         "- permutation p = %.4f" % stats["g2_pvalue"],
         "- median D1_mean matched: %s; rho = %s" %
         (("nan" if stats["median_D1mean_matched"] != stats["median_D1mean_matched"]
           else "%.4f" % stats["median_D1mean_matched"]),
          ("nan" if stats["g3_rho"] != stats["g3_rho"] else "%.3f" % stats["g3_rho"])),
         "- same-mech top-25%% d0: median D1=%.4f; G4 ratio=%s" %
         (stats["median_D1mean_same_diff_top25"],
          ("%.3f" % stats["g4_ratio_obs"]) if stats["g4_ratio_obs"] is not None else "na"),
         "", "## Stopping rule",
         "- G1 FAIL -> stop: R1 non-degenerate but no stable cross-mechanism repeats.",
         "- G1 PASS, G2/G3 FAIL -> stop: R1 descriptive, not a behavioral-equivalence state.",
         "- G2/G3 PASS, G4 FAIL -> stop: R1 may over-compress.",
         "- Only G1-G4 all PASS allows discussing B0-R3 two-step closure.",
         "", "Applied: **%s**." %
         ("continue to B0-R3 discussion" if stats["overall_pass"] else "STOP"),
         "", "Figures: results/r2/figures/ (5). No two-step closure run."]
    open(os.path.join(OUT, "B0_R2_result.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
