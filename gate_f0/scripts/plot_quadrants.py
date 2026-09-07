import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pts = []
for r in csv.DictReader(open("gate_f0/results/synthetic_C_D_summary.csv")):
    g0 = float(r["G0"])
    gl = None if r["GL"] == "" else float(r["GL"])
    pts.append((r["archetype"], g0, gl))

fig, ax = plt.subplots(figsize=(6, 6))
# quadrant annotations
ax.axhline(0, color="k", lw=.8)
ax.axvline(0, color="k", lw=.8)
for g0, gl, label in pts:
    gy = 0.5 if gl is None else gl
    ax.scatter([g0], [gy], s=90)
    ax.annotate(label, (g0, gy), textcoords="offset points", xytext=(6, 6), fontsize=8)
ax.set_xlabel("G0 (current corridor terminal growth m/s)")
ax.set_ylabel("GL (left corridor terminal growth m/s)")
ax.axvspan(0, 0, color='none')
ax.grid(alpha=.3)
os.makedirs("gate_f0/figures", exist_ok=True)
fig.savefig("gate_f0/figures/f0_quadrants.png", dpi=140)
print("saved f0_quadrants.png")
