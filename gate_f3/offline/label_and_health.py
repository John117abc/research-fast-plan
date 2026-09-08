#!/usr/bin/env python3
"""Gate F3 offline labelling + dataset health check (run AFTER 108 generation).

Reads gate_f3/data/raw/<mech>/<cell>/row<r>.ndjson, runs the frozen engine
three passes (P0/PL/Pfree), stores .summary.json, and builds
gate_f3/data/dataset_labels.csv plus a health report. Empirical structure
labels are authoritative; cell-intent mismatches are reported and KEPT.
"""
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "..", "gate_f1", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "..", "gate_f1", "offline"))

import compute  # noqa: E402

INTENT = {"cross_clear": "LateralOptional", "cross_stall": "LateralNecessary",
          "cross_stall_occ": "Contingency/Wait", "lead_opt": "LateralOptional",
          "lead_nec": "LateralNecessary", "lead_cont": "Contingency/Wait",
          "block_nec": "LateralNecessary", "block_cont": "Contingency/Wait",
          "temp_opt": "LateralOptional"}


def main():
    out = []
    rows = []
    for f in sorted(glob.glob("gate_f3/data/raw/*/*/row*.ndjson")):
        r = compute.compute(f)
        if r is None:
            print("SKIP(short)", f)
            continue
        parts = f.split("/")
        mech, cell = parts[3], parts[4]
        row = int(parts[5].replace("row", "").replace(".ndjson", ""))
        intent = INTENT[cell]
        fine = r["fine"]
        pl_none = sum(1 for x in fine["PL"] if x is None)
        pf_below = sum(1 for x in fine["Pfree"] if x < 0.05)
        r["mech"] = mech
        r["cell"] = cell
        r["row"] = row
        r["intent"] = intent
        r["match"] = (r["quadrant"] == intent)
        r["pl_none_frac"] = round(pl_none / len(fine["PL"]), 3)
        r["pf_low_frac"] = round(pf_below / len(fine["Pfree"]), 3)
        # save summary sidecar (without heavy raw arrays beyond fine)
        json.dump(r, open(f.replace(".ndjson", ".summary.json"), "w"))
        slim = {k: r[k] for k in
                ("mech", "cell", "row", "quadrant", "intent", "match",
                 "G0", "GL", "v0", "s0", "pl_none_frac", "pf_low_frac")}
        rows.append(slim)
        out.append(f)
    with open("gate_f3/data/dataset_labels.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            rr = dict(r)
            for k in ("G0", "GL"):
                rr[k] = round(rr[k], 3) if rr[k] is not None else ""
            w.writerow(rr)
    # health report
    print(f"total annotated: {len(rows)}")
    from collections import Counter
    print("quadrant dist:", dict(Counter(r["quadrant"] for r in rows)))
    print("mech dist:", dict(Counter(r["mech"] for r in rows)))
    print("intent-match per cell:")
    for cell in sorted(INTENT):
        rr = [r for r in rows if r["cell"] == cell]
        if rr:
            mm = sum(1 for r in rr if r["match"])
            qq = Counter(r["quadrant"] for r in rr)
            print(f"  {cell:16s} {mm}/{len(rr)} match  quadrants {dict(qq)}")
    mism = [r for r in rows if not r["match"]]
    print("intent-mismatch rows (KEPT):", [(r["cell"], r["row"], r["quadrant"]) for r in mism])
    n_mask = sum(1 for r in rows if r["pl_none_frac"] > 0)
    n_pf = sum(1 for r in rows if r["pf_low_frac"] > 0.5)
    print(f"rows with some PL-infeasible t (mask>0): {n_mask}/{len(rows)}; "
          f"rows with Pfree<eps on >half horizon: {n_pf}")
    json.dump({"n": len(rows), "quadrant_dist": dict(Counter(r["quadrant"] for r in rows)),
               "mech_dist": dict(Counter(r["mech"] for r in rows)),
               "mismatch": mism, "pl_mask_rows": n_mask, "pf_low_rows": n_pf},
              open("gate_f3/data/health.json", "w"), indent=1)
    print("wrote dataset_labels.csv + health.json")


if __name__ == "__main__":
    main()
