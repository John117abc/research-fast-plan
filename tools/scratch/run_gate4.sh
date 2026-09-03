#!/usr/bin/env bash
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh
export DISPLAY=:1

EXACT_CKPT="$WORK_DIR/PlanT/checkpoints/last_exact_holdout_1.ckpt"
REL_CKPT="$WORK_DIR/PlanT/checkpoints/last_relation_holdout_1.ckpt"
CARLA="$HOME/carla-0.9.15-linux/CarlaUE4.sh"

restart_carla() {
  pkill -9 -f "CarlaUE4-Linux-Shipping" 2>/dev/null
  pkill -9 -f "CarlaUE4.sh" 2>/dev/null
  sleep 3
  setsid nohup "$CARLA" -quality-level=Low </dev/null > /tmp/carla_server.log 2>&1 &
  for i in $(seq 1 90); do
    if python -c "import carla; c=carla.Client('localhost',2000); c.set_timeout(5); c.get_world()" 2>/dev/null; then
      echo "CARLA ready (attempt $i)"
      return 0
    fi
    sleep 2
  done
  echo "CARLA NOT READY"
  return 1
}

ROUTES="24 25 26 27 28 29"

for N in $ROUTES; do
  for rep in exact relation; do
    CKPT=$EXACT_CKPT
    [ "$rep" = "relation" ] && CKPT=$REL_CKPT
    OUT="outputs/ood_${rep}_route${N}.json"
    echo "=== [$(date +%H:%M:%S)] ${rep} longest6_${N}.xml ==="
    restart_carla || { echo "!!! CARLA FAILED before ${rep} route ${N}"; continue; }
    export PLANT_CHECKPOINT="$CKPT"
    if python -u leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
      --routes=leaderboard/data/longest6_split/longest6_${N}.xml \
      --track=MAP --agent=PlanT/PlanT_agent.py --checkpoint="$OUT" --timeout=300 \
      > "outputs/eval_ood_${rep}_route${N}.log" 2>&1; then
      echo "OK ${rep} route${N}"
    else
      echo "!!! FAILED ${rep} route ${N} (exit $?)"
    fi
  done
done
echo "=== GATE4 DONE ==="
