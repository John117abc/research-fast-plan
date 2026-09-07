#!/usr/bin/env python3
"""Gate6 I1-I5 interventions + Response Signature for selected states v2 (offline).

For each state: W0 = offline baseline forward; then on the dominant actor token:
  I1 x/y += 2m along own heading ; I2 x/y -= 2m ; I3 speed*1.20 ; I4 speed*0.80 ;
  I5 remove token.
dWk = Wk - W0 (flattened over all pred_wps). S = concat(vec(dW1..dW5)).
Saves gate6/signatures/<state_id>.npz (W0..W5) + gate6/signatures_summary.csv
"""
import argparse
import csv
import json
import math
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
    return net.to("cuda" if torch.cuda.is_available() else "cpu")


def forward_wps(net, d):
    batch = {
        "x_objs": torch.from_numpy(d["x_objs"]).float().to(net.device),
        "idxs": torch.from_numpy(d["idxs"]).long().to(net.device),
        "route_original": torch.from_numpy(d["route_original"]).float().to(net.device),
        "speed_limit": torch.from_numpy(d["speed_limit"]).long().to(net.device),
        "BEV": torch.from_numpy(d["BEV"]).float().to(net.device),
        "y_objs": None,
    }
    with torch.inference_mode():
        (_, _, pred_plan, _) = net(batch)
    return pred_plan[1].detach().squeeze(0).cpu().numpy()


def drop_row(d, row_idx):
    x = d["x_objs"].copy()
    keep = [0] + [i for i in range(1, x.shape[0]) if i != row_idx]
    d2 = dict(d)
    d2["x_objs"] = x[keep]
    d2["idxs"] = np.arange(1, len(keep), dtype=np.int32)[None, :]
    return d2


def move_along_heading(d, row_idx, dx2, dy2):
    x = d["x_objs"].copy()
    row = x[row_idx]
    theta = math.radians(float(row[3]))
    x[row_idx, 1] = row[1] + dx2 * math.cos(theta)
    x[row_idx, 2] = row[2] + dx2 * math.sin(theta)
    d2 = dict(d)
    d2["x_objs"] = x
    return d2


def scale_speed(d, row_idx, factor):
    x = d["x_objs"].copy()
    x[row_idx, 4] = float(x[row_idx, 4]) * factor
    d2 = dict(d)
    d2["x_objs"] = x
    return d2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", default="gate6/selected_states_v2.csv")
    ap.add_argument("--out", default="gate6/signatures")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    net = load_model()
    print("model loaded", flush=True)
    states = list(csv.DictReader(open(a.states)))
    summary = []
    for s in states:
        path = s.get("snapshot_path", "")
        if not path or not os.path.isfile(path):
            # reconstruct path from state csv route/frame if missing
            path = _guess_path(s)
        if not os.path.isfile(path):
            print("skip missing", s["state_id"], flush=True)
            continue
        d = np.load(path)
        row_idx = int(s["dominant_token_idx"])
        try:
            w0 = forward_wps(net, d)
            variants = {
                "I1": move_along_heading(d, row_idx, 2.0, 0.0),
                "I2": move_along_heading(d, row_idx, -2.0, 0.0),
                "I3": scale_speed(d, row_idx, 1.20),
                "I4": scale_speed(d, row_idx, 0.80),
            }
            # I5 uses drop_row with row_idx in original x_objs
            w5 = forward_wps(net, drop_row(d, row_idx))
            wk = {"W0": w0}
            for k, dk in variants.items():
                wk[k] = forward_wps(net, dk)
            wk["I5"] = w5
            sig = []
            for k in ("I1", "I2", "I3", "I4", "I5"):
                sig.append((wk[k] - w0).reshape(-1))
            S = np.concatenate(sig)
            np.savez(os.path.join(a.out, f"{s['state_id']}.npz"), **{k: v for k, v in wk.items()},
                     signature=S)
            summary.append({
                "state_id": s["state_id"], "scenario_group": s["scenario_group"],
                "unique_instance_id": s["unique_instance_id"],
                "dominant_actor_type": s.get("dominant_actor_type", ""),
                "dominant_belongs_to_target_scenario": s.get("dominant_belongs_to_target_scenario", ""),
                "signature_path": os.path.join(a.out, f"{s['state_id']}.npz"),
                "signature_norm": round(float(np.linalg.norm(S)), 4),
                "W0_max": round(float(np.abs(w0).max()), 4),
            })
            print("done", s["state_id"], "norm", round(float(np.linalg.norm(S)), 3), flush=True)
        except Exception as ex:
            print("ERR", s["state_id"], ex, flush=True)

    with open("gate6/signatures_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["state_id", "scenario_group", "unique_instance_id",
                                          "dominant_actor_type",
                                          "dominant_belongs_to_target_scenario",
                                          "signature_path", "signature_norm", "W0_max"])
        w.writeheader()
        w.writerows(summary)
    print("wrote signatures_summary.csv rows", len(summary))


def _guess_path(s):
    route = s["unique_instance_id"].split("|")[0]
    snapdirs = {
        "route10": "outputs/gate6/snapshots/exact_town12_route10_route0_09_04_14_40_59",
        "route14": "outputs/gate6/snapshots/exact_town12_route14_route0_09_04_15_52_40",
        "route3": "outputs/gate6/snapshots/exact_town12_route3_discovery_route0_09_04_17_01_56",
    }
    return os.path.join(snapdirs[route], f"f{int(s['frame']):06d}.npz")


if __name__ == "__main__":
    main()
