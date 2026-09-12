#!/usr/bin/env python3
"""B1-0 Step 6: full R1^8s on 10 real Waymo states (plant2, frozen engine).

For states with an official left neighbor: build corridor-local occupancy from
canonical, normalize each action/branch progress by the free baseline (remove
interaction actors only), and compute R1^8s (8 actions x 2 branches x 16 t).
No successor (B1 needs only R1; B2 does successors in CARLA).

usage: python gate_b1/scripts/26_waymo_r1_smoke.py --n 10 --seed 0
"""
import argparse
import csv
import glob
import json
import os
import random
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
B0 = os.path.join(ROOT, "gate_b0")
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, B1)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402
from adapters import waymo_adapter as wa  # noqa: E402

OUT = os.path.join(B1, "results/b1_0/step6_r1")
N8 = 16


def cols8():
    return ["%s_%s_t%d" % (b, u, k) for u in ACTION_IDS for b in ("V0", "VL")
            for k in range(1, N8 + 1)]


COLS8 = cols8()


def _ratio(p, pf):
    if p is None or pf is None or p <= 0 or pf <= 0:
        return 0.0
    return min(max(p / pf, 0.0), 1.0)


def compute_r1_8s(v0, lane_w, slots_all, slots_free):
    cor = StraightCorridor(cr.COR_LEN, lane_w)
    occ = cr.build_occ(slots_all, 0.0, n_steps=N8)
    occf = cr.build_occ(slots_free, 0.0, n_steps=N8)
    out = {}
    for a in ACTIONS:
        r = cr.run_probe_curves((0.0, v0, 0, 0.0), a["ax"], a["lateral"], occ, cor, n_steps=N8)
        rf = cr.run_probe_curves((0.0, v0, 0, 0.0), a["ax"], a["lateral"], occf, cor, n_steps=N8)
        for k in range(N8):
            out["V0_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["p0"][k], rf["p0"][k]), 4)
            out["VL_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["pL"][k], rf["pL"][k]), 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(os.path.join(OUT, "figures"), exist_ok=True)
    cand = []
    for path in sorted(glob.glob(os.path.join(B1, "canonical", "*.json"))):
        c = wa.load_canonical(path)
        ego = wa.ego_state(c)
        cur = wa.find_current_lane_official(ego, c["lanes"])
        if cur is None:
            continue
        nb, _ = wa.official_left_neighbor(ego, cur["lane"], cur["i_sdc"], c["lanes"])
        if nb is None:
            continue
        cand.append((c, ego, nb))
    random.Random(a.seed).shuffle(cand)
    cand = cand[: a.n]
    rows = []
    curves = {}
    for c, ego, nb in cand:
        W = nb["lateral"]
        inter = wa.interaction_actor_ids(c, ego, W)
        slots = wa.build_slots(c, ego)
        free = wa.build_slots(c, ego, exclude_ids=list(inter.keys()))
        sig = compute_r1_8s(ego["speed"], W, slots, free)
        arr = np.array([sig[k] for k in COLS8])
        rows.append({"scenario_id": c["scenario_id"], "lane_width": round(W, 3),
                     "ego_speed": round(ego["speed"], 2), "n_interaction": len(inter),
                     "V_min": round(float(arr.min()), 4), "V_max": round(float(arr.max()), 4),
                     "V_mean": round(float(arr.mean()), 4),
                     **sig})
        curves[c["scenario_id"]] = arr.tolist()
        print(c["scenario_id"], "W", round(W, 2), "v", round(ego["speed"], 2),
              "Vmean", round(float(arr.mean()), 3), "Vmax", round(float(arr.max()), 3))
    with open(os.path.join(OUT, "r1_8s_waymo_smoke.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(curves, open(os.path.join(OUT, "r1_8s_curves.json"), "w"))
    summ = {"n_states": len(rows),
            "all_V_in_0_1": bool(all(0.0 <= r["V_min"] and r["V_max"] <= 1.0 for r in rows)),
            "mean_V_mean": round(float(np.mean([r["V_mean"] for r in rows])), 4)}
    json.dump(summ, open(os.path.join(OUT, "r1_smoke_summary.json"), "w"), indent=1)
    _fig(curves)
    print(json.dumps(summ, indent=1))


def _fig(curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.arange(1, N8 + 1) * 0.5
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for sid, arr in curves.items():
        A = np.array(arr)
        for u in ("U2", "U6"):
            c0 = [COLS8.index("V0_%s_t%d" % (u, k)) for k in range(1, N8 + 1)]
            cL = [COLS8.index("VL_%s_t%d" % (u, k)) for k in range(1, N8 + 1)]
            axes[0].plot(t, A[c0], alpha=0.6)
            axes[1].plot(t, A[cL], alpha=0.6)
    axes[0].set_title("Waymo R1^8s current corridor V0 (U2,U6)")
    axes[1].set_title("Waymo R1^8s left corridor VL (U2,U6)")
    for ax in axes:
        ax.set_xlabel("t (s)"); ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
    fig.savefig(os.path.join(OUT, "figures", "waymo_r1_8s_curves.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
