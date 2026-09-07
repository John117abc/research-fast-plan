#!/usr/bin/env python3
"""Gate6 dominant-actor screening (offline).

For each valid-instance window frame, offline-baseline forward (W0) then remove
each dynamic actor token (type 1/2/6) and forward -> D_i = RMS(||dW|| over N wps).
Emits per-frame CSV rows.
"""
import argparse
import csv
import json
import os
import sys

import numpy as np
import torch

PLANT = os.path.join(os.path.dirname(__file__), "..", "..", "PlanT")
sys.path.insert(0, PLANT)
from lit_module import LitHFLM  # noqa: E402

CKPT = "/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt"
DYNAMIC_TYPES = (1, 2, 6)


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
    wps = pred_plan[1].detach().squeeze(0).cpu().numpy()
    return wps


def drop_row(d, row_idx):
    """Return a modified copy of npz fields with object row `row_idx` removed.

    row_idx is a 1-based index into the object block (row0 = padding).
    """
    x = d["x_objs"].copy()
    n_objs = x.shape[0] - 1
    keep = [0] + [i for i in range(1, x.shape[0]) if i != row_idx]
    x2 = x[keep]
    n2 = len(keep) - 1
    d2 = dict(d)
    d2["x_objs"] = x2
    d2["idxs"] = np.arange(1, n2 + 1, dtype=np.int32)[None, :]
    return d2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapdir", required=True)
    ap.add_argument("--scnlog", required=True)
    ap.add_argument("--instances", required=True)  # discovery instances csv (frozen pool)
    ap.add_argument("--route-tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-frames", type=int, default=0)
    a = ap.parse_args()

    # frozen valid instance set for this route tag: (config_name) with interaction Y
    valid = set()
    with open(a.instances) as f:
        for r in csv.DictReader(f):
            if r["route"] == a.route_tag and r["interaction"] == "Y":
                valid.add(r["config_name"])

    events = [json.loads(l) for l in open(a.scnlog)]
    events = {e["config_name"]: e for e in events if e["config_name"] in valid}
    print(f"valid instances for {a.route_tag}: {sorted(events.keys())}", flush=True)

    meta = {}
    meta_path = os.path.join(a.snapdir, "meta.jsonl")
    for line in open(meta_path):
        m = json.loads(line)
        meta[m["frame"]] = m

    net = load_model()
    print("model loaded", flush=True)

    # per-instance window frames
    inst_frames = {}
    for cfg, e in events.items():
        typ = e["type"]
        fids = []
        if typ == "HardBreakRoute":
            te = e.get("game_time") or 0.0
            for fr, m in sorted(meta.items()):
                t = fr / 20.0
                if te <= t <= te + 60:
                    fids.append(fr)
        else:
            ids = set(e.get("actor_ids", []))
            ids.discard(None)
            for fr, m in sorted(meta.items()):
                if any(act["actor_id"] in ids for act in m["actors"]):
                    fids.append(fr)
        inst_frames[cfg] = fids
        print(f"  {cfg}: window_frames={len(fids)}", flush=True)

    out_rows = []
    done = 0
    for cfg, fids in inst_frames.items():
        e = events[cfg]
        for fr in fids:
            npz_path = os.path.join(a.snapdir, f"f{fr:06d}.npz")
            if not os.path.exists(npz_path):
                continue
            d = np.load(npz_path)
            x = d["x_objs"]
            n_objs = x.shape[0] - 1
            dyn = [i for i in range(1, x.shape[0])
                   if int(round(float(x[i, 0]))) in DYNAMIC_TYPES]
            if not dyn:
                continue
            try:
                w0 = forward_wps(net, d)
            except Exception as ex:
                print("  baseline fail", npz_path, ex, flush=True)
                continue
            Ds = []
            for i in dyn:
                d2 = drop_row(d, i)
                try:
                    wi = forward_wps(net, d2)
                except Exception:
                    continue
                dif = np.linalg.norm(wi - w0, axis=1)
                Ds.append((float(np.sqrt(np.mean(dif ** 2))), i))
            Ds.sort(reverse=True)
            if not Ds:
                continue
            d1, d1_idx = Ds[0]
            d2v = Ds[1][0] if len(Ds) > 1 else 0.0
            ratio = d1 / max(d2v, 0.05)
            m = meta.get(fr, {})
            out_rows.append({
                "route": a.route_tag, "config_name": cfg,
                "scenario_group": e["type"], "frame": fr,
                "scenario_progress": -1,
                "num_dynamic_actors": len(dyn),
                "dominant_actor_id": _actor_id_of(m, d1_idx),
                "dominant_token_idx": d1_idx,
                "D1": round(d1, 5), "D2": round(d2v, 5),
                "D1_D2_ratio": round(ratio, 3),
                "pass_D1": int(d1 >= 0.20),
                "pass_ratio": int(ratio >= 1.5),
                "single_dominant": int(d1 >= 0.20 and ratio >= 1.5),
                "snapshot_path": npz_path,
            })
            done += 1
            if a.max_frames and done >= a.max_frames:
                break
        print(f"  done {cfg} ({len(out_rows)} rows so far)", flush=True)

    if not out_rows:
        print("no rows", flush=True)
        return
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {a.out}: {len(out_rows)} rows", flush=True)


def _actor_id_of(m, token_idx):
    try:
        for act in m.get("actors", []):
            if act.get("token_idx") == token_idx:
                return act.get("actor_id")
    except Exception:
        pass
    return None


if __name__ == "__main__":
    main()
