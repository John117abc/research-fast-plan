#!/usr/bin/env bash
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

EXACT_CKPT="$WORK_DIR/PlanT/checkpoints/last_exact_holdout_1.ckpt"
REL_CKPT="$WORK_DIR/PlanT/checkpoints/last_relation_holdout_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"
MAX_RETRY=3

start_carla() {
  local PORT=$1
  pkill -9 -f "carla-rpc-port=$PORT" 2>/dev/null
  sleep 3
  local STREAM=$((PORT + 10))
  setsid nohup "$CARLA" -quality-level=Low -carla-rpc-port=$PORT -carla-streaming-port=$STREAM </dev/null > /tmp/carla_server_${PORT}.log 2>&1 &
  for i in $(seq 1 90); do
    if python -c "import carla; c=carla.Client('localhost',$PORT); c.set_timeout(5); c.get_world()" 2>/dev/null; then
      echo "  CARLA port $PORT ready (attempt $i)"
      return 0
    fi
    sleep 2
  done
  echo "  CARLA port $PORT NOT READY"
  return 1
}

is_carla_alive() {
  local PORT=$1
  pgrep -f "CarlaUE4-Linux-Shipping CarlaUE4 -quality-level=Low -carla-rpc-port=${PORT}" >/dev/null
}

monitor() {
  local PE=$1 PR=$2
  while kill -0 "$PE" 2>/dev/null || kill -0 "$PR" 2>/dev/null; do
    if ! is_carla_alive 2000 && kill -0 "$PE" 2>/dev/null; then
      echo "  !! CARLA-2000 (exact) DIED while eval running -> abort attempt"
      kill -9 "$PE" 2>/dev/null; kill -9 "$PR" 2>/dev/null
      return 1
    fi
    if ! is_carla_alive 2001 && kill -0 "$PR" 2>/dev/null; then
      echo "  !! CARLA-2001 (relation) DIED while eval running -> abort attempt"
      kill -9 "$PE" 2>/dev/null; kill -9 "$PR" 2>/dev/null
      return 1
    fi
    sleep 3
  done
  return 0
}

check_done() {
  local f
  for f in "$@"; do
    if [ ! -f "$f" ] || [ "$(stat -c%s "$f" 2>/dev/null)" -lt 2000 ]; then
      return 1
    fi
  done
  return 0
}

ROUTES="25 26 27 28 29"

for N in $ROUTES; do
  DONE=0
  for ATT in $(seq 1 "$MAX_RETRY"); do
    echo "=== [$(date +%H:%M:%S)] longest6_${N}.xml (parallel) attempt $ATT/$MAX_RETRY ==="
    start_carla 2000 || { echo "  !!! CARLA-A failed before route $N"; sleep 5; continue; }
    start_carla 2001 || { echo "  !!! CARLA-B failed before route $N"; sleep 5; continue; }

    export PLANT_CHECKPOINT="$EXACT_CKPT"
    python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
      --host localhost --port 2000 --traffic-manager-port 8000 \
      --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
      --track=MAP --agent=PlanT/PlanT_agent.py \
      --checkpoint=outputs/ood_exact_route${N}.json --timeout=300 \
      > "outputs/eval_ood_exact_route${N}.log" 2>&1 &
    PID_EXACT=$!

    export PLANT_CHECKPOINT="$REL_CKPT"
    python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
      --host localhost --port 2001 --traffic-manager-port 8001 \
      --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
      --track=MAP --agent=PlanT/PlanT_agent.py \
      --checkpoint=outputs/ood_relation_route${N}.json --timeout=300 \
      > "outputs/eval_ood_relation_route${N}.log" 2>&1 &
    PID_REL=$!

    if monitor "$PID_EXACT" "$PID_REL"; then
      wait "$PID_EXACT"; OK_EXACT=$?
      wait "$PID_REL";  OK_REL=$?
      if check_done "outputs/ood_exact_route${N}.json" "outputs/ood_relation_route${N}.json" && [ $OK_EXACT -eq 0 ] && [ $OK_REL -eq 0 ]; then
        echo "OK exact route${N} (attempt $ATT)"
        echo "OK relation route${N} (attempt $ATT)"
        DONE=1
        break
      else
        echo "  !!! route $N attempt $ATT: evals exited (exact=$OK_EXACT rel=$OK_REL) but CARLA/result suspect -> retry"
        sleep 3
      fi
    else
      echo "  !!! route $N attempt $ATT: CARLA crash detected -> retry"
      sleep 3
    fi
  done
  [ $DONE -eq 1 ] || echo "!!! route $N GAVE UP after $MAX_RETRY attempts"
done
echo "=== GATE4 PARALLEL DONE ==="
