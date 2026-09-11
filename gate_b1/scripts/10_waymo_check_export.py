#!/usr/bin/env python3
"""B1-0 Step 2 (+ canonical export): JSON <-> official TFRecord consistency.

Run with the `waymo_rc` env. For a seeded sample of data_json/training files:
  - locate the source tfrecord (name prefix) and the record index (filename suffix)
  - parse that record with scenario_pb2 and compare key quantities to the JSON
  - export a canonical_state JSON (raw parse only; NO R1/collision/feasible logic)

usage: python gate_b1/scripts/10_waymo_check_export.py --n 12 --seed 0
writes gate_b1/results/b1_0/step2_json_tfrecord/{check.csv,summary.json}
       gate_b1/canonical/<scenario_id>.json
"""
import argparse
import csv
import glob
import json
import os
import random
import sys

import numpy as np
import tensorflow as tf
from waymo_open_dataset.protos import scenario_pb2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B1 = os.path.join(ROOT, "gate_b1")
JSON_DIR = "/mnt/2T_HDD/WaymoDatabase/data_json/training"
TFR_DIR = "/mnt/2T_HDD/WaymoDatabase/data/training"
OUT = os.path.join(B1, "results/b1_0/step2_json_tfrecord")
CANON = os.path.join(B1, "canonical")


def parse_json_name(name):
    # tfrecord-00000-of-01000_325.json -> ("tfrecord-00000-of-01000", 325)
    base = os.path.basename(name)[:-len(".json")]
    prefix, idx = base.rsplit("_", 1)
    return prefix, int(idx)


def load_record(tfrecord_path, index):
    ds = tf.data.TFRecordDataset(tfrecord_path, compression_type="")
    for i, data in enumerate(ds):
        if i == index:
            sc = scenario_pb2.Scenario()
            sc.ParseFromString(data.numpy())
            return sc
    return None


def canonical(sc, prefix, index):
    sdc = sc.tracks[sc.sdc_track_index]
    lanes = []
    for mf in sc.map_features:
        if mf.WhichOneof("feature_data") == "lane":
            lanes.append({"id": int(mf.id),
                          "type": int(mf.lane.type),
                          "polyline": [[float(p.x), float(p.y), float(p.z)] for p in mf.lane.polyline],
                          "entry_lanes": list(mf.lane.entry_lanes),
                          "exit_lanes": list(mf.lane.exit_lanes)})
    def track(t):
        return {"id": int(t.id), "object_type": int(t.object_type),
                "frames": [{"x": float(s.center_x), "y": float(s.center_y), "z": float(s.center_z),
                            "heading": float(s.heading), "vx": float(s.velocity_x),
                            "vy": float(s.velocity_y), "valid": bool(s.valid),
                            "length": float(s.length), "width": float(s.width),
                            "height": float(s.height)} for s in t.states]}
    return {"scenario_id": sc.scenario_id, "source_tfrecord": prefix, "record_index": index,
            "timestamps_seconds": list(sc.timestamps_seconds),
            "current_time_index": int(sc.current_time_index),
            "sdc_track_index": int(sc.sdc_track_index),
            "ego": track(sdc),
            "actors": [track(t) for t in sc.tracks if t.id != sdc.id],
            "lanes": lanes,
            "objects_of_interest": list(sc.objects_of_interest),
            "tracks_to_predict": [{"track_index": int(x.track_index), "difficulty": int(x.difficulty)}
                                  for x in sc.tracks_to_predict]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CANON, exist_ok=True)
    files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    random.Random(a.seed).shuffle(files)
    files = files[: a.n]
    rows = []
    for f in files:
        prefix, idx = parse_json_name(f)
        tfp = os.path.join(TFR_DIR, prefix.replace("tfrecord-", "training.tfrecord-", 1))
        j = json.load(open(f))
        sc = load_record(tfp, idx)
        r = {"json_file": os.path.basename(f), "tfrecord": os.path.basename(tfp),
             "record_index": idx}
        if sc is None:
            r.update({"scenario_id_match": False, "note": "record not found"})
            rows.append(r)
            continue
        c = canonical(sc, prefix, idx)
        json.dump(c, open(os.path.join(CANON, "%s.json" % c["scenario_id"]), "w"))
        si = c["sdc_track_index"]
        je = j["objects"][si]
        pe = c["ego"]["frames"][c["current_time_index"]]
        r.update({
            "scenario_id_match": bool(j["scenario_id"] == c["scenario_id"]),
            "sdc_id_match": bool(int(je["id"]) == c["ego"]["id"]),
            "n_tracks_json": len(j["objects"]), "n_tracks_tf": len(c["actors"]) + 1,
            "n_frames_json": len(je["position"]), "n_frames_tf": len(c["ego"]["frames"]),
            "cur_idx_json_valid": bool(je["valid"][c["current_time_index"]]),
            "cur_idx_tf_valid": bool(pe["valid"]),
            "ego_dx": round(abs(je["position"][c["current_time_index"]]["x"] - pe["x"]), 5),
            "ego_dy": round(abs(je["position"][c["current_time_index"]]["y"] - pe["y"]), 5),
            "ego_dheading": round(abs(je["heading"][c["current_time_index"]] - pe["heading"]), 5),
            "ego_dvx": round(abs(je["velocity"][c["current_time_index"]]["x"] - pe["vx"]), 5),
            "ego_dvy": round(abs(je["velocity"][c["current_time_index"]]["y"] - pe["vy"]), 5),
            "bbox_len_match": round(abs(float(je["length"]) - pe["length"]), 5),
            "bbox_wid_match": round(abs(float(je["width"]) - pe["width"]), 5),
            "n_lanes_json": sum(1 for x in j["roads"] if x["type"] == "lane"),
            "n_lanes_tf": len(c["lanes"]),
            "future_valid_tf": sum(1 for x in c["ego"]["frames"][c["current_time_index"]:] if x["valid"]),
        })
        rows.append(r)
        print("checked", c["scenario_id"], "id_match", r["scenario_id_match"])
    with open(os.path.join(OUT, "check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = all(r.get("scenario_id_match") and r.get("sdc_id_match") and
             r.get("ego_dx", 9) < 1e-3 and r.get("ego_dy", 9) < 1e-3 and
             r.get("n_frames_json") == r.get("n_frames_tf") for r in rows)
    summary = {"n_checked": len(rows), "all_consistent": bool(ok)}
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
