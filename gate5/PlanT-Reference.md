# Gate 5 · 最终判定 与 PlanT-Reference 冻结

> 日期：2026-09-03 · 对应文档 §5/§7/§10

## 最终判定模板（§10）

```
Gate 5 Result: PASS

Critical Issues:
1. Research 5-epoch exact/relation 模型在 route25/28 的停车牌处可静止 ≥180s 而被
   AgentBlocked 判定（Gate 4）。官方 30-epoch 基座在相同路线可自行恢复（最长 ~30s）。
   → 该"长停→可能超时"是"训练程度 × 停车牌清除条件(<3m & <0.1m/s)"交互所致，非基座逻辑缺陷；
   但后续 Driving Equivalence（使用 research 模型）需注意此不对称卡停风险与 blocked 阈值影响。
2. 官方基座自身也会在部分停车牌低速碾过（r25 stop=1.22、r28 stop=0.877 各 1 次）→
   停车违规属基座固有行为，等价性度量需把 stop/滚动行为作为 shared-base artifact 说明。
3. 三条 route 本次各跑 1 次（TM seed=100）；同 seed 重复稳定性（FAIL-E 场景）未做压力测试，
   等价性阶段建议至少加 1-2 次重复或多种子以评估方差。
4. route29 存在固定 NPC 碰撞事件（官方与 nostop 模型均 coll≈0.6）→ 作为参照需知晓该常量碰撞。

Can PlanT be used as the reference platform? YES

Reason:
官方 PlanT 2.0 (autonomousvision/plant2 @6269e5a + epoch=029 ckpt) 在当前本地 pipeline
（含已审计 patch）下：3/3 代表性 route 100% 闭环、无 blocked、无 CARLA 崩溃；stop-sign
生命周期正常闭环；训练/在线 input、token、path+wps、controller 均核验一致；
须关闭干预默认全关、debug-only patch 不改数值行为。可作为后续研究基座并冻结为 PlanT-Reference。
```

## §5.1 PASS 九条核对
- [x] 1. 官方代码/checkpoint 来源明确（6269e5a + epoch=029 cfg 完整、可加载）
- [x] 2. 本地 patch 已完全审计（patch_audit：两层来源、A/B/C 分类、must-off 全默认关）
- [x] 3. 训练/在线 input 一致（token 结构、relation/NoStop 同源同函数）
- [x] 4. input_ego_speed 逻辑明确（官方 False/False；研究 True/True；单位 m/s 一致）
- [x] 5. stop-sign lifecycle 能正常闭环（无永久 deadlock；4+8 次交互全消失）
- [x] 6. token/route/BEV/path+wps 无明显错误（pred_wps/path 100% 可用，尺度正常）
- [x] 7. controller 能正确执行 planner 输出（r29 91% 移动、无系统踩死）
- [x] 8. 少量代表 route 正常闭环（r29/r25/r28 全 100% Completed）
- [x] 9. 无系统性 CARLA/pipeline 崩溃（3/3 无 crash、attempt 1 全成）

## §5.2 FAIL-A~E 检查
- FAIL-A（输入不一致）：未触发
- FAIL-B（核心规则状态机死锁）：官方基座未触发（无永久 deadlock）——但见 Critical Issues #1（research 模型）
- FAIL-C（controller 污染）：未触发
- FAIL-D（官方 baseline 无法闭环）：未触发（3/3 完成）
- FAIL-E（高度不稳定）：本次无证据触发（单次 seed=100）；稳定性留待多 seed/重复阶段

---

# PlanT-Reference 冻结规格（§7）

后续任何实验从该 reference 派生。

| 项 | 冻结值 |
|---|---|
| upstream repo | `autonomousvision/plant2` |
| official commit | `6269e5a`（upstream/main == upstream/HEAD；本地 main 对齐） |
| 本地研究分支 | `relation-pilot` @ `8b6f23c`（+ 未提交 Gate4.5/4.6 诊断 patch，见 patch_audit） |
| 官方 checkpoint | `/mnt/2T_HDD/PlanT2.0/checkpoints/PlanT2/epoch=029_final_1.ckpt` |
| checkpoint cfg | `input_representation=exact(缺省)`、`input_ego_speed=False`、`input_bev=True`、`input_static_cars=True`、`max_epochs=30`、`batch=128`、`lr=1e-4`、waypoints path+wps(path20/wps8/bins8, 5:1:1) |
| CARLA | 0.9.15 |
| Python / PyTorch | 3.10.16 / 2.6.0+cu124（CUDA 12.4），pl 2.5.0.post0 |
| controller | carla_garage `LateralPIDController` + `LongitudinalLinearRegressionController`（未修改） |
| route planner | leaderboard `GlobalRoutePlanner`（未修改） |
| input representation | exact（官方）；research 另有 relation 变体 |
| input_ego_speed | 官方 False；research True |
| 启用 patch | 无（全部须关闭项默认 OFF） |
| 保留但不影响行为 | Gate4.5A JSONL 日志、`draw_string` 调试覆盖层（debug-only） |
| smoke 结果 | r29/r25/r28 全部 100% Completed（详见 step4_smoke_results.md） |
| 评测入口 | `leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py`；TM seed=100；`PlanT/PlanT_agent.py` |
| 配置快照 | `gate5/config/` |
| 版本记录 | `gate5/official_version.txt` |
