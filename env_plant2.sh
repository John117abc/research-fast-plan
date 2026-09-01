#!/usr/bin/env bash

export WORK_DIR="$HOME/PycharmProjects/research-safe-drive/plant2"
export DATA_DIR="/mnt/2T_HDD/PlanT2.0"
# 训练用 SSD 副本（HDD 随机读太慢，~6 samples/s）
export DS="/home/jiangchengxuan/data/PlanT2_SSD/PlanT_2_dataset"
# HDD 原始解压路径（备份）：
# export DS="$DATA_DIR/PlanT2_Dataset/data/PlanT2_DS/PlanT_2_dataset"
export CARLA_ROOT="$HOME/carla-0.9.15-linux"
export SCENARIO_RUNNER_ROOT="$WORK_DIR/scenario_runner_autopilot"
export LEADERBOARD_ROOT="$WORK_DIR/leaderboard_autopilot"

export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:$LEADERBOARD_ROOT:$SCENARIO_RUNNER_ROOT:$WORK_DIR/PlanT:$WORK_DIR/carla_garage:$PYTHONPATH"
export PLANT_CHECKPOINT="$DATA_DIR/checkpoints/PlanT2/epoch=029_final_1.ckpt"

# 先关闭 PlanT 可视化，减少不必要的变量
export PLANT_VIZ=""

# 训练阶段不用在线上传 wandb
export WANDB_MODE=offline