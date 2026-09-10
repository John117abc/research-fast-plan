#!/usr/bin/env python3
"""Gate B0-2: single-state action probe smoke (4 states x 8 actions).

usage: python gate_b0/scripts/02_smoke_action_probe.py
Engineering check only; not a scientific verdict.
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
from consequence import action_consequence as ac  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

SMOKE = [("block_nec", 1), ("lead_nec", 1), ("cross_stall", 1), ("lead_opt", 1)]
MODE_NAME = {0: "KEEP", 1: "CHANGING_LEFT", 2: "LEFT"}


def main():
    states = {(s["cell"], s["row"]): s for s in common.list_states()}
    rows = []
    print("%-16s %-4s %-8s %-5s %6s %6s %8s %7s %7s %s" %
          ("state", "act", "lat", "M", "succ_s", "succ_v", "Q", "Qfree", "V_raw", "mode"))
    for key in SMOKE:
        st = states[key]
        slots = common.build_slots(st["path"])
        sig = ac.compute_signature(st["ego_speed"], 0, 0.0, slots[:cr.N + 1], st["ego_s"])
        for aid in ACTION_IDS:
            e = sig["actions"][aid]
            succ = e["successor"]
            mode = MODE_NAME.get(succ[2]) if succ else "-"
            print("%-16s %-4s %-8s %-5d %6s %6s %8.2f %7.2f %7s %s" % (
                st["state_id"], aid,
                "left" if aid in ("U4", "U5", "U6", "U7") else "keep",
                e["M"], ("%.2f" % succ[0]) if succ else "-",
                ("%.2f" % succ[1]) if succ else "-",
                e["Q"], e["Qfree"],
                ("%.3f" % e["V_raw"]) if e["V_raw"] is not None else "-", mode))
            rows.append({"state_id": st["state_id"], "action_id": aid,
                         "ax": None, "lateral_mode": "left" if aid in ("U4", "U5", "U6", "U7") else "keep",
                         "first_1s_feasible": e["valid"],
                         "successor_s": succ[0] if succ else "",
                         "successor_v": succ[1] if succ else "",
                         "successor_mode": mode, "lane_change_elapsed": succ[3] if succ else "",
                         "Q": e["Q"], "Q_free": e["Qfree"], "V_raw": e["V_raw"],
                         "V_clipped": e["V"]})
        print("-" * 100)
    # hard engineering assertions
    ok = True
    for key in SMOKE:
        st = states[key]
        slots = common.build_slots(st["path"])
        sig = ac.compute_signature(st["ego_speed"], 0, 0.0, slots[:cr.N + 1], st["ego_s"])
        for aid in ("U4", "U5", "U6", "U7"):
            succ = sig["actions"][aid]["successor"]
            if succ is None or succ[2] != 1 or abs(succ[3] - 1.0) > 1e-6:
                print("ASSERT FAIL: START_LEFT successor must be CHANGING tau=1.0", st["state_id"], aid, succ)
                ok = False
    out = os.path.join(B0, "results/discovery/smoke_action_probe.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("SMOKE", "PASS" if ok else "FAIL", "->", out)


if __name__ == "__main__":
    main()
