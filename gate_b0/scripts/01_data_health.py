#!/usr/bin/env python3
"""Gate B0-1: Dev-108 data health + index table.

usage: python gate_b0/scripts/01_data_health.py
writes gate_b0/results/discovery/data_health.{json,csv}
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

CFG = common.cfg()
DT = CFG["data"]["dt"]
H = CFG["data"]["horizon_s"]
REC = CFG["data"]["record_s"]


def main():
    states = common.list_states()
    checks, index = [], []
    n_bad = 0
    for st in states:
        rows = common.load_rows(st["path"])
        ts = [r["sim_t"] for r in rows]
        mono = all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1))
        sim_max = max(ts) if ts else -1.0
        grid_ok = all(any(abs(t - k * DT) < 0.3 for t in ts)
                      for k in range(0, int(REC / DT) + 1))
        actors_seen = set()
        for r in rows:
            for a in r["actors"]:
                actors_seen.add(a["actor_id"])
        tracked = all(a in actors_seen for a in st["target_actor_ids"])
        bbox_ok = all("bbox" in r["ego"] and r["ego"]["bbox"].get("extent")
                      for r in rows[:3]) and all(
            "bbox" in a for r in rows[:3] for a in r["actors"])
        ok = (mono and sim_max >= H - 1e-6 and grid_ok and tracked and bbox_ok
              and st["ego_lane_id"] is not None)
        if not ok:
            n_bad += 1
        checks.append({"state_id": st["state_id"], "n_rows": len(rows),
                       "sim_t_max": round(sim_max, 3), "monotone": mono,
                       "grid_0p5_ok": grid_ok, "actors_tracked": tracked,
                       "bbox_ok": bbox_ok, "ok": ok})
        index.append({
            "state_id": st["state_id"], "run_id": st["run_id"], "case_id": st["case_id"],
            "fine_mechanism": st["fine_mechanism"], "coarse_mechanism": st["coarse_mechanism"],
            "param_group_id": st["param_group_id"], "ego_speed": st["ego_speed"],
            "ego_s": round(st["ego_s"], 3), "ego_lane_id": st["ego_lane_id"],
            "target_actor_ids": ";".join(str(x) for x in st["target_actor_ids"]),
            "decision_frame": st["decision_frame"], "n_rows": len(rows),
            "sim_t_max": round(sim_max, 3), "ok": ok,
        })
    os.makedirs(os.path.join(B0, "results/discovery"), exist_ok=True)
    with open(os.path.join(B0, "results/discovery/data_health.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(index[0].keys()))
        w.writeheader()
        w.writerows(index)
    report = {"n_states": len(states), "n_bad": n_bad,
              "all_ok": n_bad == 0, "checks": checks}
    json.dump(report, open(os.path.join(B0, "results/discovery/data_health.json"), "w"), indent=1)
    print("states=%d bad=%d all_ok=%s" % (len(states), n_bad, n_bad == 0))
    for c in checks:
        if not c["ok"]:
            print("  BAD", c)
    print("wrote data_health.json + data_health.csv")


if __name__ == "__main__":
    main()
