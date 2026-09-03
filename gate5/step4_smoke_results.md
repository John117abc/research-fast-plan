# Gate 5 · Step 4 记录：PlanT-Reference 闭环 Smoke 结果

> 日期：2026-09-03 · 对应文档 §4
> 模型：**官方 pretrained** `epoch=029_final_1.ckpt`（30-epoch 全量、exact、input_ego_speed=False、input_bev/static=True）
> 条件：TM seed=100；Relation/NoStop/Path-mask/force-drop 全默认关闭（patch audit 背书）；单 CARLA 顺序执行；route29→25→28；`tools/scratch/run_gate5_smoke.sh`
> 运行：3 条 route 全部 attempt 1 成功，无 CARLA crash、无重试。

## §4.3 指标表

| Route | Status | Route % | Composed | Collision vehicle | Stop infraction | 时长(s) | CARLA crash |
|---|---:|---:|---:|---:|---:|---:|---|
| 29（正常参照） | **Completed** | 100.00 | 60.00 | 0.596（1 次） | 0 | 143.3 | 无 |
| 25（历史问题点） | **Completed** | 100.00 | 23.04 | 1.22（1 次） | 1.22（1 次） | 464.2 | 无 |
| 28（历史问题点） | **Completed** | 100.00 | 48.00 | 0.877（1 次） | 0.877（1 次） | 349.0 | 无 |

## 保存的遥测（ego_speed / pred_wps / mean_speed_raw / type4 / next stop / controller）

```
outputs/gate5/gate5_ref_route29.json|.log|_tm100.jsonl
outputs/gate5/gate5_ref_route25.json|.log|_tm100.jsonl
outputs/gate5/gate5_ref_route28.json|.log|_tm100.jsonl
```

## 关键解读

1. **官方基座可正常闭环**：3/3 条 route 100% 完成、无 blocked、无 CARLA 崩溃。→ 不触发 §5.2 FAIL-D。
2. **Stop-sign 生命周期正常**（§3.2）：route25 的 8 处、route28 的 4 处停车牌交互 token 全部正常消失，多数能"原地 cleared"，个别为长停（≤30s）后驶过；从不永久卡死。→ 不触发 FAIL-B。
3. **与历史对比**：Gate 4 中 research exact/relation（5-epoch）在 route25/28 出现 blocked（45.29%/9.65%、100%/39.31%）；**官方 30-epoch 模型在同一条路线全部通过**。→ 佐证此前 blocked 源于"模型训练不足 + 停车牌清除条件的交互"，**非基座逻辑缺陷**；但注意 research 模型确实更易卡停，见 Step 5 Critical Issues。
4. **碰撞一致性锚点**：route29 官方 composed=60.00 且 coll≈0.6，与 Gate4.6 两条 nostop 模型在 route29 的 60.00/0.6 完全一致 → route29 存在固定 NPC 碰撞场景，作为等价性参照稳定。
5. 官方模型同样会低速碾停（stop_infraction r25=1.22、r28=0.877 各 1 次）→ 停车违规是基座固有行为（两臂等受影响），Cross-Scenario Equivalence 度量需纳入说明。

## §4 smoke 判定 = **通过**
- 无系统性 CARLA/pipeline 崩溃；代表性 route（29/25/28）均正常闭环。
- 官方 PlanT-Reference 可作为后续研究运行基座（冻结见 `gate5/PlanT-Reference.md`）。
