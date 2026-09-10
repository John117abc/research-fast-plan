#!/usr/bin/env bash
# Gate B0-0 freeze environment. Read-only; writes hashes under results/discovery/env_freeze.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
OUT="gate_b0/results/discovery/env_freeze"
mkdir -p "$OUT"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  { git rev-parse HEAD; git status --porcelain; } > "$OUT/git_commit.txt"
else
  echo "not a git repo" > "$OUT/git_commit.txt"
fi

(conda run -n plant2 pip freeze 2>/dev/null || pip freeze) > "$OUT/pip_freeze.txt" || true

conda run -n plant2 python - <<'PY' > "$OUT/carla_version.txt" 2>/dev/null || echo "carla import failed" > "$OUT/carla_version.txt"
import carla
print(getattr(carla, "__version__", "unknown"))
PY

sha256sum gate_f0/road_segment.json > "$OUT/road_segment_sha256.txt"
find gate_f0/feasible -name '*.py' -print0 | sort -z | xargs -0 sha256sum > "$OUT/gate_f0_core_sha256.txt"
find gate_b0/config -type f -print0 | sort -z | xargs -0 sha256sum > "$OUT/gate_b0_config_sha256.txt"

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OUT/timestamp.txt"
echo "wrote $OUT"
