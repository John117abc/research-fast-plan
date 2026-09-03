# Gate 4.5A/B/C + Gate 4.6：Blocked 归因与 Relation 表示有效性 实验记录

> 实验工程：CARLA 0.9.15 + PlanT 2.0 + Exact / Relation-v0（5 epoch pilot，Town05 holdout）
> 记录日期：2026-09-01
> 关键结论：**Gate 4 OOD 中观察到的 "blocked" 主要来自共享的停车牌 token 死锁（工程机制），而非 Relation 表示本身的失效；移除该干扰后，Relation-v0 保留了与 Exact 相当的基本闭环驾驶能力。**

---

## 0. 起点：Gate 4 OOD 原始结果（带停车牌模型，TM seed=100）

使用 `last_exact_holdout_1.ckpt` / `last_relation_holdout_1.ckpt`（均 5 epoch、exclude Town05、input_ego_speed=True）。

| route | Exact status | Exact route% | Exact blocked | Exact coll | Relation status | Relation route% | Relation blocked | Relation coll |
|---|---|---:|---:|---:|---|---:|---:|---:|
| 24 | Failed | 36.18 | 1.24 | 0 | Failed | 36.22 | 1.24 | 0 |
| 25 | Failed | 45.29 | 1.35 | 0 | Failed | 9.65 | 6.32 | 0 |
| 26 | ❌ CARLA 崩溃 | — | — | — | ❌ CARLA 崩溃 | — | — | — |
| 27 | ❌ CARLA 崩溃 | — | — | — | ❌ CARLA 崩溃 | — | — | — |
| 28 | Completed | 100.00 | 0 | 0.9 | Failed | 39.31 | 2.23 | 0 |
| 29 | Completed | 100.00 | 0 | 0.6 | Completed | 100.00 | 0 | 0.6 |

观测到的现象：Relation 作为"路口第一辆车"时容易 blocked；有前车时通常能继续走。

---

## 1. Gate 4.5A：零训练诊断（定位 blocked 发生时的模型内部状态）

**方法**：不加任何干预，只给 `PlanT_agent.py` 加在线 JSONL 日志（creep 前的 `desired_speed_raw`/`mean_speed_raw`、真实 `next_light_state/dist`、`num_type4/5_tokens`、dangerous relations + 原始 x/y、`has_lead_vehicle`）。TM seed=100，route25/28。

**关键发现**：
1. **控制层排除**：blocked 时 `mean_speed_raw` 持续低值、且 throttle 有 ON 帧 → 是 **planner 输出**接近静止 waypoint，不是控制器问题。
2. **卡点位置**：两个 blocked 都在**停车牌**（`next_stop_dist=0`、`t4=1`、`t5=0`），**不是绿灯路口**（H1 的"绿灯无 token"场景未捕获，保持未验证）。
3. **停车牌 token 从不消失**：整个卡死窗口 `type4` token 100% 持续在输入中（`cleared_stop_sign` 从未触发）。
4. **模型逐帧振荡**：同一输入下 `mean_speed_raw` 在 ~2.9 / ~0.31 交替、`hazard_brake` 0/1 交替 → throttle/brake 打架，车原地不动（无法 commit 前进）。
5. **存在 off-path 假威胁**（相关项，后经 4.5B 证伪为因果）：
   - 相邻车道 / 后方车被 bounding-circle 代理判为 `mc≈-0.04~-0.05`（预测重叠）、`tcpa≈0.7s`
   - raw 几何证实全部 `in_path=False`（侧向偏移 2.5~5.5m）
6. **A/B 判别**：Exact 在同一停车牌停 ~70s 后**最终通过**，Relation 永久卡死（180s 后被 AgentBlockedTest 终止）。

**暴露的代码机制（Root Cause）**：
```
cleared_stop_sign 清除条件要求 distance_to_stop_sign（trigger_volume）< 3m
+ 模型因 type=4 token 在输入中而不肯向前蠕动
→ Ego 永远到不了 <3m 清除范围
→ cleared_stop_sign 永不触发
→ type=4 token 永不消失
→ 模型持续收到"仍需停车"约束
→ Stop-Sign Token Deadlock
```
该机制为 Exact/Relation **共享**；Exact 有时能靠 planner 输出强行走过阈值恢复，Relation 更容易陷入并维持死锁。

