#!/usr/bin/env bash
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

REL_CKPT="$WORK_DIR/PlanT/checkpoints/last_relation_holdout_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"
TM_SEED=100
mkdir -p outputs/gate45c

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

run_relation() {
  local TAG=$1 DROP=$2
  echo "=== [$(date +%H:%M:%S)] gate45c ${TAG} (drop_type4=$DROP) ==="
  start_carla 2000 || { echo "  !!! CARLA failed"; return; }
  export PLANT_CHECKPOINT="$REL_CKPT"
  export GATE45C_FORCE_DROP=$DROP
  export GATE45A_TM_SEED=$TM_SEED
  python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
    --host localhost --port 2000 --traffic-manager-port 8000 --traffic-manager-seed=$TM_SEED \
    --routes=leaderboard/data/longest6_split/longest6_25.xml \
    --track=MAP --agent=PlanT/PlanT_agent.py \
    --checkpoint=outputs/gate45c_relation_${TAG}.json --timeout=300 \
    > "outputs/gate45c_relation_${TAG}.log" 2>&1
  RC=$?
  echo "  relation ${TAG} exit=$RC"
  NEW=$(ls -t outputs/gate45a/relation_*_25_*.jsonl 2>/dev/null | head -1)
  if [ -n "$NEW" ]; then
    mv "$NEW" outputs/gate45c/relation_route25_${TAG}_tm${TM_SEED}.jsonl
  fi
}

run_relation runC0_dropOFF 0
run_relation runC1_dropON 1
echo "=== GATE45C DONE ==="
