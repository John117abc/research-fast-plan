#!/usr/bin/env python3
"""B1 freeze: environment + dataset manifest + code hashes.

usage: python gate_b1/scripts/30_freeze.py
"""
import glob
import hashlib
import os
import subprocess
import sys

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
OUT = os.path.join(B1, "freeze")
FILES = ["gate_b1/adapters/waymo_adapter.py",
         "gate_b1/scripts/00_carla_h8_audit.py",
         "gate_b1/scripts/10_waymo_check_export.py",
         "gate_b0/consequence/r1_signature.py",
         "gate_b0/action_probe/constrained_rollout.py",
         "gate_b0/action_probe/action_set.py",
         "gate_b0/consequence/relation_distance.py"]
DATA = {"json_training": "/mnt/2T_HDD/WaymoDatabase/data_json/training/*.json",
        "json_testing": "/mnt/2T_HDD/WaymoDatabase/data_json/testing/*.json",
        "tfrecord_training": "/mnt/2T_HDD/WaymoDatabase/data/training/training.tfrecord-*",
        "tfrecord_testing": "/mnt/2T_HDD/WaymoDatabase/data/testing/testing.tfrecord-*"}


def sha(p):
    return hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode()
    except Exception:  # noqa
        commit, status = "no-git", ""
    open(os.path.join(OUT, "git_commit.txt"), "w").write(commit + "\n")
    open(os.path.join(OUT, "git_status.txt"), "w").write(status)
    with open(os.path.join(OUT, "code_hashes.txt"), "w") as fh:
        for f in FILES:
            fh.write("%s  %s\n" % (sha(f), f))
    with open(os.path.join(OUT, "dataset_manifest.txt"), "w") as fh:
        for k, pat in DATA.items():
            n = len(glob.glob(pat))
            fh.write("%s: %d\n" % (k, n))
    open(os.path.join(OUT, "environment.txt"), "w").write(
        "plant2: engine/R1/CARLA audit\nwaymo_rc: TFRecord parsing only\n"
        "interface: canonical_state JSON\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
