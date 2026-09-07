#!/usr/bin/env python3
"""Gate6 14: intervention active/noise QC.

For each state: replay noise = RMS(W0_offline - pred_wps_online) from snapshot.
Per intervention block r_k = RMS(W_k - W0). active_k if r_k >= 3*noise (else
marked inactive; also report r_k < noise as 'below-noise').
Emits gate6/intervention_qc.csv + active-rate summary.
"""
import csv
import math
import os

import numpy as np


def rms_flat(arr):
    return float(np.sqrt(np.mean(np.asarray(arr, dtype=float) ** 2)))


def main():
    rows = []
    sigdir = "gate6/signatures"
    for r in csv.DictReader(open("gate6/selected_states_v3.csv")):
        p = os.path.join(sigdir, f"{r['state_id']}.npz")
        d = np.load(p)
        w0 = d["W0"]
        # replay noise vs online (saved in snapshot npz pred_wps_online)
        snap = r["unique_instance_id"].split("|")[0]
        import glob
        snappaths = {
            "route10": "outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59",
            "route14": "outputs/gate6/snapshots/exact_town12_route14_route0_09_04_15_52_40",
            "route3": "outputs/gate6/snapshots/exact_town12_route3_discovery_route0_09_04_17_01_56",
        }
        sp = os.path.join(snappaths[snap], f"f{int(r['frame']):06d}.npz")
        try:
            sd = np.load(sp)
            online = sd["pred_wps_online"] if "pred_wps_online" in sd else None
        except Exception:
            online = None
        noise = rms_flat(w0 - online) if online is not None else None
        blocks = {}
        for k in ("I1", "I2", "I3", "I4", "I5"):
            blocks[k] = rms_flat(d[k] - w0)
        rec = {"state_id": r["state_id"], "scenario_group": r["scenario_group"],
               "unique_instance_id": r["unique_instance_id"],
               "replay_noise_rms": round(noise, 6) if noise is not None else ""}
        for k in ("I1", "I2", "I3", "I4", "I5"):
            rec[f"rms_{k}"] = round(blocks[k], 4)
            if noise is not None:
                rec[f"active_{k}"] = int(blocks[k] >= 3.0 * noise)
                rec[f"below_noise_{k}"] = int(blocks[k] < noise)
            else:
                rec[f"active_{k}"] = ""
                rec[f"below_noise_{k}"] = ""
        rows.append(rec)

    flds = ["state_id", "scenario_group", "unique_instance_id", "replay_noise_rms"] + \
           [f"rms_{k}" for k in ("I1", "I2", "I3", "I4", "I5")] + \
           [f"active_{k}" for k in ("I1", "I2", "I3", "I4", "I5")] + \
           [f"below_noise_{k}" for k in ("I1", "I2", "I3", "I4", "I5")]
    with open("gate6/intervention_qc.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flds)
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    have_noise = [r for r in rows if r["replay_noise_rms"] != ""]
    print(f"rows={n} (with replay noise {len(have_noise)})")
    for k in ("I1", "I2", "I3", "I4", "I5"):
        act = sum(1 for r in rows if str(r[f"active_{k}"]) == "1")
        blw = sum(1 for r in rows if str(r[f"below_noise_{k}"]) == "1")
        print(f"{k}: active(>=3*noise)={act}/{n}  below-noise={blw}/{n}")
    if have_noise:
        print("replay_noise_rms median=%.5f max=%.5f" % (
            sorted(float(r['replay_noise_rms']) for r in have_noise)[len(have_noise) // 2],
            max(float(r['replay_noise_rms']) for r in have_noise)))


if __name__ == "__main__":
    main()
