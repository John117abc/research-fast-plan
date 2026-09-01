from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

roots = [
    Path("leaderboard/data/longest6_split"),
    Path("leaderboard/data/bench2drive_split"),
]

result = defaultdict(list)

for root in roots:
    if not root.exists():
        continue
    for xml_file in root.glob("*.xml"):
        try:
            tree = ET.parse(xml_file)
        except Exception:
            continue

        towns = {
            route.attrib.get("town")
            for route in tree.getroot().iter("route")
            if route.attrib.get("town")
        }

        for town in towns:
            result[town].append(str(xml_file))

for town in sorted(result):
    print(f"\n[{town}]")
    for f in result[town][:20]:
        print("  ", f)
