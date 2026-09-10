#!/usr/bin/env python3
"""Gate B0-R1 diagnostics: diversity, hard-case separation, distance matrix, figs.

usage: python gate_b0/scripts/10_r1_diagnostics.py
writes results/discovery/{r1_signature_stats.json, r1_unique_signature_count.txt,
r1_distance_matrix.csv, r1_group_separability.csv, fig_r1_*.png,
B0_R1_diagnostic.md}
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
GROUPS = ["lead_opt", "lead_nec", "block_nec", "cross_stall"]
# FROZEN stopping-rule thresholds (B0-R1), set before inspecting results:
RULE = {"max_cluster": 5, "min_distinct": 90, "min_sep_ratio": 1.0}


def cols():
    out = []
    for u in ACTION_IDS:
        for b in ("V0", "VL"):
            for k in range(1, 21):
                out.append("%s_%s_t%d" % (b, u, k))
    return out


COLS = cols()


def load_r1():
    rows = list(csv.DictReader(open(os.path.join(OUT, "r1_signatures.csv"))))
    X = np.array([[float(r[c]) for c in COLS] for r in rows])
    return rows, X


def load_r0():
    rows = list(csv.DictReader(open(os.path.join(OUT, "signatures.csv"))))
    sigs = {r["state_id"]: {"M": [int(r["M_%s" % a]) for a in ACTION_IDS],
                            "V": [float(r["V_%s" % a]) for a in ACTION_IDS]} for r in rows}
    return rows, sigs


def mean_abs_matrix(X):
    n = len(X)
    D = np.zeros((n, n))
    for i in range(n):
        D[i] = np.mean(np.abs(X - X[i]), axis=1)
    return D


def sep_ratio(D, idx_a, idx_b):
    within = []
    for idx in (idx_a, idx_b):
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                within.append(D[idx[i], idx[j]])
    between = [D[i, j] for i in idx_a for j in idx_b]
    w = float(np.mean(within)) if within else float("nan")
    b = float(np.mean(between))
    if w == 0:
        return (float("nan") if b == 0 else float("inf")), b, w
    return b / w, b, w


def main():
    rows, X = load_r1()
    ids = [r["state_id"] for r in rows]
    group_idx = {g: [k for k, r in enumerate(rows) if r["fine_mechanism"] == g] for g in GROUPS}

    # diversity
    rounded3 = [tuple(np.round(X[k], 3)) for k in range(len(X))]
    from collections import Counter
    c3 = Counter(rounded3)
    rounded2 = [tuple(np.round(X[k], 2)) for k in range(len(X))]
    c2 = Counter(rounded2)
    allone = int(np.sum(np.all(X >= 0.999, axis=1)))
    stats = {
        "n_states": len(rows), "n_values": len(COLS),
        "unique_r3": len(c3), "largest_cluster_r3": max(c3.values()),
        "unique_r2": len(c2), "largest_cluster_r2": max(c2.values()),
        "all_ones_like": allone,
    }

    # R1 separability (mean-abs over 320 dims)
    D1 = mean_abs_matrix(X)
    np.savetxt(os.path.join(OUT, "r1_distance_matrix.csv"), D1, delimiter=",", fmt="%.5f")
    seps = {}
    for a in GROUPS:
        for b in GROUPS:
            if a < b:
                r, bb, ww = sep_ratio(D1, group_idx[a], group_idx[b])
                seps["%s|%s" % (a, b)] = {"ratio": round(r, 4),
                                          "between": round(bb, 5), "within": round(ww, 5)}

    # R0 separability for comparison
    r0rows, r0sigs = load_r0()
    r0_ids = [r["state_id"] for r in r0rows]
    r0_idx = {g: [k for k, r in enumerate(r0rows) if r["fine_mechanism"] == g] for g in GROUPS}
    D0 = np.zeros((len(r0rows), len(r0rows)))
    for i in range(len(r0rows)):
        for j in range(len(r0rows)):
            D0[i, j] = rd.d_mean(r0sigs[r0_ids[i]], r0sigs[r0_ids[j]])
    seps0 = {}
    for a in GROUPS:
        for b in GROUPS:
            if a < b:
                r, bb, ww = sep_ratio(D0, r0_idx[a], r0_idx[b])
                seps0["%s|%s" % (a, b)] = round(r, 4)

    # hard-case pair of interest
    key = "lead_nec|lead_opt"
    sep_r1 = seps[key]["ratio"]
    sep_r0 = seps0[key]

    # block_nec vs lead_opt current-corridor decay time (KEEP ax=0 -> U2)
    def decay_time(group):
        idx = group_idx[group]
        mean_curve = X[idx][:, COLS.index("V0_U2_t1"):COLS.index("V0_U2_t1") + 20].mean(axis=0)
        below = np.where(mean_curve < 0.5)[0]
        return (int(below[0]) + 1) if len(below) else None, mean_curve
    t_block, curve_block = decay_time("block_nec")
    t_leadopt, curve_leadopt = decay_time("lead_opt")
    t_leadnec, curve_leadnec = decay_time("lead_nec")

    passed = (stats["largest_cluster_r2"] <= RULE["max_cluster"]
              and stats["unique_r2"] >= RULE["min_distinct"]
              and sep_r1 >= RULE["min_sep_ratio"])
    verdict = {
        "frozen_rule": RULE,
        "diversity_recovered": bool(stats["largest_cluster_r2"] <= RULE["max_cluster"]
                                    and stats["unique_r2"] >= RULE["min_distinct"]),
        "lead_opt_vs_lead_nec_separated": bool(sep_r1 >= RULE["min_sep_ratio"]),
        "sep_ratio_r1": sep_r1, "sep_ratio_r0": sep_r0,
        "decay_t_half_U2_block_nec": t_block,
        "decay_t_half_U2_lead_opt": t_leadopt,
        "decay_t_half_U2_lead_nec": t_leadnec,
        "overall": "R1_DEGENERACY_RESOLVED" if passed else "R1_STILL_INSUFFICIENT",
    }
    out = {"stats": stats, "separability_r1": seps, "separability_r0": seps0,
           "verdict": verdict}
    json.dump(out, open(os.path.join(OUT, "r1_signature_stats.json"), "w"), indent=1)
    open(os.path.join(OUT, "r1_unique_signature_count.txt"), "w").write(
        "unique_r3=%d largest_cluster_r3=%d unique_r2=%d largest_cluster_r2=%d all_ones_like=%d\n"
        % (stats["unique_r3"], stats["largest_cluster_r3"], stats["unique_r2"],
           stats["largest_cluster_r2"], stats["all_ones_like"]))
    _write_sep(seps, seps0)
    _figures(rows, X, group_idx)
    _report(stats, seps, seps0, verdict)
    print(json.dumps(out, indent=1))


def _write_sep(seps, seps0):
    with open(os.path.join(OUT, "r1_group_separability.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair", "ratio_R1", "between_R1", "within_R1", "ratio_R0"])
        for k in seps:
            w.writerow([k, seps[k]["ratio"], seps[k]["between"], seps[k]["within"],
                        seps0.get(k)])


def _figures(rows, X, group_idx):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.arange(1, 21) * 0.5
    for g in GROUPS:
        idx = group_idx[g]
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
        for a in ACTION_IDS:
            c0 = [COLS.index("V0_%s_t%d" % (a, k)) for k in range(1, 21)]
            cL = [COLS.index("VL_%s_t%d" % (a, k)) for k in range(1, 21)]
            axes[0].plot(t, X[idx][:, c0].mean(axis=0), marker=".", label=a)
            axes[1].plot(t, X[idx][:, cL].mean(axis=0), marker=".", label=a)
        axes[0].set_title("%s: current-corridor V0 (mean)" % g)
        axes[1].set_title("%s: left-corridor VL (mean)" % g)
        for ax in axes:
            ax.set_xlabel("t (s)"); ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
        axes[1].legend(fontsize=7, ncol=2)
        fig.savefig(os.path.join(OUT, "fig_r1_%s.png" % g), dpi=120, bbox_inches="tight")
        plt.close(fig)

    # focused comparison on U2 (keep, ax=0) and U6 (left, ax=0)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for col, (a, name) in enumerate([("U2", "keep ax=0"), ("U6", "left ax=0")]):
        for row_i, b in enumerate(["V0", "VL"]):
            for g in GROUPS:
                idx = group_idx[g]
                cs = [COLS.index("%s_%s_t%d" % (b, a, k)) for k in range(1, 21)]
                axes[row_i, col].plot(t, X[idx][:, cs].mean(axis=0), marker=".", label=g)
            axes[row_i, col].set_title("%s (%s)" % (b, name))
            axes[row_i, col].set_xlabel("t (s)"); axes[row_i, col].set_ylim(-0.05, 1.05)
            axes[row_i, col].grid(alpha=0.3)
    axes[0, 0].legend(fontsize=7)
    fig.savefig(os.path.join(OUT, "fig_r1_focus_U2_U6.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def _report(stats, seps, seps0, verdict):
    L = ["# Gate B0-R1 diagnostic (development only, Dev-108)", "",
         "R1(X) = {V0^u(t), VL^u(t)} for u in U0..U7, t=0.5..10s (320 values),",
         "normalized by matched free baseline. Frozen stopping rule: %s." % verdict["frozen_rule"],
         "", "## Diversity",
         "- values per state: %d" % stats["n_values"],
         "- unique (round 3): %d / %d; largest cluster: %d" %
         (stats["unique_r3"], stats["n_states"], stats["largest_cluster_r3"]),
         "- unique (round 2): %d / %d; largest cluster: %d" %
         (stats["unique_r2"], stats["n_states"], stats["largest_cluster_r2"]),
         "- all-ones-like states (every V>=0.999): %d" % stats["all_ones_like"],
         "", "R0 reference: unique (round 3)=57/108, largest cluster=47, all-ones-like=47.",
         "", "## Group separability (between/within mean distance)",
         "| pair | R1 ratio | R0 ratio |", "|---|---|---|"]
    for k in seps:
        L.append("| %s | %.3f | %.3f |" % (k, seps[k]["ratio"], seps0.get(k, float("nan"))))
    L += ["",
          "lead_opt vs lead_nec: R1=%.3f (R0=%.3f)" %
          (verdict["sep_ratio_r1"], verdict["sep_ratio_r0"]),
          "", "## block_nec current-corridor decay (mean V0, U2 keep ax=0)",
          "- t where mean V0 first < 0.5: block_nec=%s, lead_nec=%s, lead_opt=%s" %
          (verdict["decay_t_half_U2_block_nec"], verdict["decay_t_half_U2_lead_nec"],
           verdict["decay_t_half_U2_lead_opt"]),
          "", "## Verdict (frozen rule)",
          "- diversity recovered: %s" % verdict["diversity_recovered"],
          "- lead_opt/lead_nec separated: %s" % verdict["lead_opt_vs_lead_nec_separated"],
          "- **%s**" % verdict["overall"],
          "", "Scope note: this round only tests whether R1 resolves R0's information",
          "collapse. No new features, no scene-parameter changes, no training, no",
          "closure Gate. Labels used only as post-hoc visualization groups."]
    open(os.path.join(OUT, "B0_R1_diagnostic.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
