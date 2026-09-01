#!/usr/bin/env bash
set -e
source /home/jiangchengxuan/anaconda3/etc/profile.d/conda.sh
conda activate plant2
cd /home/jiangchengxuan/PycharmProjects/research-safe-drive/plant2
source env_plant2.sh
export CUDA_VISIBLE_DEVICES=0
export SEED=1
export CHECKPOINT_ADDON=exact_holdout
export WANDB_MODE=offline
python -u PlanT/lit_train.py \
  user=local \
  gpus=1 \
  use_caching=false \
  model.training.input_ego_speed=true \
  model.training.max_epochs=5 \
  model.training.batch_size=128 \
  model.training.num_workers=4 \
  model.training.augment=false \
  model.training.augment_parked=false \
  model.training.input_representation=exact \
  "model.training.exclude_towns=[Town05]" \
  model.pre_training.forecastLoss_weight=0 \
  expname=exact_holdout \
  'hydra.run.dir=outputs/PlanT2_train/${expname}/${now:%Y-%m-%d_%H-%M-%S}'
