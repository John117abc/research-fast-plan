import os
from collections import Counter
from pathlib import Path

root = os.environ["DS"] + "/data"
boxes = list(Path(root).rglob("boxes"))

counter = Counter()
for p in boxes:
    route_dir = p.parent
    town = route_dir.name.split("_")[0]
    counter[town] += 1

print("Route count by town:")
for town, n in sorted(counter.items()):
    print(f"{town:12s} {n}")
