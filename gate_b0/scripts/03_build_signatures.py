#!/usr/bin/env python3
"""Gate B0-3: build R0 signatures for all Dev-108 states + successor signatures.

usage: python gate_b0/scripts/03_build_signatures.py
writes:
  results/discovery/signatures.csv
  results/discovery/action_consequence_long.csv
  results/discovery/successors.json
  results/discovery/signature_health.json
"""
import csv
import json
import os
import sys

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from consequence import action_consequence as ac  # noqa: E402
from consequence import successor_state as ss  # noqa: E402
from consequence.relation_signature import signature_row  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/discovery")


def main():
    os.makedirs(OUT, exist_ok=True)
    states = common.list_states()
    sig_rows, long_rows, successors = [], [], {}
    n_anom = n_qfree_bad = n_nan = 0
    for st in states:
        slots = common.build_slots(st["path"])
        win = slots[: cr.N + 1]
        sig = ac.compute_signature(st["ego_speed"], 0, 0.0, win, st["ego_s"])
        if not sig["qfree_ok"]:
            n_qfree_bad += 1
        if sig["v_anomaly"]:
            n_anom += 1
        sig_rows.append(signature_row(st, sig))
        successors[st["state_id"]] = {}
        for aid in ACTION_IDS:
            e = sig["actions"][aid]
            if e["V_raw"] is None and e["M"] == 1:
                n_nan += 1
            long_rows.append({
                "state_id": st["state_id"], "coarse_mechanism": st["coarse_mechanism"],
                "fine_mechanism": st["fine_mechanism"], "param_group_id": st["param_group_id"],
                "action_id": aid, "lateral": "left" if aid in ("U4", "U5", "U6", "U7") else "keep",
                "first_1s_feasible": e["valid"], "M": e["M"], "Q": e["Q"],
                "Q_free": e["Qfree"], "V_raw": e["V_raw"], "V_clipped": e["V"],
                "successor_s": e["successor"][0] if e["successor"] else "",
                "successor_v": e["successor"][1] if e["successor"] else "",
                "successor_mode": e["successor"][2] if e["successor"] else "",
                "lane_change_elapsed": e["successor"][3] if e["successor"] else "",
            })
            s_sig = ss.successor_signature(e, slots, st["ego_s"], occupancy=True)
            if s_sig is None:
                successors[st["state_id"]][aid] = {"successor_valid": False,
                                                   "M": None, "V": None}
            else:
                successors[st["state_id"]][aid] = {"successor_valid": True,
                                                   "M": s_sig["M"], "V": s_sig["V"]}
        print("done", st["state_id"])
    with open(os.path.join(OUT, "signatures.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sig_rows[0].keys()))
        w.writeheader()
        w.writerows(sig_rows)
    with open(os.path.join(OUT, "action_consequence_long.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(long_rows[0].keys()))
        w.writeheader()
        w.writerows(long_rows)
    json.dump(successors, open(os.path.join(OUT, "successors.json"), "w"))
    health = {"n_states": len(states), "n_qfree_bad": n_qfree_bad,
              "n_v_anomaly": n_anom, "n_nan": n_nan,
              "g0_ok": (n_qfree_bad == 0 and n_anom == 0 and n_nan == 0)}
    json.dump(health, open(os.path.join(OUT, "signature_health.json"), "w"), indent=1)
    print("HEALTH", health)


if __name__ == "__main__":
    main()
