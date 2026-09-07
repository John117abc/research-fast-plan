#!/usr/bin/env python3
"""Gate6 dominant-actor post-process -> three CSVs + summary stats."""
import csv
import glob
import os
from collections import defaultdict

GROUP = {"HardBreakRoute": "A_HardBreak", "ParkingCutIn": "B_ParkingCutIn",
         "VehicleTurningRoute": "C_VehicleTurning", "PedestrianCrossing": "D_PedestrianCrossing"}


def main():
    files = ["gate6/dominant_frames_route10.csv", "gate6/dominant_frames_route14.csv",
             "gate6/dominant_frames_route3.csv"]
    rows = []
    for f in files:
        if os.path.isfile(f):
            for r in csv.DictReader(open(f)):
                rows.append(r)
    print("total frame rows:", len(rows))

    # add unique instance id, progress p within instance window, quartile
    for r in rows:
        r["unique_instance_id"] = f"{r['route']}|{r['config_name']}"
        r["scenario_group"] = GROUP.get(r["scenario_group"], r["scenario_group"])

    by_inst = defaultdict(list)
    for r in rows:
        by_inst[r["unique_instance_id"]].append(r)
    # normalized progress per instance (frame min/max)
    for uid, rs in by_inst.items():
        frames = sorted(int(x["frame"]) for x in rs)
        fmin, fmax = frames[0], frames[-1]
        span = max(1, fmax - fmin)
        for r in rs:
            r["scenario_progress"] = round((int(r["frame"]) - fmin) / span, 4)

    # ---- dominant_actor_frames.csv ----
    flds = ["state_id", "scenario_group", "unique_instance_id", "route_id", "frame",
            "scenario_progress", "num_dynamic_actors", "dominant_actor_id",
            "dominant_token_idx", "D1", "D2", "D1_D2_ratio", "pass_D1",
            "pass_ratio", "single_dominant"]
    with open("gate6/dominant_actor_frames.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flds)
        w.writeheader()
        for i, r in enumerate(rows):
            w.writerow({
                "state_id": f"F{i:06d}", "scenario_group": r["scenario_group"],
                "unique_instance_id": r["unique_instance_id"],
                "route_id": r["route"] + "|" + r["config_name"],
                "frame": r["frame"], "scenario_progress": r["scenario_progress"],
                "num_dynamic_actors": r["num_dynamic_actors"],
                "dominant_actor_id": r.get("dominant_actor_id", ""),
                "dominant_token_idx": r["dominant_token_idx"],
                "D1": r["D1"], "D2": r["D2"], "D1_D2_ratio": r["D1_D2_ratio"],
                "pass_D1": r["pass_D1"], "pass_ratio": r["pass_ratio"],
                "single_dominant": r["single_dominant"],
            })

    # ---- per-instance stats ----
    inst_rows = []
    for uid, rs in sorted(by_inst.items()):
        sd = [r for r in rs if r["single_dominant"] == "1"]
        d1s = [float(r["D1"]) for r in rs]
        inst_rows.append({
            "scenario_group": rs[0]["scenario_group"], "unique_instance_id": uid,
            "num_valid_frames": len(rs),
            "num_single_dominant_frames": len(sd),
            "single_dominant_rate": round(len(sd) / max(1, len(rs)), 3),
            "max_D1": round(max(d1s), 3), "median_D1": round(sorted(d1s)[len(d1s) // 2], 3),
        })
    with open("gate6/dominant_actor_instances.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_group", "unique_instance_id",
                                          "num_valid_frames", "num_single_dominant_frames",
                                          "single_dominant_rate", "max_D1", "median_D1"])
        w.writeheader()
        w.writerows(inst_rows)

    # ---- selected states (quartile max-D1 among single-dominant) ----
    sel = []
    qnames = {0: "Q1_early", 1: "Q2_early-mid", 2: "Q3_late-mid", 3: "Q4_late"}
    for uid, rs in sorted(by_inst.items()):
        sd = [r for r in rs if r["single_dominant"] == "1"]
        if not sd:
            continue
        for q in range(4):
            lo, hi = q / 4.0, (q + 1) / 4.0
            cand = [r for r in sd if lo <= float(r["scenario_progress"]) <= hi]
            if not cand:
                continue
            best = max(cand, key=lambda r: float(r["D1"]))
            best["quartile"] = qnames[q]
            sel.append(best)
    flds2 = ["state_id", "scenario_group", "unique_instance_id", "route_id", "frame",
             "scenario_progress", "quartile", "dominant_actor_id", "dominant_token_idx",
             "D1", "D2", "D1_D2_ratio", "snapshot_path"]
    with open("gate6/selected_states.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flds2)
        w.writeheader()
        for i, r in enumerate(sel):
            w.writerow({
                "state_id": f"S{i:06d}", "scenario_group": r["scenario_group"],
                "unique_instance_id": r["unique_instance_id"],
                "route_id": r["route"] + "|" + r["config_name"],
                "frame": r["frame"], "scenario_progress": r["scenario_progress"],
                "quartile": r["quartile"], "dominant_actor_id": r.get("dominant_actor_id", ""),
                "dominant_token_idx": r["dominant_token_idx"], "D1": r["D1"],
                "D2": r["D2"], "D1_D2_ratio": r["D1_D2_ratio"],
                "snapshot_path": r.get("snapshot_path", ""),
            })

    print("wrote dominant_actor_frames.csv / dominant_actor_instances.csv / selected_states.csv")
    print("\n=== per-group summary ===")
    print(f"{'group':22s} {'inst':>4s} {'inst_w/dom':>9s} {'dom-frames':>10s} {'dom-rate(med)':>12s} {'selected':>8s}")
    agg = defaultdict(list)
    for r in inst_rows:
        agg[r["scenario_group"]].append(r)
    sel_cnt = defaultdict(int)
    for r in sel:
        sel_cnt[r["scenario_group"]] += 1
    for g in ("A_HardBreak", "B_ParkingCutIn", "C_VehicleTurning", "D_PedestrianCrossing"):
        rs = agg.get(g, [])
        n_inst = len(rs)
        n_dom = sum(1 for r in rs if r["num_single_dominant_frames"] > 0)
        tot_dom = sum(r["num_single_dominant_frames"] for r in rs)
        rates = sorted(r["single_dominant_rate"] for r in rs)
        med = rates[len(rates) // 2] if rates else 0
        print(f"{g:22s} {n_inst:4d} {n_dom:9d} {tot_dom:10d} {med:12.3f} {sel_cnt.get(g,0):8d}")


if __name__ == "__main__":
    main()
