#!/usr/bin/env python3
"""Gate F1 offline per-sample metrics: three FROZEN engine runs per recording.

  1. P0 current corridor      (occupancy = recorded dynamic actors)
  2. PL left-change           (same occupancy, from the same single search)
  3. Pfree baseline           (occupancy removed; road/ego state unchanged)

Output dict (saved as results/<scene>/run<g>.summary.json):
  scene/group/v0/s0/P0_2..P0_10/PL_2..PL_10/Pfree_2..Pfree_10/G0/GL/quadrant/
  n_branches/fine series P0/PL/Pfree at 0.5 s step + normalized P^0/P^L.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))

from feasible.engine import StraightCorridor, OccupancyGT, compute_frontiers  # noqa: E402
import geo  # noqa: E402

DT = 0.5
HMAX = 10.0
N = int(HMAX / DT)
ACCEL = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
MARGIN = 0.5
T_LC = 3.0
FINE = [0.5 * (k + 1) for k in range(N)]
FINE_STEPS = [int(h / DT) for h in FINE]
H_SEL = (2, 4, 6, 8, 10)
EPS = 0.10

EXPECTED = {"A1": "G0>0", "A2": "G0>0", "B1": "GL>0", "B2": "GL>0",
            "C1": "both>0", "C2": "both>0", "D1": "both~0", "D2": "both~0",
            "G1": "GL>0", "G2": "both~0", "G3": "G0>0"}


def load(path):
    rows = [json.loads(l) for l in open(path)]
    rows.sort(key=lambda r: r["sim_t"])
    return rows


def classify(g0, gl):
    a0 = g0 > EPS
    al = (gl is not None and gl > EPS)
    if a0 and not al:
        return "LongitudinalSufficient"
    if not a0 and al:
        return "LateralNecessary"
    if a0 and al:
        return "LateralOptional"
    return "Contingency/Wait"


def check(expected, g0, gl):
    if expected == "G0>0":
        return g0 > EPS
    if expected == "GL>0":
        return gl is not None and gl > EPS and g0 <= EPS
    if expected == "both>0":
        return g0 > EPS and gl is not None and gl > EPS
    if expected == "both~0":
        return g0 <= EPS and (gl is None or gl <= EPS)
    return False


def compute(path, seg="gate_f0/road_segment.json"):
    rows = load(path)
    if len(rows) < 3:
        return None
    meta = rows[0]["scenario"] if isinstance(rows[0].get("scenario"), dict) else {}
    scene = meta.get("scene") or (meta.get("case") or "")
    group = meta.get("group")
    v0 = rows[0].get("v0") or meta.get("v0") or max(rows[0]["ego"]["speed_mps"], 0.5)
    s0 = rows[0].get("ego_s", 0.0)
    geo.load_seg(seg)
    lane_w = geo.lane_width()

    def pick(t):
        best = min(rows, key=lambda r: abs(r["sim_t"] - t))
        return best if abs(best["sim_t"] - t) < 0.3 else None

    def actors_at(t):
        r = pick(t)
        if r is None:
            return []
        out = []
        for a in r["actors"]:
            tx, ty = a["transform"]["x"], a["transform"]["y"]
            sx, ly = geo.local(tx, ty)
            if abs(ly) > lane_w + 4.0:
                continue
            e = a["bbox"]["extent"]
            out.append((sx, ly, max(float(e[0]), 1.0), max(float(e[1]), 0.3)))
        return out

    # occupancy over [0,10] sampled at 0.5 s
    slots = [actors_at(t0rel) for t0rel in np.arange(0, HMAX + 1e-6, DT)]

    # exact per-actor occupancy (one actor object per frame-slot actor)
    # NOTE: recorded 'cl' lane is physically at lat=-W on this segment; engine
    # models the alternative at lat=+W, so mirror occupancy lat into engine frame.
    def occ_exact(slots_):
        occ = OccupancyGT(N, DT)
        for i, acts in enumerate(slots_):
            if not acts:
                occ.add_actor(np.full(N + 1, -1.0), np.full(N + 1, 30.0), 1.0, 1.0)
                continue
            for (sx, ly, hl, hw) in acts:
                s_arr = np.full(N + 1, -1.0)
                lat_arr = np.full(N + 1, 30.0)
                s_arr[i] = sx - s0
                lat_arr[i] = -ly
                occ.add_actor(s_arr, lat_arr, hl, hw)
        return occ

    free_slots = [[] for _ in range(N + 1)]
    cor = StraightCorridor(200.0, lane_w)

    def run(slots_):
        occ = occ_exact(slots_)
        P0, PL, st = compute_frontiers(cor, occ, s0=0.0, v0=v0, accel_set=ACCEL,
                                       dt=DT, v_max=VMAX, n_steps=N,
                                       horizons_steps=FINE_STEPS, width=100,
                                       keep_per_bucket=20, margin=MARGIN,
                                       T_LC=T_LC, return_stats=True)
        return P0, PL, st

    P0, PL, st = run(slots)
    Pf0, PfL, stf = run(free_slots)
    Pf = Pf0  # baseline current-corridor frontier (no actors)

    def H(h):
        return int(h / DT) - 1
    G0 = (P0[H(10)] - P0[H(8)]) / 2.0 if (P0[H(10)] >= 0 and P0[H(8)] >= 0) else 0.0
    GL = ((PL[H(10)] - PL[H(8)]) / 2.0
          if (PL[H(10)] >= 0 and PL[H(8)] >= 0) else None)
    n0 = st["n0"][-1]
    out = {"scene": scene, "group": group, "v0": round(v0, 3), "s0": round(s0, 2),
           "quadrant": classify(G0, GL), "expected": EXPECTED.get(scene),
           "pass": check(EXPECTED.get(scene), G0, GL),
           "G0": round(G0, 3), "GL": round(GL, 3) if GL is not None else None,
           "P0": {f"P0_{h}": round(P0[H(h)], 2) for h in H_SEL},
           "PL": {f"PL_{h}": round(PL[H(h)], 2) for h in H_SEL},
           "Pfree": {f"Pfree_{h}": round(Pf[H(h)], 2) for h in H_SEL},
           "n_branches": n0,
           "fine": {"t": FINE,
                    "P0": [round(float(x), 2) for x in P0],
                    "PL": [round(float(x), 2) if x >= 0 else None for x in PL],
                    "Pfree": [round(float(x), 2) for x in Pf]}}
    return out


if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "gate_f1/results/B1/run5.ndjson"
    r = compute(f)
    print(json.dumps(r, indent=1) if r else "too short")
