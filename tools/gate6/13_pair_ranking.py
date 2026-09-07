#!/usr/bin/env python3
"""Gate6 pair ranking with frozen Equal-Intervention Response Similarity.

Similarity:
  cos_dir = cosine(S_dir_A, S_dir_B)      (equal-intervention direction)
  mag_sim = cosine(magA, magB)            (5-intervention magnitude profile)
Cross-scene candidate: group != group, instance != instance, snapshot != snapshot,
  cos_dir >= 0.90 AND mag_sim >= 0.50 ; ranked by cos_dir, require >=3 group-combos.
Same-scene negative: same group, different instance -> lowest cos_dir pairs.
Layers: Primary (mechanistic target-dominant) and All(primary+secondary).
"""
import csv
import math
import os
from collections import defaultdict

CROSS_THRESH = (0.90, 0.50)


def load():
    states = []
    for r in csv.DictReader(open("gate6/selected_states_v3.csv")):
        p = os.path.join("gate6/signatures", f"{r['state_id']}.npz")
        d = dict(__import__("numpy").load(p))
        r["_sig_dir"] = d["signature_dir"]
        r["_mag"] = d["magnitude_profile"]
        r["_snap"] = (r["unique_instance_id"].split("|")[0], r["frame"])
        r["primary"] = (r["primary_mechanistic"] == "1")
        states.append(r)
    return states


def cos(a, b):
    import numpy as np
    a = np.asarray(a, dtype=float).reshape(-1)
    b = np.asarray(b, dtype=float).reshape(-1)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def pairs(states, layer):
    ss = [s for s in states if (s["primary"] if layer == "primary" else True)]
    cross, same = [], []
    grp_of = lambda s: s["scenario_group"]
    for i in range(len(ss)):
        for j in range(i + 1, len(ss)):
            a, b = ss[i], ss[j]
            if a["_snap"] == b["_snap"]:
                continue
            cd = cos(a["_sig_dir"], b["_sig_dir"])
            ms = cos(a["_mag"], b["_mag"])
            rec = {"state_A": a["state_id"], "state_B": b["state_id"],
                   "group_A": grp_of(a), "group_B": grp_of(b),
                   "uid_A": a["unique_instance_id"], "uid_B": b["unique_instance_id"],
                   "cos_dir": round(cd, 4), "mag_sim": round(ms, 4)}
            if grp_of(a) != grp_of(b) and a["unique_instance_id"] != b["unique_instance_id"]:
                cross.append(rec)
            elif grp_of(a) == grp_of(b) and a["unique_instance_id"] != b["unique_instance_id"]:
                same.append(rec)
    return cross, same


def main():
    states = load()
    for layer in ("all", "primary"):
        cross, same = pairs(states, layer)
        cross.sort(key=lambda r: (-r["cos_dir"], -r["mag_sim"]))
        cand = [r for r in cross if r["cos_dir"] >= CROSS_THRESH[0] and r["mag_sim"] >= CROSS_THRESH[1]]
        combos = set((r["group_A"], r["group_B"]) for r in cand)
        print(f"\n=== layer={layer} ===")
        n_use = len([s for s in states if s["primary"]]) if layer == "primary" else len(states)
        print(f"states used ~{n_use}; cross pairs={len(cross)}; candidates@{CROSS_THRESH}={len(cand)}; "
              f"combos={len(combos)}")
        top = cand[:20] if cand else cross[:20]
        out = f"gate6/pair_cross_{layer}.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["state_A", "state_B", "group_A", "group_B",
                                              "uid_A", "uid_B", "cos_dir", "mag_sim"])
            w.writeheader()
            w.writerows(top)
        print("  wrote", out, "top rows", len(top))
        # same-scene negative
        same.sort(key=lambda r: r["cos_dir"])
        neg = same[:15]
        out2 = f"gate6/pair_samescene_neg_{layer}.csv"
        with open(out2, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["state_A", "state_B", "group_A", "group_B",
                                              "uid_A", "uid_B", "cos_dir", "mag_sim"])
            w.writeheader()
            w.writerows(neg)
        print("  wrote", out2, "rows", len(neg))
        # combo coverage among candidates
        from collections import Counter
        cc = Counter(tuple(sorted((r["group_A"], r["group_B"]))) for r in cand)
        print("  candidate combos:", dict(cc))


if __name__ == "__main__":
    main()
