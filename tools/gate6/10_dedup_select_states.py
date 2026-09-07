#!/usr/bin/env python3
"""Gate6: physical-snapshot dedup + spacing + target-tagging for selected states.

Rules (fixed, no manual attribution):
- any physical frame mapped to >=2 unique_instance_id -> excluded entirely
- one snapshot_path may enter the selected set only once (claimed across instances)
- per instance: quartile best (max D1) among single-dominant, unclaimed frames;
  a quartile may be missing
- enforce min adjacent selected-state gap >= MIN_GAP frames (default 10 = 0.5 s)
- add dominant_actor_type / dominant_belongs_to_target_scenario
Emits selected_states_v2.csv
"""
import csv
import json
import os
from collections import defaultdict

RUNS = {
    "route10": ("outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59",
                "outputs/gate6/scnlog_route10.jsonl"),
    "route14": ("outputs/gate6/snapshots/exact_town12_route14_route0_09_04_15_52_40",
                "outputs/gate6/scnlog_route14.jsonl"),
    "route3": ("outputs/gate6/snapshots/exact_town12_route3_discovery_route0_09_04_17_01_56",
               "outputs/gate6/scnlog_route3disc.jsonl"),
}
FILES = ["gate6/dominant_actor_frames.csv"]
MIN_GAP = 10  # simulator frames (~0.5 s @20 Hz)


def load_meta_index():
    idx = {}
    for route, (snapdir, _) in RUNS.items():
        m = {}
        for line in open(os.path.join(snapdir, "meta.jsonl")):
            r = json.loads(line)
            m[r["frame"]] = {a["token_idx"]: a for a in r["actors"]}
        idx[route] = m
    return idx


def owned_map():
    owned = {}
    for route, (_, sc) in RUNS.items():
        for e in (json.loads(l) for l in open(sc)):
            if e["type"] != "HardBreakRoute":
                owned[f"{route}|{e['config_name']}"] = set(e.get("actor_ids", []))
    return owned


def main():
    meta = load_meta_index()
    owned = owned_map()
    rows = []
    for f in FILES:
        for r in csv.DictReader(open(f)):
            r["route"] = r["unique_instance_id"].split("|")[0]
            rows.append(r)

    # mapping multiplicity per (route, frame)
    cnt = defaultdict(set)
    for r in rows:
        cnt[(r["route"], r["frame"])].add(r["unique_instance_id"])
    overlap_keys = {k for k, v in cnt.items() if len(v) >= 2}
    print(f"frame rows={len(rows)} unique snapshots={len(cnt)} "
          f"multi-instance(overlap) snapshots={len(overlap_keys)}")

    # order instances deterministically
    by_inst = defaultdict(list)
    for r in rows:
        if r["single_dominant"] == "1" and (r["route"], r["frame"]) not in overlap_keys:
            by_inst[r["unique_instance_id"]].append(r)
    order = sorted(by_inst.keys())

    used = set()  # (route, frame) claimed
    sel = []
    for uid in order:
        rs = by_inst[uid]
        chosen = []
        for q in range(4):
            lo, hi = q / 4.0, (q + 1) / 4.0
            cand = [r for r in rs
                    if lo <= float(r["scenario_progress"]) <= hi
                    and (r["route"], r["frame"]) not in used]
            if not cand:
                continue
            best = max(cand, key=lambda r: float(r["D1"]))
            chosen.append(best)
            used.add((best["route"], best["frame"]))
        # enforce spacing
        chosen.sort(key=lambda r: int(r["frame"]))
        changed = True
        while changed:
            changed = False
            for i in range(len(chosen) - 1):
                if int(chosen[i + 1]["frame"]) - int(chosen[i]["frame"]) < MIN_GAP:
                    drop = chosen[i] if float(chosen[i]["D1"]) <= float(chosen[i + 1]["D1"]) else chosen[i + 1]
                    keep = chosen[i + 1] if drop is chosen[i] else chosen[i]
                    used.discard((drop["route"], drop["frame"]))
                    chosen.remove(drop)
                    changed = True
                    break
        for r in chosen:
            sel.append((uid, r))

    # enrich + write
    out = []
    for uid, r in sel:
        route = uid.split("|")[0]
        frame = int(r["frame"])
        a = meta[route].get(frame, {}).get(int(r["dominant_token_idx"]), {})
        dom_type = int(a.get("type", -1)) if a else None
        dom_id = a.get("actor_id") if a else r.get("dominant_actor_id")
        belongs = (dom_id is not None and uid in owned and dom_id in owned[uid])
        out.append({
            "state_id": f"V{len(out):06d}",
            "scenario_group": r["scenario_group"],
            "unique_instance_id": uid,
            "route_id": route,
            "frame": r["frame"],
            "scenario_progress": r["scenario_progress"],
            "dominant_actor_id": dom_id if dom_id is not None else "",
            "dominant_token_idx": r["dominant_token_idx"],
            "dominant_actor_type": dom_type if dom_type is not None else "",
            "dominant_belongs_to_target_scenario": int(belongs),
            "D1": r["D1"], "D2": r["D2"], "D1_D2_ratio": r["D1_D2_ratio"],
            "quartile": "",
        })
    # recompute quartile from progress after final ordering not needed; assign by progress
    for o in out:
        p = float(o["scenario_progress"])
        o["quartile"] = {0: "Q1_early", 1: "Q2_early-mid", 2: "Q3_late-mid", 3: "Q4_late"}[int(min(3, p * 4))]
    with open("gate6/selected_states_v2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"selected_states_v2 rows={len(out)} unique snapshots=", len({(o['route_id'], o['frame']) for o in out}))

    from collections import Counter
    by = defaultdict(list)
    for o in out:
        by[o["scenario_group"]].append(o)
    print("\nper-group:")
    print(f"{'group':22s} states unique_snap inst_w_states primary(target-dom) secondary")
    for g in ("A_HardBreak", "B_ParkingCutIn", "C_VehicleTurning", "D_PedestrianCrossing"):
        os_ = by.get(g, [])
        n_inst = len({o["unique_instance_id"] for o in os_})
        uniq = len({(o["route_id"], o["frame"]) for o in os_})
        prim = sum(1 for o in os_ if o["dominant_belongs_to_target_scenario"] == 1)
        print(f"{g:22s} {len(os_):5d} {uniq:9d} {n_inst:12d} {prim:21d} {len(os_)-prim:9d}")


if __name__ == "__main__":
    main()