---

## 2. Gate 4.5B：Path / Interaction Relevance 因果干预 → **H2 被证伪**

**假设 H2**：off-path false threat（被几何 relation 判为高危险的横向/后方车）压制了 planner，导致 waypoint 收缩与 blocked。

**方法**：最小因果干预——仅在线把「top-5 dangerous ∩ in_path=False ∩ 非 lead」对象从 planner input 移除（corridor 用 route waypoints，half_width=2.5m，不用 pred_path）。A/B 同一代码，唯一差异是 mask ON/OFF。route25 / relation / TM seed=100。

**结果**：

| 指标 | Run A (mask OFF) | Run B (mask ON) |
|---|---:|---:|
| Status | Failed | Failed |
| Route % | 9.65 | 9.59 |
| Blocked | 6.32 | 6.36 |
| 时长 | 250s | 255s |
| num_masked（最大） | 0 | 5 |
| 停车牌处 mean_speed_raw | 1.57 | 1.36 |

Run B **确实删除全部 5 个 off-path 假威胁**（`d_path` 均 >2.5m、非 lead、`num_objects_after=18`），但：
- blocked 不变、route% 不变、`mean_speed_raw` 不恢复、pred_wps 振荡模式完全不变。

**判定：H2 不成立（§13 结论 C）。** 移除 off-path 交互假威胁不能解除 blocked。→ Gate 4.5A 中的"假威胁"是相关而非因果。停止 Path Relevance 扩展。

---

## 3. Gate 4.5C：Stop-Sign Token Deadlock 因果干预 → **H3 确认**

**假设 H3**：持续存在的 `type=4` 停车牌 token 与 `cleared_stop_sign` 自然清除条件共同形成死锁，是 route25 blocked 的直接机制。

**方法**：deadlock detector（`type4 在输入 ∧ 速度<0.1 持续≥2s ∧ distance_to_stop_sign≥3m ∧ 2s 内距离变化<0.2m`）触发后锁存 `debug_force_clear`，仅在线从 planner input 删除 type=4；`cleared_stop_sign` 原代码零改动。C0/C1 同一代码，唯一差异 drop ON/OFF。route25 / relation / TM seed=100。

**结果**：

| 指标 | C0 (drop OFF) | C1 (drop ON) |
|---|---:|---:|
| Status | Failed | **Completed** |
| Route % | 9.65 | **100.00** |
| Blocked | 6.32 | **0.00** |
| 时长 | 250s | 424s |
| Collision vehicle | 0 | **2.4（3次）** |
| Stop violation | 0 | **5** |
| deadlock 检出后 type4 实际删除 | — | 100%（after=0） |

C1 流程：deadlock 检出（~f931）→ type4 删除 → 模型恢复前进 → 通过停车牌 → **跑完整个 route25**。

**判定：H3 因果成立（§14 结论 A）。机制链闭环：**
```
persistent type=4 → 自然清除条件无法满足 → deadlock → blocked
force remove type=4 → planner 恢复 → progress 恢复 → blocked 解除
```

**关键安全副作用**：粗暴删除 token 也删掉了"停车义务"信号 → 模型像"没有停车牌"一样直冲路口 → 3 次碰撞 + 5 次停车违规。**说明正确修复不是"删 token"，而是"停车义务完成后的 Permission/放行信号"（R_rule）。**

---

## 4. Gate 4.6：Exact-NoStop vs Relation-NoStop（训练+在线同时删 type=4）

**目的**：公平移除共享的停车牌死锁干扰，直接检验 **Relation-v0 在 5 epoch 下是否保留接近 Exact 的基本闭环驾驶能力**（Representation Viability / Decision Sufficiency）。

**方法**：
- 新增共享过滤函数 `filter_planner_tokens`（`relation_features.py`），`dataset.py`（训练）与 `PlanT_agent.py`（在线）共用，`remove_stop_sign_token` 存入 checkpoint cfg → 训练/在线天然一致（避免 distribution shift）。
- 训练两个新模型：Exact-NoStop / Relation-NoStop，均 5 epoch、seed=1、exclude Town05、其余配置与 §18 完全一致（仅 representation 不同）。
- 评测：route25/28/29，TM seed=100。

