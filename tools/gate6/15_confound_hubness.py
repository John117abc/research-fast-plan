#!/usr/bin/env python3
"""Gate6 15: confound + hubness on Primary cross-scene candidates (68).

Attaches: same_route, |delta ego speed|, route curvature, dominant actor
distance/type per state; candidate_degree per state; scene_pair_types.
"""
import csv
import glob
import math
import os
from collections import Counter, defaultdict

import numpy as np

SNAP = {
    "route10": "outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59",
    "route14": "outputs/gate6/snapshots/exact_town12_route14_route0_09_04_15_52_40",
    "route3": "outputs/gate6/snapshots/exact_town12_route3_discovery_route0_09_04_17_01_56",
}


def meta_index(route):
    idx = {}
    for line in open(os.path.join(SNAP[route], "meta.jsonl")):
        m = json.loads(line)
        idx[m["frame"]] = m
    return idx


def curvature(route_local):
    """mean abs direction change (deg) of top-20 local route points."""
    p = np.asarray(route_local, dtype=float)
    if p.shape[0] < 3:
        return 0.0
    seg = p[1:] - p[:-1]
    norms = np.linalg.norm(seg, axis=1)
    ang = []
    for i in range(len(seg) - 1):
        if norms[i] > 1e-6 and norms[i + 1] > 1e-6:
            c = np.dot(seg[i], seg[i + 1]) / (norms[i] * norms[i + 1])
            ang.append(math.degrees(math.acos(max(-1.0, min(1.0, c)))))
    return float(np.mean(ang)) if ang else 0.0


def main():
    states = list(csv.DictReader(open("gate6/selected_states_v3.csv")))
    st = {r["state_id"]: r for r in states}
    idx = {r: meta_index(r) for r in SNAP}
    # per-state auxiliary
    aux = {}
    for r in states:
        route = r["unique_instance_id"].split("|")[0]
        m = idx[route].get(int(r["frame"]), {})
        ego_spd = m.get("ego_speed_mps")
        dom_dist = dom_type = None
        for a in m.get("actors", []):
            if a["token_idx"] == int(r["dominant_token_idx"]):
                dom_type = int(a["type"])
                dom_dist = math.hypot(a["x"], a["y"])
                break
        p = os.path.join("gate6/signatures", f"{r['state_id']}.npz")
        cur = None
        if os.path.isfile(p):
            d = dict(np.load(p))
            if "route_original" in d:
                cur = curvature(d["route_original"][0])
        aux[r["state_id"]] = {"route": route, "ego_speed": ego_spd,
                              "curvature": cur, "dom_dist": dom_dist,
                              "dom_type": dom_type}

    # recompute primary cross candidates (mirror frozen metric)
    import itertools
    prim = [s for s in states if s["primary_mechanistic"] == "1"]
    cand = []
    for a, b in itertools.combinations(prim, 2):
        if a["scenario_group"] == b["scenario_group"]:
            continue
        if a["unique_instance_id"] == b["unique_instance_id"]:
            continue
        if (a["unique_instance_id"].split("|")[0], a["frame"]) == \
           (b["unique_instance_id"].split("|")[0], b["frame"]):
            continue
        da = dict(np.load(os.path.join("gate6/signatures", f"{a['state_id']}.npz")))
        db = dict(np.load(os.path.join("gate6/signatures", f"{b['state_id']}.npz")))
        cd = float(np.dot(da["signature_dir"], db["signature_dir"]) /
                   (np.linalg.norm(da["signature_dir"]) * np.linalg.norm(db["signature_dir"]) + 1e-9))
        ms = float(np.dot(da["magnitude_profile"], db["magnitude_profile"]) /
                   (np.linalg.norm(da["magnitude_profile"]) * np.linalg.norm(db["magnitude_profile"]) + 1e-9))
        if cd >= 0.90 and ms >= 0.50:
            aa, bb = aux[a["state_id"]], aux[b["state_id"]]
            cand.append({
                "state_A": a["state_id"], "state_B": b["state_id"],
                "group_A": a["scenario_group"], "group_B": b["scenario_group"],
                "uid_A": a["unique_instance_id"], "uid_B": b["unique_instance_id"],
                "cos_dir": round(cd, 4), "mag_sim": round(ms, 4),
                "same_route": int(aa["route"] == bb["route"]),
                "delta_ego_speed": round(abs((aa["ego_speed"] or 0) - (bb["ego_speed"] or 0)), 2),
                "curv_A": round(aa["curvature"], 2) if aa["curvature"] is not None else "",
                "curv_B": round(bb["curvature"], 2) if bb["curvature"] is not None else "",
                "dom_dist_A": round(aa["dom_dist"], 2) if aa["dom_dist"] is not None else "",
                "dom_dist_B": round(bb["dom_dist"], 2) if bb["dom_dist"] is not None else "",
                "dom_type_A": aa["dom_type"], "dom_type_B": bb["dom_type"],
            })
    cand.sort(key=lambda r: -r["cos_dir"])
    with open("gate6/pair_cross_primary_confounds.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cand[0].keys()))
        w.writeheader()
        w.writerows(cand)

    # hubness over candidates
    deg = defaultdict(lambda: {"count": 0, "pairs": Counter()})
    for c in cand:
        deg[c["state_A"]]["count"] += 1
        deg[c["state_B"]]["count"] += 1
        for s in (c["state_A"], c["state_B"]):
            other_g = c["group_B"] if s == c["state_A"] else c["group_A"]
            deg[s]["pairs"][other_g] += 1
    hub = [{"state_id": s, "candidate_degree": v["count"],
            "scene_pair_types": dict(v["pairs"]), "scenario_group": st[s]["scenario_group"],
            "route": aux[s]["route"]} for s, v in deg.items()]
    hub.sort(key=lambda x: -x["candidate_degree"])
    with open("gate6/pair_hubness_primary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["state_id", "scenario_group", "route",
                                          "candidate_degree", "scene_pair_types"])
        w.writeheader()
        w.writerows(hub)

    n = len(cand)
    print(f"primary candidates={n}")
    print("same_route fraction:", sum(1 for c in cand if c["same_route"]) / n)
    sr = sorted((float(c["delta_ego_speed"]) for c in cand))
    print("delta_ego_speed median=%.1f p90=%.1f" % (sr[n // 2], sr[int(n * .9)]))
    top = cand[:50]
    print("same_route fraction in top50:", sum(1 for c in top if c["same_route"]) / len(top))
    print("hubness: states with degree>=10:", sum(1 for h in hub if h["candidate_degree"] >= 10),
          "max degree", hub[0]["candidate_degree"] if hub else 0)
    for h in hub[:6]:
        print("  ", h["state_id"], h["scenario_group"], h["route"], "deg", h["candidate_degree"], h["scene_pair_types"])


if __name__ == "__main__":
    import json as json_mod
    json = json_mod
    main()
