#!/usr/bin/env python3
"""Gate 6 Step 6.1: greedy Town12 route coverage for the 4 target groups.

Selects a small set of routes (keyed by source_file + route_id) that together
cover at least CAP independent scenario instances per group. Selection is based
only on inventory/coverage (never on planning responses).
Emits gate6/town12_discovery_routes.csv.
"""
import csv
import os
from collections import Counter

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "gate6")
MANIFEST = os.path.join(OUT, "town12_manifest.csv")
RESULT = os.path.join(OUT, "town12_discovery_routes.csv")
CAP = 8  # target instances per group


def main():
    rows = list(csv.DictReader(open(MANIFEST)))
    groups = ["A_HardBreak", "B_ParkingCutIn", "C_VehicleTurning", "D_PedestrianCrossing"]

    # instances grouped per (source_file, route_id); drop dup ids already removed
    by_route = {}
    for r in rows:
        key = (r["source_file"], r["route_id"])
        by_route.setdefault(key, []).append(r)

    # total available per group
    avail = Counter(r["scenario_group"] for r in rows)
    print("Town12 available (post-dedup):", dict(avail))

    route_counts = {k: Counter(x["scenario_group"] for x in v)
                    for k, v in by_route.items()}

    needed = {g: CAP for g in groups}
    picked = []
    covered_any = True
    while any(needed[g] > 0 for g in groups) and covered_any:
        covered_any = False
        best_key, best_score, best_gain = None, -1, None
        for key, cnt in route_counts.items():
            if key in picked:
                continue
            score = sum(min(cnt[g], needed[g]) for g in groups)
            if score > best_score:
                best_score, best_key, best_gain = score, key, cnt
        if best_key is None or best_score <= 0:
            break
        picked.append(best_key)
        covered_any = True
        for g in groups:
            needed[g] = max(0, needed[g] - min(best_gain[g], needed[g]))

    print(f"greedy selected {len(picked)} route elements for CAP={CAP}/group")
    print("remaining needed:", {g: v for g, v in needed.items() if v > 0})

    fields = ["route_id", "town", "source_file",
              "covered_hardbreak", "covered_parkingcutin",
              "covered_vehicleturning", "covered_pedestrian",
              "total_instances", "selected_order"]
    g2c = {"A_HardBreak": "covered_hardbreak",
           "B_ParkingCutIn": "covered_parkingcutin",
           "C_VehicleTurning": "covered_vehicleturning",
           "D_PedestrianCrossing": "covered_pedestrian"}
    with open(RESULT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for order, key in enumerate(picked, start=1):
            sf, rid = key
            cnt = route_counts[key]
            w.writerow({
                "route_id": rid,
                "town": "Town12",
                "source_file": sf,
                "covered_hardbreak": cnt["A_HardBreak"],
                "covered_parkingcutin": cnt["B_ParkingCutIn"],
                "covered_vehicleturning": cnt["C_VehicleTurning"],
                "covered_pedestrian": cnt["D_PedestrianCrossing"],
                "total_instances": sum(cnt.values()),
                "selected_order": order,
            })
    print("wrote", RESULT)


if __name__ == "__main__":
    main()
