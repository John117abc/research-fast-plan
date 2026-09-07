#!/usr/bin/env python3
"""Gate6 6.12A: plot dW trajectories (same scale per pair) for representative
Primary cross-scene pairs. dW_k path = (dx_t, dy_t) over waypoints t."""
import csv
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLOCKS = ["I1", "I2", "I3", "I4", "I5"]
LABEL = {"I1": "+2m", "I2": "-2m", "I3": "spd*1.2", "I4": "spd*0.8", "I5": "remove"}
COLOR = {"I1": "#d62728", "I2": "#1f77b4", "I3": "#2ca02c", "I4": "#ff7f0e", "I5": "#9467bd"}


def main():
    cand = [c for c in csv.DictReader(open("gate6/pair_cross_primary_confounds.csv"))
            if c["same_route"] == "0"]
    by = defaultdict(list)
    for c in cand:
        by[tuple(sorted((c["group_A"], c["group_B"])))].append(c)
    outdir = "gate6/figures/dw"
    os.makedirs(outdir, exist_ok=True)
    made = []
    for combo in sorted(by):
        cs = sorted(by[combo], key=lambda x: -float(x["cos_dir"]))[:1]
        for c in cs:
            sa, sb = c["state_A"], c["state_B"]
            da = dict(np.load(os.path.join("gate6/signatures", f"{sa}.npz")))
            db = dict(np.load(os.path.join("gate6/signatures", f"{sb}.npz")))
            figs = []
            for d, s in ((da, sa), (db, sb)):
                w0 = d["W0"]
                dw = {k: d[k] - w0 for k in BLOCKS}
                figs.append((s, dw))
            allv = np.concatenate([np.concatenate(list(dw.values())) for _, dw in figs])
            lim = float(np.abs(allv).max()) * 1.1
            fig, axes = plt.subplots(1, 2, figsize=(11, 5))
            for ax, (s, dw) in zip(axes, figs):
                ax.plot([-lim, lim], [0, 0], ':', color='grey', lw=.5)
                ax.plot([0, 0], [-lim, lim], ':', color='grey', lw=.5)
                for k in BLOCKS:
                    v = dw[k]  # (8,2)
                    ax.plot(v[:, 0], v[:, 1], '-o', color=COLOR[k], ms=3,
                            label=f"{LABEL[k]} ({k})")
                ax.set_title(s)
                ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
                ax.set_xlabel("dx (m)"); ax.set_ylabel("dy (m)")
                ax.set_aspect("equal"); ax.grid(alpha=.3)
                ax.legend(fontsize=6, loc="best")
            fig.suptitle(f"{combo} cos_dir={c['cos_dir']}")
            fig.tight_layout()
            p = os.path.join(outdir, f"dw_{sa}_{sb}.png")
            fig.savefig(p, dpi=130)
            plt.close(fig)
            made.append((combo, sa, sb, c["cos_dir"], p))
    with open("gate6/figure_manifest_dw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["combo", "state_A", "state_B", "cos_dir", "file"])
        w.writerows(made)
    print("wrote", len(made), "dW figures")


if __name__ == "__main__":
    main()
