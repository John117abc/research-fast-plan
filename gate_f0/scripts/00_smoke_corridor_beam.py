"""Gate F0-0: offline corridor/beam smoke (synthetic straight corridor).

Checks: (1) no obstacle -> P0(H) grows monotonically; (2) static barrier ahead
-> P0(H) saturates at the barrier.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feasible.beam_search import beam_forward, max_progress  # noqa: E402

DT = 0.5
ACCEL = (-4.0, -2.0, 0.0, 1.5)
V_MAX = 12.0
HORIZONS = [2, 4, 6, 8]


def steps(h):
    return int(h / DT)


def run(v0, barrier=None):
    if barrier is None:
        def feasible(_s):
            return True
    else:
        def feasible(s):
            return s.s <= barrier
    layers = beam_forward(0.0, v0, ACCEL, DT, steps(8), feasible,
                          V_MAX, width=100)
    P = max_progress(layers, [steps(h) for h in HORIZONS])
    return P


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "results", "smoke")
    os.makedirs(out, exist_ok=True)

    P_free = run(v0=8.0, barrier=None)
    P_bar = run(v0=8.0, barrier=55.0)
    print("P_free(2,4,6,8) =", [round(p, 2) for p in P_free])
    print("P_bar (55)      =", [round(p, 2) for p in P_bar])

    ok1 = all(P_free[i + 1] > P_free[i] for i in range(3)) and P_free[-1] > 20
    g0_bar = (P_bar[-1] - P_bar[-2]) / 2.0
    ok2 = abs(P_bar[-1] - 55.0) < 3.0 and g0_bar < 0.2
    print(f"[free monotonic] ok={ok1}  P8-P6={(P_free[-1]-P_free[-2]):.2f}")
    print(f"[barrier sat]    ok={ok2}  P8~{P_bar[-1]:.2f}  G0(6-8)={(P_bar[-1]-P_bar[-2])/2:.3f} <= 0.2")
    if not (ok1 and ok2):
        raise SystemExit("F0-0 smoke FAILED")
    print("F0-0 smoke PASS")


if __name__ == "__main__":
    main()
