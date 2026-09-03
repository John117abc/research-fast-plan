#!/usr/bin/env bash
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

EXACT_CKPT="$WORK_DIR/PlanT/checkpoints/last_exact_holdout_1.ckpt"
REL_CKPT="$WORK_DIR/PlanT/checkpoints/last_relation_holdout_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"
TM_SEED=100
export GATE45A_TM_SEED=$TM_SEED
mkdir -p outputs/gate45a

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

run_route() {
  local N=$1
  echo "=== [$(date +%H:%M:%S)] gate45a route${N} ==="
  start_carla 2000 || { echo "  !!! CARLA-A failed route $N"; return; }
  start_carla 2001 || { echo "  !!! CARLA-B failed route $N"; return; }

  export PLANT_CHECKPOINT="$EXACT_CKPT"
  python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
    --host localhost --port 2000 --traffic-manager-port 8000 --traffic-manager-seed=$TM_SEED \
    --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
    --track=MAP --agent=PlanT/PlanT_agent.py \
    --checkpoint=outputs/gate45a_exact_route${N}.json --timeout=300 \
    > "outputs/gate45a_exact_route${N}.log" 2>&1 &
  PID_EXACT=$!

  export PLANT_CHECKPOINT="$REL_CKPT"
  python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
    --host localhost --port 2001 --traffic-manager-port 8001 --traffic-manager-seed=$TM_SEED \
    --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
    --track=MAP --agent=PlanT/PlanT_agent.py \
    --checkpoint=outputs/gate45a_relation_route${N}.json --timeout=300 \
    > "outputs/gate45a_relation_route${N}.log" 2>&1 &
  PID_REL=$!

  wait $PID_EXACT && echo "OK exact route${N}" || echo "!!! FAILED exact route ${N}"
  wait $PID_REL && echo "OK relation route${N}" || echo "!!! FAILED relation route ${N}"
}

run_route 25
run_route 28
echo "=== GATE45A DONE ==="
