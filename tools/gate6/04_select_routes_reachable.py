#!/usr/bin/env python3
"""Gate6 route3-fix A: reachable-oriented Town12 route scoring.

Adds trigger_progress (0..1) per scenario instance along its route polyline and
route_length; ranks Town12 route elements by: target coverage in the reachable
prefix (first ~55% of route), count per group (>=2 each), and shorter length.
Emits gate6/town12_discovery_routes_reachable.csv (all Town12 routes that contain
>=1 target instance, with per-instance progress) plus a short recommendation.
"""
import csv
import glob
import math
import os
import xml.etree.ElementTree as ET

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "gate6")
TARGETS = {"HardBreakRoute", "ParkingCutIn", "VehicleTurningRoute", "PedestrianCrossing"}
GROUPS = {"HardBreakRoute": "A_HardBreak", "ParkingCutIn": "B_ParkingCutIn",
          "VehicleTurningRoute": "C_VehicleTurning", "PedestrianCrossing": "D_PedestrianCrossing"}
SOURCES = ["leaderboard/data/routes_training.xml"] + \
    sorted(glob.glob("leaderboard/data/routes_validation_split/*.xml")) + \
    sorted(glob.glob("leaderboard/data/bench2drive_split/*.xml"))
REACHABLE_FRAC = 0.55  # assume PlanT can reliably cover first 55% of a Town12 route


def polyline_length(points):
    return sum(math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
               for i in range(1, len(points)))


def nearest_progress(route_pts, tx, ty):
    """Project trigger onto route polyline; return cumulative progress fraction."""
    if tx is None or ty is None or len(route_pts) < 2:
        return None
    best = None
    best_t = None
    for i in range(1, len(route_pts)):
        ax, ay = route_pts[i - 1]
        bx, by = route_pts[i]
        vx, vy = bx - ax, by - ay
        wx, wy = tx - ax, ty - ay
        vlen2 = vx * vx + vy * vy
        t = 0.0 if vlen2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
        px, py = ax + t * vx, ay + t * vy
        d = math.hypot(tx - px, ty - py)
        if best is None or d < best:
            best = d
            best_t = t
            seg = i
    # cumulative distance to projected point
    cum = 0.0
    for i in range(1, seg):
        cum += math.hypot(route_pts[i][0] - route_pts[i - 1][0],
                          route_pts[i][1] - route_pts[i - 1][1])
    cum += best_t * math.hypot(route_pts[seg][0] - route_pts[seg - 1][0],
                               route_pts[seg][1] - route_pts[seg - 1][1])
    return cum


def main():
    from collections import Counter
    route_len = {}
    inst_by_route = {}
    per_route_detail = {}
    for path in SOURCES:
        if not os.path.isfile(path):
            continue
        try:
            tree = ET.parse(path)
        except Exception:
            continue
        for r in tree.getroot().iter("route"):
            if r.attrib.get("town") != "Town12":
                continue
            rid = r.attrib.get("id")
            wps = [(float(p.attrib["x"]), float(p.attrib["y"]))
                   for p in r.find("waypoints").iter("position")] if r.find("waypoints") is not None else []
            if len(wps) < 2:
                continue
            L = polyline_length(wps)
            key = (os.path.basename(path), rid)
            route_len[key] = L
            rows = []
            for s in r.iter("scenario"):
                typ = s.attrib.get("type")
                if typ not in TARGETS:
                    continue
                tp = s.find("trigger_point")
                tx = tp.attrib.get("x") if tp is not None else None
                ty = tp.attrib.get("y") if tp is not None else None
                tyaw = tp.attrib.get("yaw") if tp is not None else None
                prog = nearest_progress(wps, float(tx), float(ty)) if (tx and ty) else None
                prog = 0.0 if prog is None else prog / L
                rows.append({
                    "route_id": rid, "source_file": os.path.basename(path),
                    "scenario_type": typ, "scenario_group": GROUPS[typ],
                    "unique_instance_id": "|".join(
                        ["Town12", str(rid), typ,
                         f"{float(tx):.1f}" if tx else "", f"{float(ty):.1f}" if ty else "",
                         f"{float(tyaw):.1f}" if tyaw else ""]),
                    "scenario_xml_name": s.attrib.get("name", ""),
                    "trigger_progress": round(prog, 3),
                })
            if rows:
                inst_by_route[key] = rows
                per_route_detail[key] = {"length": L, "rows": rows}

    # write full reachable csv (per-instance)
    fields = ["route_id", "source_file", "route_length", "scenario_type",
              "scenario_group", "unique_instance_id", "scenario_xml_name", "trigger_progress"]
    with open(os.path.join(OUT, "town12_discovery_routes_reachable.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key, rows in inst_by_route.items():
            for row in sorted(rows, key=lambda x: x["trigger_progress"]):
                w.writerow({"route_id": key[1], "source_file": key[0],
                            "route_length": round(route_len[key]),
                            **{k: row[k] for k in ("scenario_type", "scenario_group",
                                                   "unique_instance_id", "scenario_xml_name",
                                                   "trigger_progress")}})

    # route-level scoring
    scored = []
    for key, rows in inst_by_route.items():
        cnt = Counter(r["scenario_group"] for r in rows)
        reach = [r for r in rows if r["trigger_progress"] <= REACHABLE_FRAC]
        rcnt = Counter(r["scenario_group"] for r in reach)
        scored.append({
            "key": key, "length": route_len[key], "total_targets": len(rows),
            "reachable_targets": len(reach),
            "per_group_total": cnt, "per_group_reachable": rcnt,
        })
    scored.sort(key=lambda x: (x["length"], -x["reachable_targets"]))
    print("Town12 route elements with targets:", len(scored))
    print("\nTop short routes with reachable coverage per group (need >=2 each for smoke):")
    for s in scored[:15]:
        print(f"  {s['key']} len={s['length']:6.0f}m total={s['total_targets']:2d} "
              f"reach<={REACHABLE_FRAC}: {dict(s['per_group_reachable'])}  (all:{dict(s['per_group_total'])})")


if __name__ == "__main__":
    main()