**训练结果**：

| 模型 | 最终 loss_all | checkpoint |
|---|---:|---|
| Exact-NoStop | 0.511 | `last_exact_nostop_holdout_1.ckpt` |
| Relation-NoStop | 0.505 | `last_relation_nostop_holdout_1.ckpt` |

（原带停车牌模型参考：exact 0.504 / relation 0.487。NoStop 损失略升，符合"去掉一类输入"的预期；Relation-NoStop 与 Exact-NoStop 训练损失接近。）

**sanity 全部通过**：单元测试、双 smoke、checkpoint cfg（`remove_stop_sign_token=True`）、dataset 采样 type4=0。

**评测结果（TM seed=100）**：

| 指标 | r25 Exact-NS | r25 Rel-NS | r28 Exact-NS | r28 Rel-NS | r29 Exact-NS | r29 Rel-NS |
|---|---|---:|---:|---:|---:|---:|---:|
| Status | Completed | Completed | Completed | Completed | Completed | Completed |
| Route % | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| Driving Score | 2.17 | 1.30 | 8.26 | 4.25 | 60.00 | 60.00 |
| Blocked | 0 | 0 | 0 | 0 | 0 | 0 |
| Collision vehicle | 2.4 | 3.0 | 1.8 | 3.5 | 0.6 | 0.6 |
| Stop violation | 5 | 5 | 4 | 4 | 0 | 0 |
| 时长 (s) | 448 | 441 | 641 | 358 | 138 | 139 |
| num_type4_tokens | 0 | 0 | 0 | 0 | 0 | 0 |

**前后对比（Original 带停车牌 vs NoStop）**：

| | r25 Exact | r25 Rel | r28 Exact | r28 Rel | r29 Exact | r29 Rel |
|---|---|---|---|---|---|---|
| Original Route% | 45.29 | 9.65 | 100.00 | 39.31 | 100.00 | 100.00 |
| **NoStop Route%** | **100.00** | **100.00** | **100.00** | **100.00** | **100.00** | **100.00** |
| Original Blocked | 1.35 | 6.32 | 0 | 2.23 | 0 | 0 |
| **NoStop Blocked** | **0** | **0** | **0** | **0** | **0** | **0** |
| Original Collision | 0 | 0 | 0.9 | 0 | 0.6 | 0.6 |
| NoStop Collision | 2.4 | 3.0 | 1.8 | 3.5 | 0.6 | 0.6 |

---

## 5. Gate 4.6 判定（§17 情况 B 为主，含安全警示）

| 维度 | 结果 |
|---|---|
| ① Progress | **相等**：双模型 3 条路线全 100% 完成、blocked=0（原模型 relation 9.65%/39.31%、exact 45.29% blocked）|
| ② Safety | Exact-NoStop 略好：r25 coll 2.4 vs 3.0；r28 coll 1.8 vs 3.5；**r29 完全相同（0.6/0.6）** |
| ③ Planner Behavior | 无死锁振荡（blocked=0）；**Relation 更主动**（msr median ~2.3，r28 用时 358s vs Exact 641s），Exact 更保守（停得多、撞得少）|
| ④ route29 等价性 | **完全一致**（score 60.00、coll 0.6、dur 138/139s、msr median 16.05/15.80）|

**主结论（正面 — 情况 B）**：移除停车牌死锁后，**Relation-NoStop 保留与 Exact-NoStop 相当的基本闭环驾驶能力**。Progress 完全打平、route29 行为等价、无 blocked。这证实：**Gate 4 OOD 的 blocked 主要是共享停车牌死锁工程问题，不是 Relation 表示失效**。支持继续研究 Driving Relational Bottleneck。

**安全警示（部分情况 A）**：无停车牌信息被迫冲路口时，**Relation 比 Exact 更易碰撞**（r25/r28）。Relation 更激进且缺规则信号时隐式路口安全判断更弱 → **Relation 比 Exact 更需要"规则完成/放行"信号**（呼应 Gate 4.5C）。

