# Gate 5 · Step 1 记录：锁定官方 PlanT 2.0 Reference

> 日期：2026-09-03 · 对应文档 §1（§1.1 版本 / §1.2 配置 / §1.3 官方 checkpoint）
> 结论：**Step 1 = 通过**，无 §1.3 FAIL 触发项。

## §1.1 官方代码信息 → `gate5/official_version.txt`

- repo：fork of `autonomousvision/plant2`；origin=`John117abc/research-fast-plan`，upstream=`autonomousvision/plant2`
- **official commit = 6269e5a**（`upstream/main` == `upstream/HEAD`，本地 `main` 与其对齐）
- 当前研究分支：`relation-pilot` @ 8b6f23c（official 之后 +1 commit：relation-representation pilot infra）
- 工作区另有**未提交改动**（`PlanT/PlanT_agent.py`、`dataset.py`、`relation_features.py`、`config/model/PlanT.yaml` + outputs 日志）—— 属 Gate 4.5A/B/C+4.6 诊断，Step 2 patch audit 将正式归类
- CARLA 0.9.15 / Python 3.10.16 / PyTorch 2.6.0+cu124 / CUDA 12.4 / pl 2.5.0.post0 / 2×RTX A4000

## §1.2 官方配置保存 → `gate5/config/`

见 `gate5/config/README.md`。含：顶层 config、模型配置、user 配置、官方 ckpt cfg 导出（json）、env 脚本、研究 run 脚本。

## §1.3 官方 pretrained checkpoint 核对（epoch=029_final_1.ckpt）

文件：`/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt`（446,559,352 B）

| 核对项 | 结果 |
|---|---|
| checkpoint 可加载（当前代码 `LitHFLM.load_from_checkpoint`） | ✅ LOAD_OK（strict state_dict 校验通过） |
| checkpoint cfg 可读取 | ✅ `hyper_parameters.cfg` 完整导出 |
| input_ego_speed | False（官方 30-epoch 全量训练，不带 ego speed embedding） |
| input_bev / input_static_cars | True / True |
| training split | 无 exclude/include towns（= 全数据集，含 Town05） |
| output type / waypoints | path+wps / path_len=20 / wps_len=8 / bins_speed=8 |
| checkpoint epoch | 29（max_epochs=30，最终 epoch） |
| input_representation / remove_stop_sign_token | 键不存在 → agent 走缺省 exact / False ✅ 与当前代码兼容 |
| checkpoint 与代码结构兼容 | ✅ model/lit_module 与 official 相同（未被我方改动） |

### §1.3 通过标准核对

- [x] 官方 commit 已记录
- [x] 官方运行配置已保存
- [x] checkpoint 配置可读取
- [x] checkpoint 与代码结构兼容

### §1.3 FAIL 条件核对

- checkpoint 无法加载 → 未出现
- checkpoint cfg 与当前代码明显不兼容 → 未出现（缺省字段语义一致）
- 官方 commit 无法确认 → 未出现（6269e5a 双远端一致）
- 当前代码来源不明确 → 未出现（fork 链清晰）
