#!/usr/bin/env python3
"""Gate B0-R1: build action-conditioned branch-evolution signatures.

R1(X) = { V0^u(t), VL^u(t) }_{u in U, t=0.5..10s}, V normalized by the matched
free baseline (same action, no actors). Replaces R0's scalar max-progress.

usage: python gate_b0/scripts/09_build_r1.py
writes results/discovery/r1_signatures.csv
"""
import csv
import os
import sys

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402

OUT = os.path.join(B0, "results/discovery")


def curve_cols():
    cols = []
    for u in ACTION_IDS:
        for b in ("V0", "VL"):
            for k in range(1, cr.N + 1):
                cols.append("%s_%s_t%d" % (b, u, k))
    return cols


COLS = curve_cols()


def ratio(p, pf):
    if p is None or pf is None or p <= 0 or pf <= 0:
        return 0.0
    return min(max(p / pf, 0.0), 1.0)


def main():
    states = common.list_states()
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    rows = []
    for st in states:
        slots = common.build_slots(st["path"])
        win = slots[: cr.N + 1]
        occ = cr.build_occ(win, st["ego_s"])
        empty = cr.empty_occ()
        row = {"state_id": st["state_id"], "coarse_mechanism": st["coarse_mechanism"],
               "fine_mechanism": st["fine_mechanism"],
               "param_group_id": st["param_group_id"], "ego_speed": st["ego_speed"]}
        for a in ACTIONS:
            r = cr.run_probe_curves((0.0, st["ego_speed"], 0, 0.0), a["ax"],
                                    a["lateral"], occ, cor)
            rf = cr.run_probe_curves((0.0, st["ego_speed"], 0, 0.0), a["ax"],
                                     a["lateral"], empty, cor)
            for k in range(cr.N):
                row["V0_%s_t%d" % (a["id"], k + 1)] = round(ratio(r["p0"][k], rf["p0"][k]), 4)
                row["VL_%s_t%d" % (a["id"], k + 1)] = round(ratio(r["pL"][k], rf["pL"][k]), 4)
        rows.append(row)
        print("done", st["state_id"])
    keys = list(rows[0].keys())
    with open(os.path.join(OUT, "r1_signatures.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("wrote r1_signatures.csv (%d states x %d value cols)" %
          (len(rows), len(COLS)))


if __name__ == "__main__":
    main()
