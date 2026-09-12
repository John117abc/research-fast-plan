#!/usr/bin/env python3
"""B1 Step 7: mechanism distribution + representative pairs (curves + consistency).

usage: python gate_b1/scripts/54_b1_representatives.py
"""
import csv
import json
import os
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
B0 = os.path.join(ROOT, "gate_b0")
sys.path.insert(0, B1)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
OUT = os.path.join(B1, "results/b1")
FIG = os.path.join(OUT, "figures")
from action_probe.action_set import ACTION_IDS  # noqa: E402


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


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def consistency(vi, vj):
    rhos = []
    for k in range(1, 17):
        ci = np.array([float(vi["V0_%s_t%d" % (u, k)]) + float(vi["VL_%s_t%d" % (u, k)]) for u in ACTION_IDS])
        cj = np.array([float(vj["V0_%s_t%d" % (u, k)]) + float(vj["VL_%s_t%d" % (u, k)]) for u in ACTION_IDS])
        r = pearson(rankdata(ci), rankdata(cj))
        if not np.isnan(r):
            rhos.append(r)
    dVL = []
    for u in ACTION_IDS:
        a = np.array([float(vi["VL_%s_t%d" % (u, k)]) for k in range(1, 17)])
        b = np.array([float(vj["VL_%s_t%d" % (u, k)]) for k in range(1, 17)])
        c = pearson(np.diff(a), np.diff(b))
        if not np.isnan(c):
            dVL.append(c)
    return (float(np.mean(rhos)) if rhos else None, float(np.mean(dVL)) if dVL else None)


def main():
    os.makedirs(FIG, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(OUT, "r1_signatures.csv"))))
    X = {r["state_id"]: r for r in rows}
    # mechanism distribution
    from collections import Counter
    dist = Counter(r["primary_mechanism"] for r in rows)
    with open(os.path.join(OUT, "mechanism_distribution.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["mechanism", "n"])
        for m, c in sorted(dist.items()):
            w.writerow([m, c])
    stats = json.load(open(os.path.join(OUT, "cross_mechanism_neighbor_stats.json")))
    reps = [("cross_nearest", p) for p in stats["representative"]["cross_nearest"]] + \
           [("same_farthest", p) for p in stats["representative"]["same_farthest"]]
    out = []
    for tag, p in reps:
        vi, vj = X[p["i"]], X[p["j"]]
        rho, dVL = consistency(vi, vj)
        out.append({"type": tag, "state_i": p["i"], "state_j": p["j"],
                    "mech_i": p["mech_i"], "mech_j": p["mech_j"], "d": p["d"],
                    "action_rank_consistency": rho, "dVL_trend_corr": dVL})
    with open(os.path.join(OUT, "representative_pairs.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    # figure: representative R1 curves (U2 keep, U6 left)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.arange(1, 17) * 0.5
    fig, axes = plt.subplots(4, 5, figsize=(18, 12))
    axes = axes.ravel()
    for ax, (tag, p) in zip(axes, reps):
        vi, vj = X[p["i"]], X[p["j"]]
        for u, ls in (("U2", "-"), ("U6", "--")):
            for b in ("V0", "VL"):
                ax.plot(t, [float(vi["%s_%s_t%d" % (b, u, k)]) for k in range(1, 17)], ls,
                        alpha=0.8, label="%s %s%s" % (p["i"][:6], u, b))
                ax.plot(t, [float(vj["%s_%s_t%d" % (b, u, k)]) for k in range(1, 17)], ls,
                        alpha=0.5, label="%s %s%s" % (p["j"][:6], u, b))
        ax.set_title("%s d=%.3f %s~%s" % (tag, p["d"], p["mech_i"].split("_")[0],
                                          p["mech_j"].split("_")[0]), fontsize=7)
        ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=4, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "b1_representative_pairs.png"), dpi=110)
    plt.close(fig)
    print("wrote mechanism_distribution.csv + representative_pairs.csv + figure")


if __name__ == "__main__":
    main()
