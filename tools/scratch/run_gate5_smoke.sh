#!/usr/bin/env bash
# Gate 5 Step 4: PlanT-Reference (official epoch=029) smoke on route25/28/29, TM seed=100.
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

OFFICIAL_CKPT="/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"
TM_SEED=100
PORT=2000
STREAM=$((PORT + 10))
TMPORT=8000
MAX_RETRY=3
mkdir -p outputs/gate5

start_carla() {
  pkill -9 -f "carla-rpc-port=$PORT" 2>/dev/null
  sleep 3
  setsid nohup "$CARLA" -quality-level=Low -carla-rpc-port=$PORT -carla-streaming-port=$STREAM </dev/null > /tmp/carla_gate5.log 2>&1 &
  for i in $(seq 1 90); do
    if python -c "import carla; c=carla.Client('localhost',$PORT); c.set_timeout(5); c.get_world()" 2>/dev/null; then
      echo "  CARLA ready (attempt $i)"; return 0
    fi
    sleep 2
  done
  echo "  CARLA NOT READY"; return 1
}

is_carla_alive() { pgrep -f "CarlaUE4-Linux-Shipping CarlaUE4 -quality-level=Low -carla-rpc-port=${PORT}" >/dev/null; }

run_route() {
  local N=$1
  for ATT in $(seq 1 "$MAX_RETRY"); do
    echo "=== [$(date +%H:%M:%S)] route${N} attempt $ATT/$MAX_RETRY (official ref, tm$TM_SEED) ==="
    start_carla || { echo "  !!! CARLA start fail route $N"; sleep 5; continue; }
    sleep 8
    export PLANT_CHECKPOINT="$OFFICIAL_CKPT"
    export GATE45A_TM_SEED=$TM_SEED
    unset GATE45B_MASK GATE45C_FORCE_DROP
    python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
      --host localhost --port $PORT --traffic-manager-port $TMPORT --traffic-manager-seed=$TM_SEED \
      --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
      --track=MAP --agent=PlanT/PlanT_agent.py \
      --checkpoint=outputs/gate5/gate5_ref_route${N}.json --timeout=300 \
      > "outputs/gate5/gate5_ref_route${N}.log" 2>&1 &
    PID=$!
    while kill -0 "$PID" 2>/dev/null; do
      if ! is_carla_alive; then
        echo "  !! CARLA died mid-run route $N (attempt $ATT) -> kill eval, retry"
        kill -9 "$PID" 2>/dev/null
        return 1
      fi
      sleep 3
    done
    wait "$PID"; RC=$?
    if [ $RC -eq 0 ] && [ -s "outputs/gate5/gate5_ref_route${N}.json" ]; then
      # capture jsonl telemetry (agent logs to outputs/gate45a)
      NEW=$(ls -t outputs/gate45a/exact_routelongest6_${N}_route0_*_tm${TM_SEED}.jsonl 2>/dev/null | head -1)
      if [ -n "$NEW" ]; then cp "$NEW" "outputs/gate5/gate5_ref_route${N}_tm${TM_SEED}.jsonl"; fi
      echo "OK official-ref route${N} (attempt $ATT)"
      return 0
    else
      echo "  !!! route $N attempt $ATT eval exit=$RC json empty -> retry"
      sleep 3
    fi
  done
  echo "!!! route $N GAVE UP after $MAX_RETRY attempts"
  return 1
}

for N in 29 25 28; do
  run_route "$N"
done
echo "=== GATE5 SMOKE DONE ==="
