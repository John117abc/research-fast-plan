#!/usr/bin/env bash
# Gate 4.6: Exact-NoStop / Relation-NoStop training (smoke then full, dual-GPU parallel)
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
source env_plant2.sh

COMMON_ARGS="user=local gpus=1 use_caching=false \
  hydra.run.dir=outputs/\${exp_folder_name}/\${expname}/\${now:%Y-%m-%d_%H-%M-%S} \
  model.training.input_ego_speed=true \
  model.training.augment=false model.training.augment_parked=false \
  model.training.remove_stop_sign_token=true \
  model.pre_training.forecastLoss_weight=0"

run_smoke() {
  local GPU=$1 REPR=$2 ADDON=$3 EXP=$4
  echo "=== smoke $REPR on GPU $GPU ==="
  CUDA_VISIBLE_DEVICES=$GPU SEED=1 WANDB_MODE=offline CHECKPOINT_ADDON=$ADDON \
    python -u PlanT/lit_train.py $COMMON_ARGS \
    overfit=5 model.training.max_epochs=1 model.training.batch_size=8 model.training.num_workers=2 \
    model.training.input_representation=$REPR \
    expname=$EXP \
    > "outputs/gate46_smoke_${REPR}.log" 2>&1
  echo "smoke $REPR exit=$?"
}

run_full() {
  local GPU=$1 REPR=$2 ADDON=$3 EXP=$4
  echo "=== full train $REPR on GPU $GPU ==="
  CUDA_VISIBLE_DEVICES=$GPU SEED=1 WANDB_MODE=offline CHECKPOINT_ADDON=$ADDON \
    python -u PlanT/lit_train.py $COMMON_ARGS \
    model.training.max_epochs=5 model.training.batch_size=128 model.training.num_workers=4 \
    model.training.input_representation=$REPR \
    "model.training.exclude_towns=[Town05]" \
    expname=$EXP \
    > "outputs/gate46_train_${REPR}.log" 2>&1
  echo "train $REPR exit=$?"
}

echo "########## SMOKE PHASE ##########"
run_smoke 0 exact exact_nostop_smoke exact_nostop_smoke &
P1=$!
run_smoke 1 relation relation_nostop_smoke relation_nostop_smoke &
P2=$!
wait $P1 $P2
echo "########## FULL TRAIN PHASE ##########"
run_full 0 exact exact_nostop_holdout exact_nostop_holdout &
F1=$!
run_full 1 relation relation_nostop_holdout relation_nostop_holdout &
F2=$!
wait $F1 $F2
echo "=== GATE46 TRAINING DONE ==="
