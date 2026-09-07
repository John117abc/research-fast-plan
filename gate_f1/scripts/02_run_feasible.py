#!/usr/bin/env python3
"""Gate F1 02: batch offline three-run engine metrics over recorded runs.

For every results/<scene>/run<g>.ndjson writes run<g>.summary.json and appends
one CSV row to gate_f1/results/f1_all_summary.csv.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "offline"))

import compute  # noqa: E402


def main():
    rows = []
    for ndjson in sorted(glob.glob("gate_f1/results/*/run*.ndjson")):
        scene = ndjson.split("/")[-2]
        group = os.path.basename(ndjson).replace("run", "").replace(".ndjson", "")
        r = compute.compute(ndjson)
        if r is None:
            print("skip(short)", ndjson)
            continue
        out = ndjson.replace(".ndjson", ".summary.json")
        json.dump(r, open(out, "w"), indent=1)
        flat = {"scene": r["scene"], "group": r["group"], "v0": r["v0"],
                "s0": r["s0"], "quadrant": r["quadrant"],
                "expected": r["expected"], "pass": r["pass"],
                "G0": r["G0"], "GL": r["GL"], "n_branches": r["n_branches"]}
        for k in (f"P0_{h}" for h in (2, 4, 6, 8, 10)):
            flat[k] = r["P0"][k]
        for k in (f"PL_{h}" for h in (2, 4, 6, 8, 10)):
            flat[k] = r["PL"][k]
        for k in (f"Pfree_{h}" for h in (2, 4, 6, 8, 10)):
            flat[k] = r["Pfree"][k]
        rows.append(flat)
        print(f"{scene:4s} g{group}: {r['quadrant']:22s} pass={r['pass']} "
              f"G0={r['G0']:.2f} GL={r['GL']}")
    import csv
    if rows:
        keys = list(rows[0].keys())
        with open("gate_f1/results/f1_all_summary.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"wrote f1_all_summary.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
