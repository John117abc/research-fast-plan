#!/usr/bin/env bash
# Gate6 smoke: run one route with PlanT-Reference (official ckpt), TM seed=100.
# Env: ROUTE_XML=<path> TAG=<short tag, e.g. town12_route3>
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

OFFICIAL_CKPT="/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"
ROUTE_XML="${ROUTE_XML:?need ROUTE_XML}"
TAG="${TAG:?need TAG}"
TM_SEED=100
PORT=2000
TMPORT=8000
STREAM=$((PORT + 10))
OUTD="outputs/gate6"
mkdir -p "$OUTD" gate6/smoke
export GATE6_SMOKE=1
export GATE6_SNAP=1
export GATE6_SCNLOG=1
export GATE6_SCNLOG_PATH="$OUTD/scnlog_${TAG}.jsonl"
export GATE45A_TM_SEED=$TM_SEED
export PLANT_CHECKPOINT="$OFFICIAL_CKPT"
unset GATE45B_MASK GATE45C_FORCE_DROP

echo "=== gate6 smoke $TAG start $(date +%H:%M:%S) ==="
pkill -9 -f "carla-rpc-port=$PORT" 2>/dev/null; sleep 3
setsid nohup "$CARLA" -quality-level=Low -carla-rpc-port=$PORT -carla-streaming-port=$STREAM </dev/null > /tmp/carla_gate6.log 2>&1 &
for i in $(seq 1 90); do
  python -c "import carla; c=carla.Client('localhost',$PORT); c.set_timeout(5); c.get_world()" 2>/dev/null && { echo "CARLA ready ($i)"; break; }
  sleep 2
done

python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --host localhost --port $PORT --traffic-manager-port $TMPORT --traffic-manager-seed=$TM_SEED \
  --routes="$ROUTE_XML" --track=MAP --agent=PlanT/PlanT_agent.py \
  --checkpoint="$OUTD/smoke_${TAG}.json" --timeout=300 \
  > "$OUTD/smoke_${TAG}.log" 2>&1
RC=$?

# move newest matching jsonl
NEW=$(ls -t outputs/gate45a/exact_*tm${TM_SEED}.jsonl 2>/dev/null | head -1)
if [ -n "$NEW" ]; then cp "$NEW" "gate6/smoke/smoke_${TAG}_tm${TM_SEED}.jsonl"; fi
pkill -9 -f "carla-rpc-port=$PORT" 2>/dev/null
echo "=== gate6 smoke $TAG done RC=$RC $(date +%H:%M:%S) ==="
