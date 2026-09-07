#!/usr/bin/env python3
"""F2 visualization: PCA of the frontier space colored by structure vs scene."""
import json
import os

import numpy as np

os.makedirs("gate_f2/results", exist_ok=True)
os.makedirs("gate_f2/figures", exist_ok=True)

Z = np.load("gate_f2/results/Z.npy")
pts = json.load(open("gate_f2/results/points.json"))
mu = Z.mean(0)
Zc = Z - mu
U, S, Vt = np.linalg.svd(Zc, full_matrices=False)
PC = Zc @ Vt[:2].T

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

STRUCTS = ["LateralOptional", "LateralNecessary", "Contingency/Wait", "LongitudinalSufficient"]
SCOL = {"LateralOptional": "#2a7", "LateralNecessary": "#fb5",
        "Contingency/Wait": "#c33"}
SCEN = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "G1", "G2", "G3"]
CCOL = {"A1": "#e00", "A2": "#f88", "B1": "#2a7", "B2": "#7cc",
        "C1": "#08c", "C2": "#8cf", "D1": "#a5a", "D2": "#c5c",
        "G1": "#54a", "G2": "#c96", "G3": "#387"}

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
for ax, key, col, lbl in ((axes[0], "struct", SCOL, "structure"),
                          (axes[1], "scene", CCOL, "physical scene")):
    for val in dict.fromkeys(p[key] for p in pts):
        idx = [k for k, p in enumerate(pts) if p[key] == val]
        ax.scatter(PC[idx, 0], PC[idx, 1], s=34, alpha=.8, c=col[val],
                   label=val if key == "struct" else val)
    ax.set_title("Z_F colored by " + lbl)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=.3)
fig.tight_layout()
fig.savefig("gate_f2/figures/f2_PCA_struct_vs_scene.png", dpi=140)
print("PCA fig saved")
