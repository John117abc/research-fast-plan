#!/usr/bin/env python3
"""Gate6 replay gate: reproduce online pred_wps from saved forward snapshots."""
import argparse
import csv
import glob
import os
import sys

import numpy as np
import torch

PLANT = os.path.join(os.path.dirname(__file__), "..", "..", "PlanT")
sys.path.insert(0, PLANT)
from lit_module import LitHFLM  # noqa: E402

CKPT = "/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt"


def load_model():
    net = LitHFLM.load_from_checkpoint(CKPT, map_location="cpu")
    net.eval()
    return net


def replay_one(net, npz_path):
    d = np.load(npz_path)
    batch = {
        "x_objs": torch.from_numpy(d["x_objs"]).float(),
        "idxs": torch.from_numpy(d["idxs"]).long(),
        "route_original": torch.from_numpy(d["route_original"]).float(),
        "speed_limit": torch.from_numpy(d["speed_limit"]).long(),
        "BEV": torch.from_numpy(d["BEV"]).float(),
        "y_objs": None,
    }
    with torch.inference_mode():
        (_, _, pred_plan, _) = net(batch)
    pred_path, pred_wps, _ = pred_plan
    wps_off = pred_wps.detach().squeeze(0).cpu().numpy() if pred_wps is not None else None
    return wps_off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="*",
                    default=sorted(glob.glob("outputs/gate6/snapshots/exact_bench2drive_*")))
    ap.add_argument("--n-per-dir", type=int, default=10)
    ap.add_argument("--out", default="gate6/replay_check.csv")
    ap.add_argument("--sample-size", type=int, default=None)
    a = ap.parse_args()

    net = load_model()
    print("model loaded")

    files = []
    for d in a.dirs:
        lst = sorted(glob.glob(os.path.join(d, "f*.npz")))
        if not lst:
            continue
        n = min(len(lst), a.n_per_dir)
        stride = len(lst) // n
        idxs = sorted({i * stride for i in range(n)} | {len(lst) - 1})
        files.extend([lst[i] for i in idxs])
    files = files[:a.sample_size] if a.sample_size else files
    print(f"replaying {len(files)} snapshots")

    rows = []
    for f in files:
        try:
            wps_online = np.load(f)["pred_wps_online"]
            wps_off = replay_one(net, f)
            if wps_off is None:
                rows.append({"file": os.path.basename(f), "ok": 0,
                             "max_abs_error": "", "mean_abs_error": "",
                             "note": "no wps output"})
                continue
            err = np.abs(wps_off - wps_online)
            rows.append({"file": os.path.basename(f), "ok": 1,
                         "max_abs_error": f"{err.max():.6f}",
                         "mean_abs_error": f"{err.mean():.6f}",
                         "note": ""})
        except Exception as e:
            rows.append({"file": os.path.basename(f), "ok": 0,
                         "max_abs_error": "", "mean_abs_error": "", "note": str(e)[:80]})

    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "ok", "max_abs_error", "mean_abs_error", "note"])
        w.writeheader()
        w.writerows(rows)
    oks = [r for r in rows if r["ok"]]
    print(f"wrote {a.out}: ok={len(oks)}/{len(rows)}")
    if oks:
        mx = max(float(r["max_abs_error"]) for r in oks)
        print(f"max_abs_error over ok rows = {mx:.6f} m")


if __name__ == "__main__":
    main()
