#!/usr/bin/env python3
"""Extract a single <route id=... town=...> element from a routes XML into its own file."""
import argparse
import copy
import xml.etree.ElementTree as ET


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--town", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tree = ET.parse(a.src)
    root = tree.getroot()
    match = None
    for r in root.iter("route"):
        if r.attrib.get("id") == a.route_id:
            if a.town is None or r.attrib.get("town") == a.town:
                match = r
                break
    if match is None:
        raise SystemExit(f"route id={a.route_id} town={a.town} not found in {a.src}")

    new_root = ET.Element("routes")
    new_root.append(copy.deepcopy(match))
    # ensure output dir
    import os
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    ET.ElementTree(new_root).write(a.out, encoding="utf-8", xml_declaration=True)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
