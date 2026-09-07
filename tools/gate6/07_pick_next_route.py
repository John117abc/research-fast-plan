#!/usr/bin/env python3
"""Pick next Town12 route by gap-weighted score over expected-reachable triggers.

Collected so far (route10): HB7 PCI5 VT2 PED5 ; target 8 per group.
Gap: HB1 PCI3 VT6 PED3.
Score(route) = 3*N_VT + 2*N_PCI + 2*N_PED + 0.5*N_HB   (counts capped by gap)
counting only triggers with progress <= REACH_FRAC.
Excludes already-run routes.
"""
import csv
import os
from collections import defaultdict

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "gate6")
CSV_PATH = os.path.join(OUT, "town12_discovery_routes_reachable.csv")
RUN = {"routes_training.xml": {"10"}}
TARGET = 8
HAVE = {"A_HardBreak": 7, "B_ParkingCutIn": 5, "C_VehicleTurning": 2, "D_PedestrianCrossing": 5}
W = {"C_VehicleTurning": 3, "B_ParkingCutIn": 2, "D_PedestrianCrossing": 2, "A_HardBreak": 0.5}
REACH_FRAC = float(os.environ.get("REACH_FRAC", "0.60"))


def main():
    rows = list(csv.DictReader(open(CSV_PATH)))
    by = defaultdict(list)
    for r in rows:
        by[(r["source_file"], r["route_id"])].append(r)
    results = []
    for key, rs in by.items():
        if key in RUN or key[0].startswith("bench2drive"):
            continue
        length = float(rs[0]["route_length"])
        contrib = defaultdict(int)
        for r in rs:
            if float(r["trigger_progress"]) <= REACH_FRAC:
                contrib[r["scenario_group"]] += 1
        gap_left = {g: max(0, TARGET - HAVE[g]) for g in W}
        score = sum(W[g] * min(contrib[g], gap_left[g]) for g in W)
        results.append((score, key, length, dict(contrib), sum(contrib.values())))
    results.sort(key=lambda x: (-x[0], x[2]))
    print(f"REACH_FRAC={REACH_FRAC}  have={HAVE}  target={TARGET}")
    print(f"{'score':>6} {'route':>24} {'len':>7}  reachable(A/B/C/D)  reach_tot")
    for score, key, length, contrib, tot in results[:12]:
        c = f"{contrib.get('A_HardBreak',0)}/{contrib.get('B_ParkingCutIn',0)}/{contrib.get('C_VehicleTurning',0)}/{contrib.get('D_PedestrianCrossing',0)}"
        print(f"{score:6.1f} {key[1]+':'+key[0]:>24} {length:7.0f}  {c:>18}  {tot}")


if __name__ == "__main__":
    main()
