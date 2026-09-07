"""Gate F0-1: offline engine validation on synthetic straight two-lane corridor.

A temporary closure -> expect G0 > eps (P0 resumes after the window clears).
B static blocker + free left -> expect G0 <= eps and GL > eps.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from feasible.engine import (StraightCorridor, OccupancyGT, static_series,
                             compute_frontiers)  # noqa: E402

DT = 0.5
ACCEL = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
N = 16
HOR = [2, 4, 6, 8]
HSTEPS = [int(x / DT) for x in HOR]
MARGIN = 0.5
W = 3.5


def series_active(t0_idx, t1_idx, s, lat_active, lat_inactive=30.0):
    s_series = np.full(N + 1, float(s))
    lat = np.array([lat_active if t0_idx <= i <= t1_idx else lat_inactive
                    for i in range(N + 1)], dtype=float)
    return s_series, lat


def run_case(name, occ):
    cor = StraightCorridor(200.0, W)
    P0, PL = compute_frontiers(cor, occ, s0=0.0, v0=8.0, accel_set=ACCEL,
                               dt=DT, v_max=VMAX, n_steps=N,
                               horizons_steps=HSTEPS, width=100,
                               keep_per_bucket=20, margin=MARGIN, T_LC=3.0)
    G0 = (P0[-1] - P0[-2]) / 2.0
    GL = (PL[-1] - PL[-2]) / 2.0 if PL[-1] >= 0 else None
    print(f"[{name}]")
    print("   P0=", [round(x, 2) for x in P0], " G0=", round(G0, 3))
    print("   PL=", [round(x, 2) for x in PL], " GL=", round(GL, 3) if GL is not None else None)
    return P0, PL, G0, GL


def main():
    # A: temporary closure on C0 lane around s=42, active t in [3.0, 5.5] s (steps 6..11)
    occA = OccupancyGT(N, DT)
    sA, latA = series_active(6, 11, 42.0, 0.0)
    occA.add_actor(sA, latA, 0.4, 0.4)

    # B: static blocker on C0 at s=55 forever
    occB = OccupancyGT(N, DT)
    occB.add_actor(*static_series(48.0, 0.0, N), 2.0, 1.0)

    P0a, PLa, G0a, GLa = run_case("A temp", occA)
    P0b, PLb, G0b, GLb = run_case("B static+freeLeft", occB)

    eps = 0.10
    okA = G0a > eps
    okB = (G0b <= eps) and (GLb is not None and GLb > eps) and (PLb[-1] > P0b[-1] + 3)
    print(f"\nA expect G0>eps: G0={G0a:.3f} -> {okA}")
    print(f"B expect G0<=eps & GL>eps: G0={G0b:.3f} GL={GLb} PL8={PLb[-1]:.1f} P08={P0b[-1]:.1f} -> {okB}")
    if okA and okB:
        print("F0-1 engine smoke PASS")
    else:
        raise SystemExit("F0-1 engine smoke FAILED")


if __name__ == "__main__":
    main()
