#!/usr/bin/env python3
"""Gate B0-R2 step 1: successor R1 for every (state, action).

usage: python gate_b0/scripts/11_build_r1_successors.py
writes gate_b0/results/r2/r1_successors.json
"""
import json
import os
import sys

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from consequence import r1_signature as r1  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402

OUT = os.path.join(B0, "results/r2")


def main():
    os.makedirs(OUT, exist_ok=True)
    states = common.list_states()
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    successors = {}
    for st in states:
        slots = common.build_slots(st["path"])
        occ = cr.build_occ(slots[: cr.N + 1], st["ego_s"])
        successors[st["state_id"]] = {}
        for a in ACTIONS:
            pr = cr.run_probe((0.0, st["ego_speed"], 0, 0.0), a["ax"],
                              a["lateral"], occ, cor)
            entry = {"successor": pr["successor"]}
            sr1 = r1.successor_r1(entry, slots, st["ego_s"]) if pr["valid"] else None
            if sr1 is None:
                successors[st["state_id"]][a["id"]] = {"valid": False, "r1": None,
                                                       "successor": None}
            else:
                successors[st["state_id"]][a["id"]] = {
                    "valid": True, "successor": [round(x, 4) for x in pr["successor"]],
                    "r1": sr1}
        print("done", st["state_id"])
    json.dump(successors, open(os.path.join(OUT, "r1_successors.json"), "w"))
    print("wrote r1_successors.json")


if __name__ == "__main__":
    main()
