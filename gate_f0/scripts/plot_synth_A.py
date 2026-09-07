import os
import sys

sys.path.insert(0, "gate_f0/scripts")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from synthetic_temporary_barrier import run, FINE

fig, ax = plt.subplots(figsize=(7, 4))
for lbl, kw in (("closure s_c=20 dur4", dict(s_c=20, Ts=1.0, Te=5.0, v0=6.0)),
                ("free s_c=40 dur2", dict(s_c=40, Ts=1.0, Te=3.0, v0=6.0))):
    r = run(**kw)
    ax.plot(FINE, r["P0"], "-o", ms=3, label=lbl)
ax.set_xlabel("t (s)")
ax.set_ylabel("P0(t) (m)")
ax.legend()
ax.grid(alpha=0.3)
ax.set_title("Synthetic TemporaryBarrier: P0 frontier")
os.makedirs("gate_f0/figures", exist_ok=True)
fig.savefig("gate_f0/figures/synthetic_A_P0.png", dpi=140)
print("saved figure")
