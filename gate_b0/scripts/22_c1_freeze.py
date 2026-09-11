#!/usr/bin/env python3
"""B0-C1 freeze: record hashes of params, R1/distance/stats code, env BEFORE
any CARLA generation. After this, code must not change.

usage: python gate_b0/scripts/22_c1_freeze.py
"""
import hashlib
import os
import subprocess
import sys

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
OUT = os.path.join(B0, "results/confirmatory/freeze")

FILES = {
    "r1_impl_sha256.txt": [
        "gate_b0/consequence/r1_signature.py",
        "gate_b0/action_probe/constrained_rollout.py",
        "gate_b0/action_probe/action_set.py",
    ],
    "distance_impl_sha256.txt": ["gate_b0/consequence/relation_distance.py"],
    "b0r3_stats_sha256.txt": ["gate_b0/scripts/19_r3_stats.py"],
    "confirmatory_params_sha256.txt": ["gate_b0/confirmatory/confirmatory_params.csv"],
    "road_segment_sha256.txt": ["gate_f0/road_segment.json"],
}


def sha(path):
    h = hashlib.sha256()
    h.update(open(os.path.join(ROOT, path), "rb").read())
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode()
    except Exception as e:  # noqa
        commit, status = "no-git", str(e)
    open(os.path.join(OUT, "git_commit.txt"), "w").write(commit + "\n")
    open(os.path.join(OUT, "git_status.txt"), "w").write(status)
    for name, files in FILES.items():
        with open(os.path.join(OUT, name), "w") as fh:
            for f in files:
                fh.write("%s  %s\n" % (sha(f), f))
    try:
        v = subprocess.check_output(
            [sys.executable, "-c", "import carla;print(getattr(carla,'__version__','?'))"],
            cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa
        v = "unknown"
    open(os.path.join(OUT, "carla_version.txt"), "w").write(v + "\n")
    open(os.path.join(OUT, "timestamp.txt"), "w").write(
        subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode())
    print("froze to", OUT)
    for f in sorted(os.listdir(OUT)):
        print(" ", f)


if __name__ == "__main__":
    main()
