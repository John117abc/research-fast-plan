from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

roots = [
    Path("leaderboard/data/longest6_split"),
    Path("leaderboard/data/bench2drive_split"),
]

for root in roots:
    if not root.exists():
        continue

    print("\n" + "#" * 100)
    print("ROOT:", root)
    print("#" * 100)

    for xml_file in sorted(root.glob("*.xml")):
        try:
            tree = ET.parse(xml_file)
        except Exception as e:
            print("PARSE_FAILED", xml_file, e)
            continue

        routes = list(tree.getroot().iter("route"))
        for route in routes:
            town = route.attrib.get("town", "UNKNOWN")
            route_id = route.attrib.get("id", "UNKNOWN")

            scenario_counter = Counter()
            for scenario in route.iter("scenario"):
                stype = scenario.attrib.get("type", "UNKNOWN")
                scenario_counter[stype] += 1

            print(f"\nXML={xml_file} route_id={route_id} town={town}")
            print(f"scenario_total={sum(scenario_counter.values())}")
            for stype, n in sorted(scenario_counter.items()):
                print(f"  {stype:45s} {n}")
