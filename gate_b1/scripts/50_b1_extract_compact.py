#!/usr/bin/env python3
"""B1 Step 7 extractor (waymo_rc): compact canonical for formal B1 selection.

Parses raw WOMD training TFRecords and writes a compact canonical JSON per
scenario (ego + actors at 0.5 s over [idx0..idx0+16], lanes with official
left_neighbors). Parsing/map only; NO R1/collision/feasible logic.

usage: python gate_b1/scripts/50_b1_extract_compact.py --files 100 --out gate_b1/canonical_b1
"""
import argparse
import glob
import json
import os
import sys

import tensorflow as tf
from waymo_open_dataset.protos import scenario_pb2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TFR_DIR = "/mnt/2T_HDD/WaymoDatabase/data/training"
IDX0, STEP, NFR = 10, 5, 16   # decision frame, 0.5 s step, 16 steps -> 8 s


def compact(sc, prefix, index):
    sdc = sc.tracks[sc.sdc_track_index]
    ex, ey = sdc.states[IDX0].center_x, sdc.states[IDX0].center_y

    def frames(t):
        out = []
        for k in range(NFR + 1):
            fi = IDX0 + k * STEP
            if fi >= len(t.states):
                break
            s = t.states[fi]
            out.append({"x": s.center_x, "y": s.center_y, "heading": s.heading,
                        "vx": s.velocity_x, "vy": s.velocity_y, "valid": bool(s.valid)})
        return out

    lanes = []
    for mf in sc.map_features:
        if mf.WhichOneof("feature_data") != "lane":
            continue
        lc = mf.lane
        pts = [[p.x, p.y] for p in lc.polyline]
        if not pts:
            continue
        dmin = min((px - ex) ** 2 + (py - ey) ** 2 for px, py in pts) ** 0.5
        if dmin > 80.0:
            continue
        pts = pts[::3] + [pts[-1]]
        def nb(n):
            return {"feature_id": int(n.feature_id), "self_start_index": int(n.self_start_index),
                    "self_end_index": int(n.self_end_index),
                    "neighbor_start_index": int(n.neighbor_start_index),
                    "neighbor_end_index": int(n.neighbor_end_index)}
        lanes.append({"id": int(mf.id), "type": int(lc.type), "polyline": pts,
                      "left_neighbors": [nb(n) for n in lc.left_neighbors],
                      "right_neighbors": [nb(n) for n in lc.right_neighbors]})
    actors = []
    for t in sc.tracks:
        if t.id == sdc.id:
            continue
        s0 = t.states[IDX0]
        if not s0.valid:
            continue
        if ((s0.center_x - ex) ** 2 + (s0.center_y - ey) ** 2) ** 0.5 > 120.0:
            continue
        actors.append({"id": int(t.id), "type": int(t.object_type),
                       "length": s0.length, "width": s0.width, "frames": frames(t)})
    return {"scenario_id": sc.scenario_id, "source_tfrecord": prefix, "record_index": index,
            "current_time_index": int(sc.current_time_index),
            "sdc_track_index": int(sc.sdc_track_index),
            "ego": {"id": int(sdc.id), "length": sdc.states[IDX0].length,
                    "width": sdc.states[IDX0].width, "frames": frames(sdc)},
            "actors": actors, "lanes": lanes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=100)
    ap.add_argument("--out", default=os.path.join(ROOT, "gate_b1/canonical_b1"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(TFR_DIR, "training.tfrecord-*")))[: a.files]
    n = 0
    for fp in files:
        prefix = os.path.basename(fp).replace("training.", "")
        ds = tf.data.TFRecordDataset(fp, compression_type="")
        for idx, data in enumerate(ds):
            sc = scenario_pb2.Scenario()
            sc.ParseFromString(data.numpy())
            if sc.sdc_track_index >= len(sc.tracks):
                continue
            if not sc.tracks[sc.sdc_track_index].states[IDX0].valid:
                continue
            c = compact(sc, prefix, idx)
            json.dump(c, open(os.path.join(a.out, "%s.json" % c["scenario_id"]), "w"))
            n += 1
        print("done", os.path.basename(fp), "total", n)
    print("wrote", n, "scenarios to", a.out)


if __name__ == "__main__":
    main()
