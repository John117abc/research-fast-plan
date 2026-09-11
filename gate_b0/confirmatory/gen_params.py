#!/usr/bin/env python3
"""Generate B0-C1 confirmatory parameter table: 9 cells x 8 NEW rows = 72.

New combinations within the Dev-108-validated physical ranges; no new physical
mechanism. Writes gate_b0/confirmatory/confirmatory_params.csv with an exact
`spec_json` for factory.make_f3. Run and freeze BEFORE any CARLA generation.

usage: python gate_b0/confirmatory/gen_params.py
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "gate_b0/confirmatory/confirmatory_params.csv")
MECH = {"cross_clear": "cross", "cross_stall": "cross", "cross_stall_occ": "cross",
        "lead_opt": "lead", "lead_nec": "lead", "lead_cont": "lead",
        "block_nec": "block", "block_cont": "block", "temp_opt": "temp"}
COARSE = {"cross": "cross", "lead": "lead", "block": "block_or_occupancy",
          "temp": "block_or_occupancy"}

# --- NEW parameter combinations (not in Dev-108 params_F3.yaml) ---
# cross: (d_conflict, ego_v, kind)
CROSS_CLEAR = [(48, 6, "ped"), (50, 6, "veh"), (54, 6, "ped"), (56, 6, "veh"),
               (60, 7, "ped"), (62, 7, "veh"), (48, 8, "ped"), (54, 8, "veh")]
CROSS_STALL = [(48, 6, "ped"), (52, 6, "ped"), (56, 6, "veh"), (60, 7, "ped"),
               (62, 7, "veh"), (52, 7, "ped"), (56, 8, "veh"), (60, 8, "ped")]
CROSS_STALL_OCC = [(54, 6, "ped"), (56, 6, "veh"), (58, 7, "ped"), (60, 7, "veh"),
                   (54, 8, "ped"), (62, 8, "veh"), (60, 6, "ped"), (62, 7, "ped")]
# block: (L, ego_v)
BLOCK_NEC = [(42, 6), (47, 6), (49, 7), (53, 7), (55, 8), (59, 8), (63, 9), (57, 9)]
BLOCK_CONT = [(42, 6), (47, 6), (49, 7), (53, 7), (55, 8), (59, 8), (63, 9), (57, 9)]
# lead_opt: (s0, v_lead, ego_v)
LEAD_OPT = [(49, 3.0, 6), (51, 3.5, 6), (53, 4.0, 7), (55, 2.5, 7),
            (57, 3.5, 8), (59, 2.5, 8), (61, 3.0, 9), (63, 4.0, 9)]
# lead_nec/lead_cont: (s0, v0, tc, a, ego_v)
LEAD_NEC = [(42, 6, 2.0, 2.5, 6), (47, 8, 2.5, 2.5, 6), (49, 6, 1.5, 3.0, 7),
            (53, 8, 2.0, 2.5, 7), (55, 8, 2.5, 2.5, 8), (59, 9, 2.0, 3.0, 8),
            (61, 6, 1.5, 2.5, 9), (63, 8, 2.5, 2.5, 9)]
LEAD_CONT = LEAD_NEC
# temp: (occ_s, t_leave, away_v, ego_v)
TEMP_OPT = [(53, 3.0, 8, 6), (56, 4.5, 9, 6), (59, 2.5, 11, 6), (61, 5.5, 8, 7),
            (63, 3.5, 9, 7), (57, 6.5, 11, 8), (64, 2.5, 9, 8), (62, 4.5, 11, 9)]


def spec_for(cell, row):
    if cell in ("cross_clear", "cross_stall", "cross_stall_occ"):
        d, v, kind = row
        return {"cell": cell, "ego_v": v, "d_conflict": d, "kind": kind, "_prescreen": "NA"}
    if cell in ("block_nec", "block_cont"):
        L, v = row
        return {"cell": cell, "ego_v": v, "L": L, "_prescreen": "NA"}
    if cell == "lead_opt":
        s0, vl, v = row
        return {"cell": cell, "ego_v": v, "s0": s0, "v_lead": vl, "_prescreen": "NA"}
    if cell in ("lead_nec", "lead_cont"):
        s0, v0, tc, a, v = row
        return {"cell": cell, "ego_v": v, "s0": s0, "v0": v0, "tc": tc, "a": a,
                "_prescreen": "NA"}
    if cell == "temp_opt":
        occ, tl, av, v = row
        return {"cell": cell, "ego_v": v, "occ_s": occ, "t_leave": tl, "away_v": av,
                "_prescreen": "NA"}
    raise KeyError(cell)


def main():
    table = {"cross_clear": CROSS_CLEAR, "cross_stall": CROSS_STALL,
             "cross_stall_occ": CROSS_STALL_OCC, "block_nec": BLOCK_NEC,
             "block_cont": BLOCK_CONT, "lead_opt": LEAD_OPT, "lead_nec": LEAD_NEC,
             "lead_cont": LEAD_CONT, "temp_opt": TEMP_OPT}
    rows = []
    for cell in table:
        for k, r in enumerate(table[cell], 1):
            spec = spec_for(cell, r)
            mech = MECH[cell]
            cid = "c1_%s_%02d" % (cell, k)
            rows.append({
                "confirm_id": cid, "cell_id": cell, "fine_mechanism": cell,
                "coarse_mechanism": COARSE[mech], "mech": mech,
                "ego_v0": spec["ego_v"],
                "kind": spec.get("kind", ""), "d_conflict": spec.get("d_conflict", ""),
                "s0": spec.get("s0", ""), "v0": spec.get("v0", ""),
                "v_lead": spec.get("v_lead", ""), "tc": spec.get("tc", ""),
                "decel_value": spec.get("a", ""), "L": spec.get("L", ""),
                "occ_s": spec.get("occ_s", ""), "t_leave": spec.get("t_leave", ""),
                "away_v": spec.get("away_v", ""),
                "left_lane_actor_params": ("queue" if cell == "cross_stall_occ"
                                           else ("queue" if cell == "lead_cont" else "")),
                "spec_json": json.dumps(spec, sort_keys=True),
            })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (%d rows)" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
