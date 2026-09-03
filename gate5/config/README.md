# gate5/config — 实际运行配置快照

来源目录：仓库根 + `PlanT/config/` + `tools/scratch/`，生成于 2026-09-03（Gate 5 Step 1.2）。

| 文件 | 来源 | 说明 |
|---|---|---|
| `config.yaml` | `PlanT/config/config.yaml` | 训练顶层 hydra 配置（默认 user=…/model=PlanT） |
| `PlanT_model.yaml` | `PlanT/config/model/PlanT.yaml` | **模型配置**：waypoints=path+wps(path20/wps8/bins8, 5:1:1)、training 默认(input_ego_speed=False, input_bev=True, input_static_cars=True, **input_representation=exact, remove_stop_sign_token=False**, exclude_towns=[]) |
| `user_local.yaml` | `PlanT/config/user/local.yaml` | 本机 user 覆盖：`working_dir` |
| `official_ckpt_cfg.json` | 官方 ckpt `hyper_parameters.cfg` 导出（`resolve=False`） | 官方 30-epoch 训练配置原文 |
| `env_plant2.sh` | 仓库根 | 环境变量：DS/CARLA_ROOT/SCENARIO_RUNNER_ROOT/LEADERBOARD_ROOT/PYTHONPATH/PLANT_CHECKPOINT/WANDB_MODE |
| `run_exact.sh` | `tools/scratch/` | 研究 Exact-holdout 训练启动（5 epoch, Town05 排除, ego_speed=true, exact） |
| `run_relation.sh` | `tools/scratch/` | 研究 Relation-holdout 训练启动（同上，relation） |
| `run_gate46_train.sh` | `tools/scratch/` | Gate4.6 NoStop（exact/relation）训练启动 |
| `run_gate46_eval.sh` | `tools/scratch/` | Gate4.6 评测启动（TM seed=100, 并行双 CARLA） |

## 官方 ckpt cfg 关键值（epoch=029_final_1.ckpt）

```
model.training: input_ego_speed=False, input_bev=True, input_static_cars=True,
                max_epochs=30, batch_size=128, lr=1e-4, num_workers=16,
                augment=True, augment_parked=True, range=50, range_factor_front=2
model.waypoints: path+wps / linear / path_len=20 / wps_len=8 / bins_speed=8 / 5:1:1
无 input_representation / remove_stop_sign_token / exclude_towns / include_towns 键
（agent 侧缺省→ representation=exact, remove_stop_sign_token=False）
```

## 官方 vs 研究配置差异要点

| 项 | 官方(epoch=029) | 研究 holdout(exact/relation) |
|---|---|---|
| epochs | 30（全量） | 5 |
| Town 排除 | 无 | Town05 排除 |
| input_ego_speed | False | True |
| augment / parked | True / True | False / False |
| forecastLoss_weight | 1 | 0 |
| representation | exact（缺省） | exact / relation |
| remove_stop_sign_token | False（缺省） | False / True(NoStop) |
