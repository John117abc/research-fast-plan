# Gate 5 · §3.2 Stop-Sign Lifecycle 状态机（按代码，非按文档）

> 日期：2026-09-03 · 依据当前工作区代码 `PlanT/PlanT_agent.py` + `carla_garage/config.py`
> 结论：type=4 生成/清除逻辑**未被我方 patch 改动**（patch audit L2 仅新增只读 deadlock detector）。下述为官方逻辑的真实状态机。

## 涉及常量（carla_garage/config.py）
```
clearing_distance_to_stop_sign   = 3.0 m   （需速度<0.1 且距 trigger_volume 中心 <3m 才 clear）
unclearing_distance_to_stop_sign = 10.0 m  （距中心 >10m 时清除标志复位为 False）
```

## 代码锚点（PlanT_agent.py）
| 行为 | 行 | 说明 |
|---|---|---|
| type=4 token 生成 | 271-284 | `if next_stop_sign is not None and not self.cleared_stop_sign and next_stop_dist < 30:` → 把下一停车牌作为 `stop_sign` 对象 append 进 `label_raw`（随后 get_input_batch 中 class→`type_nums["stop_sign"]=4`） |
| distance_to_stop_sign | 286-291 | 自车到 `next_stop_sign.trigger_volume.location` 的真实距离；无停车牌→999999999 |
| cleared 复位 | 293-295 | `if distance_to_stop_sign > 10: cleared_stop_sign = False` |
| cleared 置位 | 296-299 | `elif ego_vehicle_speed < 0.1 and distance_to_stop_sign < 3.0: cleared_stop_sign = True` |
| token 消失 | 272 | cleared 为 True 后不再生成 type=4；或 `next_stop_dist ≥ 30`（已驶过）不再生成 |

## 状态机（真实）

```
              ┌──────────────────────────────────────────────┐
              │  S0 无停车牌 / 远离                        │
              │  next_stop_dist≥30 或 next_stop_sign=None    │
              └───────────────▲──────────────────────────────┘
                              │ next_stop_dist<30 且出现下一停车牌
                              ▼
              ┌──────────────────────────────────────────────┐
              │  S1 APPROACH（type=4 在输入中）            │
              │  0m<… 距牌 <30m 且 cleared=False            │
              └───────────────┬──────────────────────────────┘
                              │ 距 trigger_volume 中心 >10m
                              │ （同 S1，cleared 保持 False）
                              ▼  进入 10m 内
              ┌──────────────────────────────────────────────┐
              │  S2 STOP ZONE（type=4 仍在输入中）          │
              │  3m ≤ dist ≤10m，车速可能已降/停            │
              └───────────────┬──────────────────────────────┘
                              │ 车速<0.1 m/s 且 dist<3.0m
                              ▼
              ┌──────────────────────────────────────────────┐
              │  S3 CLEARED（cleared_stop_sign=True）      │
              │  type=4 从输入消失                           │
              └───────────────┬──────────────────────────────┘
                              │ 起步离开；dist>10m
                              ▼
                       回到 S0（cleared 复位 False）
```

重置规则：`cleared_stop_sign` 是**单标志**，只在 `dist>10m` 复位；若中途再次接近同/下一停车牌会回到 S1。

## 关键属性（Gate 5 PASS 判据对应）
- type=4 **不是永久的**：只要车能以 <0.1m/s 靠近到距 trigger_volume 中心 <3m 一次，即置 CLEARED、token 消失。
- 死锁诱因（Gate 4.5A 发现）：若模型在距牌 ≥3m 处长期停车（不敢再向前蠕动到 <3m），则 S2 永远到不了 S3 → type=4 持续 → 死锁。**该清除条件是官方代码固有**（未被我方修改），我方仅在 4.5C 加只读检测器记录该情形。
- reset：单一 bool，route 内按距离循环复位。

## 待补（运行日志）
§3.2 要求"最小运行日志"：在含停车牌 route 上记录 接近→减速→停车→完成→再起步→type4 消失。
→ 由官方 reference smoke（route25 含停车牌）的 Gate4.5A JSONL 提供，见 `step4/` 分析（S1→S2→S3 帧序列）。

## 运行日志（官方 reference epoch=029，route25/route28，TM seed=100）

来源：`outputs/gate5/gate5_ref_route25_tm100.jsonl` / `_route28_...jsonl`（agent 每帧记录）。

### route25：8 次停车牌交互（type4 段），全部正常消失
| 段 (rows) | 达到最小距离 (m) | 最长静止 (frames≈s) | token 消失方式 |
|---|---|---|---|
| 697-880 | 0.2 | 2 | **原地 cleared**（<3m 且 type4→0 后起步） |
| 2505-2695 | 2.7 | 3 | **原地 cleared** |
| 3142-3568 | 0.3 | 21 | 驶过（next_stop 跳至 154m） |
| 3913-4836 | 0.4 | 250≈12.5s | 驶过（next_stop→201m） |
| 5331-5579 | 0.0 | 3 | 驶过（next_stop→164m） |
| 6092-6437 | 2.8 | 17 | **原地 cleared** |
| 6641-6920 | 2.4 | 3 | **原地 cleared** |
| 7638-8439 | 0.2 | 453≈22.7s | 驶过 / 到达终点 |

代表性 S1→S3（段 697-880）：
```
approach ego=14.3 dist_sign=33.7 t4=1  throttle=1.0
stopped  ego≈0.0  dist_sign=8.8  t4=1  (等)
deepest  ego=2.43 dist_sign=0.2  t4=1  braking（贴线）
→ type4→0（cleared），车辆起步，继续前行
```

### route28：4 次停车牌交互，全部正常消失（最长静止 605 frames≈30s 后仍自行恢复）
| 段 (rows) | 最小距离 (m) | 最长静止 | token 消失方式 |
|---|---|---|---|
| 2546-2983 | 2.4 | 18 | **原地 cleared**（row≈2986，t4→0 时 next_stop=0/dist≈2.1m 后加速） |
| 3560-3888 | 2.9 | 4 | **原地 cleared** |
| 4145-5112 | 2.5 | 605≈30s | 驶过 |
| 5419-6263 | 0.1 | 276≈14s | 驶过 / 到达终点 |

### §3.2 判定
- type=4 **从不永久存在**（8/8、4/4 段全部消失）✅
- 完成停车后能进入 clear / 通过后 token 消失 ✅（多段观测到原地 cleared 或驶过）
- 车辆始终能恢复前进、跑完全程（r25 100%、r28 100%）✅
- 状态机**无永久 deadlock** ✅（虽多次出现 12~30s 的长停，最终都自行起步）

> 注：官方 30-epoch 模型也会在部分停车牌前长停（最长 ~30s）甚至低速碾过，但从不永久卡死；这与 Gate 4.5A 观测到的"研究 5-epoch exact/relation 可卡 ≥180s → AgentBlocked"不同 —— 该差异归因于模型训练程度，非生命周期逻辑。
