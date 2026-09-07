#!/usr/bin/env python3
"""Gate6 Signature QC:
1) HB lead-primary marker (dominant_matches_hardbreak_lead) + primary_mechanistic.
2) Per-state I1..I5 block norms, signature_norm, max_block_fraction.
3) Freeze Equal-Intervention metric: append signature_dir + magnitude profile.
Writes gate6/selected_states_v3.csv and gate6/signature_qc.csv (and updates npz).
"""
import csv
import glob
import json
import math
import os

RUNS = {
    "route10": ("outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59",
                "outputs/gate6/scnlog_route10.jsonl"),
    "route14": ("outputs/gate6/snapshots/exact_town12_route14_route0_09_04_15_52_40",
                "outputs/gate6/scnlog_route14.jsonl"),
    "route3": ("outputs/gate6/snapshots/exact_town12_route3_discovery_route0_09_04_17_01_56",
               "outputs/gate6/scnlog_route3disc.jsonl"),
}
BLOCKS = ["I1", "I2", "I3", "I4", "I5"]
EPS = 1e-6


def load_meta(route):
    idx = {}
    for line in open(os.path.join(RUNS[route][0], "meta.jsonl")):
        m = json.loads(line)
        idx[m["frame"]] = m
    return idx


def find_hb_lead(meta, te):
    """Return nearest stopped front dynamic actor in the hard-brake window [te,te+60].

    Uses frames where ego is slowed (<2.5 m/s); lead candidate = nearest in-lane
    (|y|<2.5, x in 1..45) stopped (<2.5 m/s) actor of type 1/6.
    """
    frames = []
    for fr, m in sorted(meta.items()):
        t = fr / 20.0
        if te <= t <= te + 60 and m["ego_speed_mps"] < 2.5:
            frames.append(m)
    if not frames:
        return None
    best = None
    best_d = None
    for m in frames:
        for a in m["actors"]:
            if a["type"] in (1.0, 6.0) and 1.0 < a["x"] < 45.0 and abs(a["y"]) < 2.5 and a["speed_kmh"] < 9.0:
                d = math.hypot(a["x"], a["y"])
                if best is None or d < best_d:
                    best, best_d = a["actor_id"], d
    return best


def main():
    meta = {r: load_meta(r) for r in RUNS}
    # HB lead per instance
    hb_events = {}
    for route, (_, sc) in RUNS.items():
        for e in (json.loads(l) for l in open(sc)):
            if e["type"] == "HardBreakRoute":
                hb_events[f"{route}|{e['config_name']}"] = find_hb_lead(meta[route], e.get("game_time") or 0.0)

    states = list(csv.DictReader(open("gate6/selected_states_v2.csv")))
    out = []
    for s in states:
        uid = s["unique_instance_id"]
        route = uid.split("|")[0]
        grp = s["scenario_group"]
        s = dict(s)
        if grp == "A_HardBreak":
            lead = hb_events.get(uid)
            s["hb_lead_actor_id"] = lead if lead is not None else ""
            s["dominant_matches_hardbreak_lead"] = int(s["dominant_actor_id"] != "" and lead is not None
                                                        and int(s["dominant_actor_id"]) == lead)
            s["primary_mechanistic"] = s["dominant_matches_hardbreak_lead"]
        else:
            s["hb_lead_actor_id"] = ""
            s["dominant_matches_hardbreak_lead"] = 0
            s["primary_mechanistic"] = s["dominant_belongs_to_target_scenario"]
        out.append(s)

    # QC over signature npz
    qc = []
    for s in out:
        p = os.path.join("gate6/signatures", f"{s['state_id']}.npz")
        if not os.path.isfile(p):
            continue
        d = dict(np.load(p))
        w0 = d["W0"]
        norms = {}
        for k in BLOCKS:
            diff = d[k] - w0
            norms[k] = float(np.linalg.norm(diff.reshape(-1)))
        sq = sum(v * v for v in norms.values())
        maxi = max(BLOCKS, key=lambda k: norms[k])
        frac = norms[maxi] ** 2 / max(sq, EPS)
        # equal-intervention signature
        sig_dir = np.concatenate([(d[k] - w0).reshape(-1) / (norms[k] + EPS) for k in BLOCKS])
        mag = np.array([norms[k] for k in BLOCKS])
        d["signature_dir"] = sig_dir
        d["magnitude_profile"] = mag
        np.savez(p, **d)
        qc.append({"state_id": s["state_id"], "scenario_group": s["scenario_group"],
                   "unique_instance_id": s["unique_instance_id"],
                   "norm_I1": round(norms["I1"], 4), "norm_I2": round(norms["I2"], 4),
                   "norm_I3": round(norms["I3"], 4), "norm_I4": round(norms["I4"], 4),
                   "norm_I5": round(norms["I5"], 4),
                   "signature_norm": round(math.sqrt(sq), 4),
                   "max_block": maxi, "max_block_fraction": round(frac, 4)})

    with open("gate6/selected_states_v3.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    with open("gate6/signature_qc.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["state_id", "scenario_group", "unique_instance_id",
                                          "norm_I1", "norm_I2", "norm_I3", "norm_I4", "norm_I5",
                                          "signature_norm", "max_block", "max_block_fraction"])
        w.writeheader()
        w.writerows(qc)

    # stats
    import statistics
    fr = [q["max_block_fraction"] for q in qc]
    mx = {}
    for q in qc:
        mx[q["max_block"]] = mx.get(q["max_block"], 0) + 1
    print(f"wrote selected_states_v3 ({len(out)}) and signature_qc.csv ({len(qc)})")
    print("max_block counts:", mx)
    print("max_block_fraction median=%.3f p10=%.3f p90=%.3f" % (
        statistics.median(fr), sorted(fr)[len(fr)//10], sorted(fr)[int(len(fr)*0.9)]))
    print("HB primary (matches lead):", sum(1 for s in out if s["scenario_group"]=="A_HardBreak" and s["primary_mechanistic"]=="1"))


if __name__ == "__main__":
    import numpy as np
    main()
