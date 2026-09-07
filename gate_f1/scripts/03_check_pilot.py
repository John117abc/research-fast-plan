#!/usr/bin/env python3
"""Gate F1 03: pilot round-1 check (protocol acceptance).

Per scenario (5 deterministic groups): report expected vs observed quadrant,
pass count and threshold >=4/5. Non-passing runs are listed, not deleted.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "offline"))

from compute import EXPECTED, classify  # noqa: E402

SCENES = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "G1", "G2", "G3"]
HOR = (2, 4, 6, 8, 10)


def main():
    rows = list(csv.DictReader(open("gate_f1/results/f1_all_summary.csv")))
    print(f"{'scene':5s} {'exp':6s} | {'quadrants observed':38s} | pass  thr")
    summary = {}
    for sc in SCENES:
        rr = [r for r in rows if r["scene"] == sc]
        if not rr:
            print(f"{sc:5s}  no rows")
            continue
        n_pass = sum(1 for r in rr if r["pass"] == "True")
        quads = {}
        for r in rr:
            quads[r["quadrant"]] = quads.get(r["quadrant"], 0) + 1
        qs = ", ".join(f"{k}×{v}" for k, v in sorted(quads.items()))
        n = len(rr)
        ok = n_pass >= max(4, int(0.8 * n))
        print(f"{sc:5s} {EXPECTED[sc]:6s} | {qs:38s} | {n_pass}/{n}   {ok}")
        summary[sc] = {"n_pass": n_pass, "ok": ok,
                       "groups": [r["group"] for r in rr if r["pass"] != "True"]}
    print("\nF1 round-1 PASS if each scene >=4/5.")
    print("Non-passing runs to inspect (kept):",
          {k: v["groups"] for k, v in summary.items() if v["groups"]})


if __name__ == "__main__":
    main()
