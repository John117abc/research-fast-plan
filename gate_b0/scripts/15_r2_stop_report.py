#!/usr/bin/env python3
"""Gate B0-R2 stop report (G1 FAIL -> no closure, per protocol sections 2/8).

usage: python gate_b0/scripts/15_r2_stop_report.py
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

OUT = os.path.join(B0, "results/r2")
FIG = os.path.join(OUT, "figures")


def main():
    os.makedirs(FIG, exist_ok=True)
    psum = json.load(open(os.path.join(OUT, "r2_pair_summary.json")))
    allp = list(csv.DictReader(open(os.path.join(OUT, "r2_all_pairs.csv"))))
    peq = list(csv.DictReader(open(os.path.join(OUT, "r2_candidate_equivalent_pairs.csv"))))
    cross_d0 = [float(r["d0_mean"]) for r in allp if r["same_coarse"] == "0"]
    same_d0 = [float(r["d0_mean"]) for r in allp if r["same_coarse"] == "1"]
    peq_d0 = [float(r["d0_mean"]) for r in peq]

    stats = {
        "n_peq": psum["n_peq"], "n_matched": psum["n_matched"],
        "n_fine_mechanism_pairs": psum["n_fine_mechanism_pairs"],
        "n_coarse_combos": psum["n_coarse_combos"],
        "peq_d0_min": psum["peq_d0_min"], "peq_d0_median": psum["peq_d0_median"],
        "peq_d0_max": psum["peq_d0_max"], "d0_threshold": psum["d0_threshold"],
        "cross_d0_p10": float(np.percentile(cross_d0, 10)),
        "cross_d0_median": float(np.median(cross_d0)),
        "gates": {"G1_candidate_equivalence": False,
                  "G2_one_step_closure": None,
                  "G3_no_extra_mech_loss": None,
                  "G4_keeps_separation": None},
        "overall_pass": False,
        "stopped_before_closure": True,
        "stop_reason": "|Peq|=%d < 15 (frozen floor); protocol section 2/8" % psum["n_peq"],
    }
    json.dump(stats, open(os.path.join(OUT, "r2_gate_stats.json"), "w"), indent=1)
    _figures(cross_d0, same_d0, peq_d0, peq)
    _report(stats, peq)
    print(json.dumps(stats, indent=1))


def _figures(cross_d0, same_d0, peq_d0, peq):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.figure()
    plt.hist(cross_d0, bins=40, alpha=0.6, density=True, label="cross-mechanism")
    plt.hist(same_d0, bins=40, alpha=0.6, density=True, label="same-mechanism")
    plt.axvline(np.percentile(cross_d0, 10), color="k", ls="--", label="bottom-10%")
    plt.xlabel("d0_mean (R1)"); plt.legend()
    plt.title("Fig R2-1: initial R1 distance distribution")
    plt.savefig(os.path.join(FIG, "r2_fig1_d0_distribution.png"), dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.hist(cross_d0, bins=40, alpha=0.5, density=True, label="all cross pairs")
    if peq_d0:
        plt.hist(peq_d0, bins=8, alpha=0.85, density=True, label="candidate Peq")
    plt.xlabel("d0_mean (R1)"); plt.legend()
    plt.title("Fig R2-2: candidate Peq initial distance vs all cross")
    plt.savefig(os.path.join(FIG, "r2_fig2_peq_d0.png"), dpi=120, bbox_inches="tight")
    plt.close()


def _report(stats, peq):
    lines = ["# Gate B0-R2 result: R1 one-step closure (Dev-108)", "",
             "**STOPPED at pair construction: G1 FAIL.** Per protocol sections 2 and 8,",
             "closure was NOT run and B0-R3 two-step was NOT entered.", "",
             "## G1 candidate equivalence: FAIL",
             "- |Peq| = **%d** (frozen floor 15)." % stats["n_peq"],
             "- Coverage was satisfied: %d fine-mechanism pairs (floor 3), "
             "%d coarse-mechanism combos (floor 2)." %
             (stats["n_fine_mechanism_pairs"], stats["n_coarse_combos"]),
             "- Bottleneck: only **%d mutual cross-mechanism nearest-neighbour pairs "
             "exist at all** before any filter, so the count floor cannot be met." %
             stats["n_peq"],
             "- Peq R1 d0: min=%.4f median=%.4f max=%.4f; cross-pair bottom-10%% "
             "threshold=%.4f." % (stats["peq_d0_min"], stats["peq_d0_median"],
                                  stats["peq_d0_max"], stats["d0_threshold"]),
             "", "## Candidate pairs (auto, no manual selection)", ""]
    for p in peq:
        lines.append("- `%s` ~ `%s` (%s | %s) d0=%.4f" %
                     (p["state_i"], p["state_j"], p["fine_i"], p["fine_j"],
                      float(p["d0_mean"])))
    lines += ["", "## Gates",
              "| Gate | Result |", "|---|---|",
              "| G1 candidate equivalence | FAIL |",
              "| G2 closure vs random cross | not run |",
              "| G3 vs same-mech matched | not run |",
              "| G4 keeps separation | not run |",
              "| overall | FAIL (stopped) |", "",
              "## Interpretation",
              "R1 is non-degenerate (107/108 unique; lead_opt/lead_nec separated), but on",
              "Dev-108 the frozen cross-mechanism candidate rule (mutual NN + bottom-10%",
              "d0 + distinct param group) yields only 11 pairs. So R1 does not yet form",
              "enough stable cross-mechanism repeated structure to justify a closure test.",
              "This is the protocol's G1-FAIL case: stop; do not modify R1, distance,",
              "thresholds or action set in response to this result.", "",
              "## Not run",
              "- one-step closure (r2_closure_*.csv)",
              "- matched/random closure controls",
              "- B0-R3 two-step closure",
              "", "Figures: results/r2/figures/r2_fig1_d0_distribution.png,",
              "r2_fig2_peq_d0.png."]
    open(os.path.join(OUT, "B0_R2_result.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