**副作用说明**：NoStop 两模型都冲停车牌（stop violation 5/4），属预期（输入剥离了对应规则）。Collision 是本次"非停车牌安全"差异的代理指标，解读时注意其来源是"冲停车牌后与横向车相撞"。

---

## 6. 整体机制总结（诊断链）

```
Gate 4 OOD "blocked" 现象
   │
   ├─ Gate 4.5A（零训练日志）：定位到停车牌处 planner 振荡 + type4 永不消失
   │
   ├─ Gate 4.5B（Path mask 干预）：H2(off-path 假威胁) 证伪 —— 删假威胁无效
   │
   └─ Gate 4.5C（type4 drop 干预）：H3(停车牌 token 死锁) 确认 —— 删 token 解除 blocked，
       但暴露安全副作用（冲停车牌 → 碰撞）
        │
        └─ Gate 4.6（训练+在线同删 type4）：公平检验表示本身
             → Relation 保留基本驾驶能力（viability 成立），
               但缺规则信号时 Relation 更易碰撞（需要 R_rule/Permission）
```

**一条主线**：Relation-v0 当前的 blocked 失败不能归因于"低维关系思想错误"或"交互关系缺 Path Relevance"，而是：
1. 共享的 stop-sign token 死锁（工程机制，导致两模型都 blocked，Relation 更易陷入）；
2. Relation 更依赖显式规则信号——一旦规则对象处理不当（死锁）或缺失（NoStop），Relation 要么卡死、要么比 Exact 更激进。

---

## 7. 已确认的附带工程发现

1. **`cleared_stop_sign` 清除条件依赖 trigger_volume 距离 <3m**，而 Ego 因 token 在输入中不肯蠕动到该范围 → 死锁。这是 Exact/Relation 共享的代码级问题。
2. **CARLA 0.9.15 并行双实例有启动竞态**：第二实例的 TM（traffic-manager）绑定可能因服务器未完全初始化而 bind 失败；修复为启动后 sleep 10s + 错峰启动评估器。route26/27 的 SignalizedJunction 场景 segfault（`Signal 11`）为 CARLA 自身崩溃，仍未解决（相关路线暂时避开）。
3. **同 seed 非完全确定**：Exact r28 两次都完成但耗时差异大（Gate4 497s vs gate45a 890s）→ 后续稳定性结论需多 TM seed（100~104）验证。

---

## 8. 建议下一步

1. **多 TM seed 验证 Gate 4.6 viability**（seed 100~104 × route25/28）：统计 `P(completion)` / `P(blocked)` / collision，排除 seed=100 偶然。
2. **正式设计 R_rule（Rule Completion / Permission）**：stop-satisfied 后提供"已停车、可通行"的低维信号（而非删 token），用 Safety + Progress 双指标回归 route25/28/29。
3. 附带：修 `cleared_stop_sign` 的 trigger_volume 距离判定（工程修复，可让两模型自然脱离死锁）；route26/27 的 CARLA 崩溃另行排查。

---

## 附：关键文件与产物

- 方案文档：`Gate4_5A_路口第一车Blocked零训练诊断方案_修正版.md`、`Gate4.5B_Path_Interaction_Relevance_机制闭环执行说明_修正版.md`、`Gate4.5C_Stop_Sign_Token_Deadlock_因果闭环执行方案_修正版.md`、`Gate4.6_Exact_NoStop_vs_Relation_NoStop_表示有效性对比实验.md`
- 代码改动（均在 `PlanT/`，debug/开关默认关闭）：`PlanT_agent.py`（日志、deadlock detector、4.5B/4.5C 门控、`remove_stop_sign_token`）、`dataset.py`（NoStop 过滤）、`relation_features.py`（`filter_planner_tokens`）、`config/model/PlanT.yaml`（`remove_stop_sign_token`）
- Checkpoint：`last_exact_holdout_1.ckpt`、`last_relation_holdout_1.ckpt`（原模型）；`last_exact_nostop_holdout_1.ckpt`、`last_relation_nostop_holdout_1.ckpt`（NoStop）
- 结果 JSON：`outputs/gate45a_*`、`outputs/gate45b_*`、`outputs/gate45c_*`、`outputs/gate46_*_route*.json`
- 诊断 JSONL：`outputs/gate45a|45b|45c|46/*.jsonl`
