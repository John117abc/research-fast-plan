#!/usr/bin/env python3
"""B0-C1 step 1: confirmatory health + R1 signatures + 576 successor cache.

Self-contained (does not modify frozen files). Reuses the frozen R1 modules.

usage: python gate_b0/scripts/23_c1_build.py
writes gate_b0/results/confirmatory/{data_health.json, r1_signatures.csv,
successor_index.csv, successor_r1_signatures.csv}
"""
import csv
import glob
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
from consequence.r1_signature import COLS  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402

RAW = os.path.join(B0, "confirmatory/raw")
OUT = os.path.join(B0, "results/confirmatory")
CFG = common.cfg()


def _family_key(spec):
    bw = CFG["param_group"]["bin_width"]
    cell = spec.get("cell", "")
    if "L" in spec:
        return "L%d" % (int(spec["L"]) // bw)
    if "d_conflict" in spec:
        return "d%d" % (int(spec["d_conflict"]) // bw)
    if "occ_s" in spec:
        return "o%d" % (int(spec["occ_s"]) // bw)
    if cell.startswith("lead") and "s0" in spec:
        return "s%d" % (int(spec["s0"]) // bw)
    return "na"


def list_states():
    out = []
    for path in sorted(glob.glob(os.path.join(RAW, "*/*/*.ndjson"))):
        parts = path.replace("\\", "/").split("/")
        mech, cell = parts[-3], parts[-2]
        cid = parts[-1][:-len(".ndjson")]
        with open(path) as fh:
            first = json.loads(fh.readline())
        sc = first.get("scenario", {})
        spec = sc.get("spec", {})
        out.append({"state_id": cid, "path": path, "mech": mech, "cell": cell,
                    "fine_mechanism": cell, "coarse_mechanism": common.coarse_of(mech),
                    "param_group_id": "%s|v%s|%s" % (cell, spec.get("ego_v"), _family_key(spec)),
                    "spec": spec, "ego_speed": float(sc.get("v_target", 0.0)),
                    "ego_s": float(first.get("ego_s", 0.0)),
                    "target_actor_ids": [a["actor_id"] for a in first.get("actors", [])]})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    states = list_states()
    assert len(states) == 72, "expected 72 states, got %d" % len(states)
    # health
    health = {"n_states": len(states), "bad": []}
    for st in states:
        rows = common.load_rows(st["path"])
        tmax = max(r["sim_t"] for r in rows)
        ids = set(st["target_actor_ids"])
        ok = tmax >= 11.0 - 1e-6
        for k in range(2, 23):
            t = k * 0.5
            r = min(rows, key=lambda x: abs(x["sim_t"] - t))
            if abs(r["sim_t"] - t) > 0.3 or not ids <= {a["actor_id"] for a in r["actors"]}:
                ok = False
                break
        health.setdefault("checks", []).append({"state_id": st["state_id"],
                                                "sim_t_max": round(tmax, 3), "ok": ok})
        if not ok:
            health["bad"].append(st["state_id"])
    health["all_ok"] = len(health["bad"]) == 0
    json.dump(health, open(os.path.join(OUT, "data_health.json"), "w"), indent=1)
    if not health["all_ok"]:
        print("HEALTH FAIL", health["bad"])
        return

    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    sig_rows, idx_rows, succ_rows = [], [], []
    for st in states:
        slots = common.build_slots(st["path"])
        win = slots[: cr.N + 1]
        occ = cr.build_occ(win, st["ego_s"])
        sig = r1.compute_r1(st["ego_speed"], 0, 0.0, win, st["ego_s"])
        row = {"state_id": st["state_id"], "coarse_mechanism": st["coarse_mechanism"],
               "fine_mechanism": st["fine_mechanism"], "param_group_id": st["param_group_id"],
               "ego_speed": st["ego_speed"], **sig}
        sig_rows.append(row)
        for a in ACTIONS:
            pr = cr.run_probe((0.0, st["ego_speed"], 0, 0.0), a["ax"], a["lateral"], occ, cor)
            s = pr["successor"]
            idx_rows.append({"state_id": st["state_id"], "probe_action": a["id"],
                             "successor_valid": int(pr["valid"]),
                             "successor_s": s[0] if s else "", "successor_v": s[1] if s else "",
                             "successor_mode": s[2] if s else "",
                             "lane_change_elapsed": s[3] if s else ""})
            srow = {"state_id": st["state_id"], "probe_action": a["id"],
                    "successor_valid": int(pr["valid"])}
            if pr["valid"]:
                sr1 = r1.successor_r1({"successor": s}, slots, st["ego_s"])
                srow.update(sr1)
            succ_rows.append(srow)
        print("done", st["state_id"])
    _write(os.path.join(OUT, "r1_signatures.csv"), sig_rows)
    _write(os.path.join(OUT, "successor_index.csv"), idx_rows)
    _write(os.path.join(OUT, "successor_r1_signatures.csv"), succ_rows)
    print("HEALTH OK; signatures %d; successors %d" % (len(sig_rows), len(succ_rows)))


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
