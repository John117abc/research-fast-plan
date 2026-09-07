#!/usr/bin/env python3
"""Gate 6 Step 6.0: build de-duplicated Town12/Town13 scene manifest.

Reads the four target scenario types from the benchmark route XML sources
(routes_training.xml, routes_validation_split/*.xml, bench2drive_split/*.xml)
and emits gate6/town12_manifest.csv / gate6/town13_manifest.csv.
"""
import csv
import glob
import os
import xml.etree.ElementTree as ET

GROUPS = {
    "HardBreakRoute": "A_HardBreak",
    "ParkingCutIn": "B_ParkingCutIn",
    "VehicleTurningRoute": "C_VehicleTurning",
    "PedestrianCrossing": "D_PedestrianCrossing",
}
TARGET_TYPES = set(GROUPS)
SOURCES = [
    "leaderboard/data/routes_training.xml",
] + sorted(glob.glob("leaderboard/data/routes_validation_split/*.xml")) \
  + sorted(glob.glob("leaderboard/data/bench2drive_split/*.xml"))

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "gate6")
os.makedirs(OUT, exist_ok=True)


def fnum(x, nd=1):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return ""


def main():
    rows = []
    for path in SOURCES:
        if not os.path.isfile(path):
            continue
        try:
            tree = ET.parse(path)
        except Exception as e:
            print("  skip (parse fail):", path, e)
            continue
        for r in tree.getroot().iter("route"):
            town = r.attrib.get("town")
            if town not in ("Town12", "Town13"):
                continue
            route_id = r.attrib.get("id")
            for s in r.iter("scenario"):
                stype = s.attrib.get("type")
                if stype not in TARGET_TYPES:
                    continue
                sname = s.attrib.get("name", "")
                tp = s.find("trigger_point")
                tx = tp.attrib.get("x") if tp is not None else None
                ty = tp.attrib.get("y") if tp is not None else None
                tyaw = tp.attrib.get("yaw") if tp is not None else None
                key = "|".join([town, str(route_id), stype,
                                fnum(tx), fnum(ty), fnum(tyaw)])
                rows.append({
                    "unique_instance_id": key,
                    "scenario_group": GROUPS[stype],
                    "scenario_type": stype,
                    "town": town,
                    "route_id": route_id,
                    "scenario_xml_name": sname,
                    "trigger_x": tx,
                    "trigger_y": ty,
                    "trigger_yaw": tyaw,
                    "source_file": os.path.basename(path),
                    "notes": "",
                })

    # dedup
    seen = set()
    dedup = []
    for row in rows:
        if row["unique_instance_id"] in seen:
            continue
        seen.add(row["unique_instance_id"])
        dedup.append(row)

    fields = ["unique_instance_id", "scenario_group", "scenario_type", "town",
              "route_id", "scenario_xml_name", "trigger_x", "trigger_y",
              "trigger_yaw", "source_file", "notes"]
    for town in ("Town12", "Town13"):
        town_rows = [r for r in dedup if r["town"] == town]
        out_csv = os.path.join(OUT, f"town{town[-2:]}_manifest.csv")
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(town_rows)
        print(f"  wrote {out_csv}: {len(town_rows)} instances "
              f"(raw {sum(1 for r in rows if r['town'] == town)}, "
              f"dedup removed {sum(1 for r in rows if r['town'] == town) - len(town_rows)})")

    from collections import Counter
    for town in ("Town12", "Town13"):
        c = Counter(r["scenario_type"] for r in dedup if r["town"] == town)
        print(f"{town}: {dict(c)}")


if __name__ == "__main__":
    main()
