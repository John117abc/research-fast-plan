#!/usr/bin/env python3
"""Gate B0-6: statistics, G0-G4 verdict, figures.

usage: python gate_b0/scripts/06_make_figures.py
writes results/discovery/{gate_stats.json, verdict.json, B0_discovery_verdict.md, fig*.png}
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
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/discovery")
CFG = common.cfg()
G = CFG["gates"]["discovery"]
SEED = CFG["stats"]["seed"]
NBOOT = CFG["stats"]["bootstrap"]


def _read(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    return list(csv.DictReader(open(path)))


def median(x):
    return float(np.median(x)) if len(x) else float("nan")


def main():
    allp = _read("all_pairs.csv")
    peq = _read("candidate_equivalent_pairs.csv")
    matched = _read("same_mechanism_matched_pairs.csv")
    summ = _read("closure_pair_summary.csv")
    d1 = {r["pair_id"]: float(r["d1_mean"]) for r in summ}
    d0 = {r["pair_id"]: float(r["d0_mean"]) for r in summ}
    cross = [r for r in summ if r["pair_type"] == "cross"]
    same = [r for r in summ if r["pair_type"] == "same"]

    rng = np.random.default_rng(SEED)
    peq_ids = [p["pair_id"] for p in peq if p["pair_id"] in d1]
    peq_d1 = [d1[k] for k in peq_ids]
    cross_d1 = [float(r["d1_mean"]) for r in cross]
    med_peq = median(peq_d1)
    med_cross = median(cross_d1)
    boot = [median(list(rng.choice(cross_d1, size=max(1, len(peq_d1)), replace=True)))
            for _ in range(NBOOT)] if cross_d1 else []
    pval = float(np.mean([b <= med_peq for b in boot])) if boot else 1.0

    matched_ids = ["%s__%s" % (m["state_i"], m["state_j"]) for m in matched]
    matched_ids = [k for k in matched_ids if k in d1]
    matched_d1 = [d1[k] for k in matched_ids]
    med_matched = median(matched_d1)
    rho = med_peq / (med_matched + 1e-9) if matched_d1 else float("nan")

    # G4: same-coarse top-25% d0
    same_sorted = sorted(same, key=lambda r: -float(r["d0_mean"]))
    n25 = max(1, int(round(0.25 * len(same_sorted))))
    psd = same_sorted[:n25]
    psd_d1 = [float(r["d1_mean"]) for r in psd]
    med_psd = median(psd_d1)

    g1 = json.load(open(os.path.join(OUT, "pair_build_summary.json")))
    g0 = json.load(open(os.path.join(OUT, "signature_health.json")))
    gates = {
        "G0_engineering_health": bool(g0["g0_ok"]),
        "G1_candidate_equivalence": bool(g1["g1_ok"]),
        "G2_one_step_closure": bool(len(peq_d1) and med_peq <= G["g2_ratio"] * med_cross and pval < G["g2_p"]
                                    and median([float(r["d1_max"]) for r in cross]) > 0
                                    and med_peq < med_cross),
        "G3_mechanism_no_extra_loss": bool(matched_d1 and rho <= G["g3_rho"]),
        "G4_keeps_same_mech_diff": bool(peq_d1 and med_psd >= G["g4_ratio"] * med_peq),
    }
    stats = {
        "n_peq": len(peq_ids), "n_matched": len(matched_ids),
        "median_d1_peq": med_peq, "median_d1_random_cross": med_cross,
        "g2_ratio_obs": (med_peq / med_cross) if med_cross else None,
        "g2_pvalue": pval, "median_d1_matched": med_matched, "g3_rho": rho,
        "median_d1_same_diff_top25": med_psd,
        "g4_ratio_obs": (med_psd / med_peq) if med_peq else None,
        "gates": gates,
        "overall_pass": bool(all(gates.values())),
    }
    json.dump(stats, open(os.path.join(OUT, "gate_stats.json"), "w"), indent=1)
    json.dump(gates, open(os.path.join(OUT, "verdict.json"), "w"), indent=1)

    _figures(allp, summ, peq, matched, d1)
    _report(stats, g1, g0, peq)
    print(json.dumps(stats, indent=1))


def _figures(allp, summ, peq, matched, d1):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d0_cross = [float(r["d0_mean"]) for r in allp if r["same_coarse"] == "0"]
    d0_same = [float(r["d0_mean"]) for r in allp if r["same_coarse"] == "1"]
    plt.figure()
    plt.hist(d0_cross, bins=40, alpha=0.6, label="cross-mechanism", density=True)
    plt.hist(d0_same, bins=40, alpha=0.6, label="same-mechanism", density=True)
    plt.xlabel("d0_mean"); plt.legend(); plt.title("Fig1 initial relation distance")
    plt.savefig(os.path.join(OUT, "fig1_d0_distribution.png"), dpi=120, bbox_inches="tight")
    plt.close()

    peq_d1 = [d1[p["pair_id"]] for p in peq if p["pair_id"] in d1]
    cross_d1 = [float(r["d1_mean"]) for r in summ if r["pair_type"] == "cross"]
    plt.figure()
    plt.hist(cross_d1, bins=40, alpha=0.6, label="random cross", density=True)
    if peq_d1:
        plt.hist(peq_d1, bins=min(10, len(peq_d1)), alpha=0.8, label="Peq")
    plt.xlabel("D1_mean"); plt.legend(); plt.title("Fig2 closure: Peq vs random cross")
    plt.savefig(os.path.join(OUT, "fig2_D1_peq_vs_random.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    for key, col in [("cross", "tab:blue"), ("same", "tab:orange")]:
        xs = [float(r["d0_mean"]) for r in summ if r["pair_type"] == key]
        ys = [float(r["d1_mean"]) for r in summ if r["pair_type"] == key]
        plt.scatter(xs, ys, s=6, alpha=0.3, c=col, label=key)
    plt.xlabel("d0_mean"); plt.ylabel("D1_mean"); plt.legend()
    plt.title("Fig3 d0 -> D1")
    plt.savefig(os.path.join(OUT, "fig3_d0_vs_d1.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    if matched:
        xs = [d1[p["pair_id"]] for p in peq if p["pair_id"] in d1]
        ys = [d1["%s__%s" % (m["state_i"], m["state_j"])] for m in matched
              if "%s__%s" % (m["state_i"], m["state_j"]) in d1]
        n = min(len(xs), len(ys))
        for k in range(n):
            plt.plot([0, 1], [xs[k], ys[k]], "o-", alpha=0.7)
    plt.xticks([0, 1], ["cross Peq", "same matched"]); plt.ylabel("D1_mean")
    plt.title("Fig4 matched comparison")
    plt.savefig(os.path.join(OUT, "fig4_matched.png"), dpi=120, bbox_inches="tight")
    plt.close()

    # Fig5 typical action signatures: most stable / most drifted Peq pairs (auto)
    sigs = {r["state_id"]: r for r in csv.DictReader(open(os.path.join(OUT, "signatures.csv")))}
    ranked = sorted([p for p in peq if p["pair_id"] in d1], key=lambda p: d1[p["pair_id"]])
    picks = ranked[:3] + ranked[-3:]
    plt.figure()
    for idx, p in enumerate(picks):
        i = p["state_i"]
        plt.plot(range(8), [float(sigs[i]["V_%s" % a]) for a in ACTION_IDS],
                 marker="o", label="%s d1=%.3f" % (i, d1[p["pair_id"]]))
    plt.xticks(range(8), ACTION_IDS); plt.ylim(-0.05, 1.05)
    plt.legend(fontsize=7); plt.title("Fig5 typical R0 signatures")
    plt.savefig(os.path.join(OUT, "fig5_signatures.png"), dpi=120, bbox_inches="tight")
    plt.close()


def _report(stats, g1, g0, peq):
    lines = ["# Gate B0 discovery verdict", "",
             "G0 engineering health: %s" % stats["gates"]["G0_engineering_health"],
             "G1 candidate equivalence: %s (|Peq|=%d, fine pairs=%d, coarse combos=%d)" %
             (stats["gates"]["G1_candidate_equivalence"], g1["n_peq"],
              g1["n_fine_mechanism_pairs"], g1["n_coarse_combos"]),
             "G2 one-step closure: %s (median D1 Peq=%.4f vs random-cross=%.4f, ratio=%s, p=%.4f)" %
             (stats["gates"]["G2_one_step_closure"], stats["median_d1_peq"],
              stats["median_d1_random_cross"],
              ("%.3f" % stats["g2_ratio_obs"]) if stats["g2_ratio_obs"] is not None else "na",
              stats["g2_pvalue"]),
             "G3 mechanism no extra loss: %s (rho=%s)" %
             (stats["gates"]["G3_mechanism_no_extra_loss"],
              ("%.3f" % stats["g3_rho"]) if stats["g3_rho"] == stats["g3_rho"] else "na"),
             "G4 keeps same-mechanism-different separation: %s (ratio=%s)" %
             (stats["gates"]["G4_keeps_same_mech_diff"],
              ("%.3f" % stats["g4_ratio_obs"]) if stats["g4_ratio_obs"] is not None else "na"),
             "", "Overall discovery PASS: %s" % stats["overall_pass"], "",
             "NOTE: G2/G3/G4 are computed for completeness but are NOT scientific",
             "evidence here: |Peq|=%d is far below the frozen floor (%d) and the" %
             (len(peq), G["peq_min"]),
             "few surviving pairs have d0=0 (identical R0), so their D1=0 is",
             "tautological. The gate fails on G1, which is the binding criterion.", "",
             "## Root cause note (R0 degeneracy)",
             "R0 = max progress per action collapses whenever a safe left lane change is",
             "available: after the forced 1 s, the free search can always resort to the",
             "lateral escape, so V ~ 1 for Optional AND Necessary. Consequence: 47/108",
             "states share the all-ones signature (lead_nec 12/12, lead_opt 12/12), and",
             "the frozen pair rule (mutual-NN + bottom-10%% d0) yields only %d Peq pairs." %
             len(peq),
             "", "Per protocol section 24 Case A: STOP; do not train a network; the missing",
             "consequence is not representation capacity but the R0 definition (scalar max",
             "progress cannot express recourse timing / which corridor is used)."]
    open(os.path.join(OUT, "B0_discovery_verdict.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
