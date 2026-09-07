#!/usr/bin/env python3
"""Gate6 16: manual trajectory sanity figures for primary cross-scene pairs.

For each of the 6 group-pair combos, pick up to 2 cross-route pairs (different
routes/instances) with highest cos_dir from the 68 primary candidates; plot
W0 (black) and I1..I5 pred_wps trajectories to gate6/figures/.
"""
import csv
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABEL = {"I1": "+2m", "I2": "-2m", "I3": "spd*1.2", "I4": "spd*0.8", "I5": "remove"}
COLOR = {"I1": "#d62728", "I2": "#1f77b4", "I3": "#2ca02c", "I4": "#ff7f0e", "I5": "#9467bd"}


def plot_pair(state_a, state_b, outdir):
    da = dict(np.load(os.path.join("gate6/signatures", f"{state_a}.npz")))
    db = dict(np.load(os.path.join("gate6/signatures", f"{state_b}.npz")))
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, s, d, title in ((axes[0], state_a, da, "state A"), (axes[1], state_b, db, "state B")):
        w0 = d["W0"]
        ax.plot(w0[:, 0], w0[:, 1], "-o", color="k", lw=2, label="W0")
        for k in ("I1", "I2", "I3", "I4", "I5"):
            w = d[k]
            ax.plot(w[:, 0], w[:, 1], "--o", color=COLOR[k], lw=1.2, ms=3,
                    label=f"{LABEL[k]} ({k})")
        ax.set_title(title + f" {s}")
        ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
        ax.legend(fontsize=7, loc="best")
        ax.grid(alpha=.3)
    fig.tight_layout()
    out = os.path.join(outdir, f"pair_{state_a}_{state_b}.png")
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main():
    cand = list(csv.DictReader(open("gate6/pair_cross_primary_confounds.csv")))
    by_combo = defaultdict(list)
    for c in cand:
        combo = tuple(sorted((c["group_A"], c["group_B"])))
        by_combo[combo].append(c)
    outdir = "gate6/figures"
    os.makedirs(outdir, exist_ok=True)
    made = []
    for combo in sorted(by_combo):
        cs = by_combo[combo]
        # prefer cross-route & distinct instances
        picks = 0
        for c in sorted(cs, key=lambda x: -float(x["cos_dir"])):
            if c["same_route"] == "1":
                continue
            if picks >= 2:
                break
            out = plot_pair(c["state_A"], c["state_B"], outdir)
            made.append((combo, c["state_A"], c["state_B"], round(float(c["cos_dir"]), 3), out))
            picks += 1
    with open("gate6/figure_manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["combo", "state_A", "state_B", "cos_dir", "file"])
        w.writerows(made)
    print(f"wrote {len(made)} figures")
    for m in made:
        print("  ", m[0], m[1], m[2], "cos", m[3], m[4])


if __name__ == "__main__":
    main()
