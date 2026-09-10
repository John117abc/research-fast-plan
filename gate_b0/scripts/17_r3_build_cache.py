#!/usr/bin/env python3
"""Gate B0-R3 step 1: data health + successor R1 cache.

Reuses the R2 successor R1 (already computed once for all 108 x 8). Writes the
required cache under results/r3/ (and results/r3/cache/).

usage: python gate_b0/scripts/17_r3_build_cache.py
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
from consequence.r1_signature import COLS  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/r3")
CACHE = os.path.join(OUT, "cache")


def main():
    os.makedirs(CACHE, exist_ok=True)
    states = common.list_states()
    succ = json.load(open(os.path.join(B0, "results/r2/r1_successors.json")))

    health = {"n_states": len(states), "need_t0_plus_s": 11.0, "bad": []}
    for st in states:
        rows = common.load_rows(st["path"])
        tmax = max(r["sim_t"] for r in rows)
        ids = set(st["target_actor_ids"])
        rec = {"state_id": st["state_id"], "sim_t_max": round(tmax, 3),
               "covers_11s": tmax >= 11.0 - 1e-6, "actors_present": True}
        if not rec["covers_11s"]:
            health["bad"].append(st["state_id"])
        for k in range(2, 23):
            t = k * 0.5
            r = min(rows, key=lambda x: abs(x["sim_t"] - t))
            if abs(r["sim_t"] - t) > 0.3 or not ids <= {a["actor_id"] for a in r["actors"]}:
                rec["actors_present"] = False
                health["bad"].append(st["state_id"])
                break
        health.setdefault("checks", []).append(rec)
    health["all_ok"] = len(health["bad"]) == 0
    json.dump(health, open(os.path.join(OUT, "data_health.json"), "w"), indent=1)
    if not health["all_ok"]:
        print("HEALTH FAIL", health["bad"][:10])
        return

    idx_rows, sig_rows = [], []
    for st in states:
        sid = st["state_id"]
        for a in ACTION_IDS:
            e = succ[sid][a]
            s = e.get("successor") or [None, None, None, None]
            idx_rows.append({"state_id": sid, "probe_action": a,
                             "successor_valid": int(e["valid"]),
                             "successor_s": s[0], "successor_v": s[1],
                             "successor_mode": s[2], "lane_change_elapsed": s[3]})
            row = {"state_id": sid, "probe_action": a, "successor_valid": int(e["valid"])}
            if e["valid"]:
                row.update(e["r1"])
            sig_rows.append(row)
    _write(os.path.join(OUT, "successor_index.csv"), idx_rows)
    _write(os.path.join(CACHE, "successor_index.csv"), idx_rows)
    _write(os.path.join(OUT, "successor_r1_signatures.csv"), sig_rows)
    _write(os.path.join(CACHE, "successor_r1_signatures.csv"), sig_rows)
    print("HEALTH OK; cached %d successors" % len(sig_rows))


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
