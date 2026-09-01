import csv
import gzip
import json
import os
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(os.environ["DS"]) / "data"
CONFIG = Path("PlanT/config/model/PlanT.yaml")
OUTPUT = Path("outputs/dataset_distribution.csv")

if not ROOT.is_dir():
    raise RuntimeError(f"Dataset root not found: {ROOT}")

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

wps_len = int(cfg["waypoints"]["wps_len"])
seq_len = int(cfg["training"]["seq_len"])


def get_town(route_dir: Path) -> str:
    return route_dir.name.split("_")[0]


def get_scenario(route_dir: Path) -> str:
    return route_dir.parent.name


def usable_by_results(route_dir: Path) -> bool:
    """
    尽量镜像 PlanTDataset 中 results.json.gz 的主要过滤逻辑。
    注意：官方 Dataset 还会检查 SLURM log 中的 silent crash；
    本统计脚本不依赖作者集群日志，因此这里称 usable_by_results，
    最终实际 trainable route 数可能略少。
    """
    result_path = route_dir / "results.json.gz"
    if route_dir.name.startswith("FAILED_") or not result_path.is_file():
        return False

    try:
        with gzip.open(result_path, "rt", encoding="utf-8") as f:
            r = json.load(f)
    except Exception:
        return False

    bad_status = {
        "Failed - Agent couldn't be set up",
        "Failed",
        "Failed - Simulation crashed",
        "Failed - Agent crashed",
    }
    if r.get("status") in bad_status:
        return False

    scores = r.get("scores", {})
    score_composed = float(scores.get("score_composed", 0.0))

    infractions = r.get("infractions", {})
    min_speed = infractions.get("min_speed_infractions", [])
    num_infractions = int(r.get("num_infractions", 0))

    # 与 PlanTDataset 的主要逻辑一致：
    # 非满分 route 只有在全部 infraction 都是 min-speed 时才允许保留。
    if score_composed < 100.0 and not (num_infractions == len(min_speed)):
        return False

    return True


rows = []
boxes_dirs = sorted(ROOT.rglob("boxes"))

for boxes_dir in boxes_dirs:
    route_dir = boxes_dir.parent
    town = get_town(route_dir)
    scenario = get_scenario(route_dir)

    frame_count = len(list(boxes_dir.glob("*.json.gz")))
    usable = usable_by_results(route_dir)

    # PlanTDataset:
    # range(5, num_seq - wps_len - seq_len - 2)
    # 因此样本数约为 num_seq - wps_len - seq_len - 7。
    approx_samples = max(0, frame_count - wps_len - seq_len - 7) if usable else 0

    rows.append({
        "scenario": scenario,
        "town": town,
        "route": route_dir.name,
        "raw_route": 1,
        "usable_by_results": int(usable),
        "frames": frame_count,
        "approx_train_samples": approx_samples,
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [
        "scenario", "town", "route", "raw_route", "usable_by_results",
        "frames", "approx_train_samples"
    ])
    writer.writeheader()
    writer.writerows(rows)


def print_counter(title, counter):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    for key, value in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"{str(key):65s} {value:10d}")


raw_by_town = Counter()
usable_by_town = Counter()
raw_by_scenario = Counter()
usable_by_scenario = Counter()
samples_by_town_scenario = Counter()
routes_by_town_scenario = Counter()

for r in rows:
    raw_by_town[r["town"]] += 1
    raw_by_scenario[r["scenario"]] += 1

    if r["usable_by_results"]:
        usable_by_town[r["town"]] += 1
        usable_by_scenario[r["scenario"]] += 1
        routes_by_town_scenario[(r["town"], r["scenario"])] += 1
        samples_by_town_scenario[(r["town"], r["scenario"])] += r["approx_train_samples"]

print(f"Dataset root: {ROOT}")
print(f"Raw route folders: {len(rows)}")
print(f"CSV saved to: {OUTPUT}")
print(f"wps_len={wps_len}, seq_len={seq_len}")

print_counter("1. Raw routes by Town", raw_by_town)
print_counter("2. Usable-by-results routes by Town", usable_by_town)
print_counter("3. Raw routes by Scenario Type", raw_by_scenario)
print_counter("4. Usable-by-results routes by Scenario Type", usable_by_scenario)
print_counter("5. Usable Route Count: Town × Scenario", routes_by_town_scenario)
print_counter("6. Approx. Train Samples: Town × Scenario", samples_by_town_scenario)
