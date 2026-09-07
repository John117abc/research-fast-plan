# Gate F0：Progress-Viable Future Structure 最小验证方案
## ——验证“纵向可维持 / 横向必要 / 横向可选 / 暂无可行进展”是否能由未来可行时空结构自然区分

> **用途**
>
> 本文直接承接当前 CARLA / PlanT / Waymo 阶段研究，不重新设计 Driving Relation，也不训练新模型。
>
> 当前要验证的唯一命题是：
>
> **在复杂动态驾驶场景中，当前默认 corridor 是否仍可通过纵向调节维持任务，以及横向 maneuver 是否已经成为任务完成的必要条件，能否由 Ego 的未来可行时空结构统一刻画。**
>
> 这是一个存在性 Gate，不是完整规划器开发。

---

# 1. 为什么现在做这个实验

当前实验已经得到两个重要结论：

1. 在 PlanT / Town12 中，不同物理机制场景的规划响应大多收缩为低阶纵向响应；
2. Waymo 中，纵向主导和低阶时间结构在普通非交互驾驶中也普遍存在。

因此：

> **仅比较 Ego 最终轨迹或 planning-response similarity，不足以作为 Driving Relation 的证据。**

当前需要把研究对象从：

```text
Scene
→ Planner output
→ Trajectory similarity
```

转成：

```text
Scene
→ Ego future feasible set
→ Maneuver necessity
```

核心变化：

> 不再问“模型最后选了什么轨迹”，而问“当前场景到底允许 Ego 有哪些未来”。

---

# 2. 本实验不做什么

Gate F0 明确不做：

```text
不训练新网络
不修改 PlanT
不做 Relation learning
不做 OOD
不做 Town13
不做复杂行为预测
不做 uncertainty modeling
不做完整 5D viability kernel
不做最优轨迹控制
不重新调一堆 cost 权重
```

第一轮只验证：

> **未来可行空间的结构，能否自然给出 maneuver necessity。**

---

# 3. 直接复用当前已有工程能力

当前已有能力可以继续使用：

```text
CARLA scenario
→ actor runtime mapping
→ Ego / actor GT state
→ route / map
→ snapshot
→ offline analysis
```

已有信息包括：

```text
actor x/y/yaw/speed/size
ego pose / speed
route
map
scenario type
frame
instance id
```

这些已经足够做 Gate F0。

本实验不需要 PlanT forward 输出作为核心量。PlanT 仅保留为后续对照 planner。

---

# 4. Gate F0 的核心对象

设：

```text
C0 = 当前默认行驶 corridor
CL = 左侧候选 corridor
CR = 右侧候选 corridor
```

第一版只做：

```text
C0 + CL
```

对每一个 corridor \(C_j\)，定义未来可行轨迹集合：

\[
\mathcal F_j(X,H)
=
\{
\tau
\mid
\tau
\text{满足道路合法、无碰撞、动力学可达，并位于 }C_j
\}
\]

然后定义：

\[
P_j(H)
=
\max_{\tau\in\mathcal F_j(X,H)}
[s_\tau(H)-s_0]
\]

解释：

> **在 horizon \(H\) 内，如果 Ego 选择 corridor \(C_j\)，最多还能安全向前推进多少。**

---

# 5. 为什么用 \(P_j(H)\)

只看 collision-free 没有意义，因为“永远停车”几乎总是安全。

所以本实验真正关心的是：

```text
安全
+
动力学可达
+
道路合法
+
能否继续向前推进
```

---

# 6. 第一版统一 horizon

固定：

```text
H = 2 s, 4 s, 6 s, 8 s
```

主判据使用：

\[
G_j
=
\frac{P_j(8)-P_j(6)}{2}
\]

解释：

> 6–8 s 之间，这个 corridor 的可行前沿是否还在继续向前扩展。

若 \(G_j\approx0\)，说明该 branch 在远端已经基本“死掉”；若 \(G_j>0\)，说明它仍然具有持续 progress 能力。

---

# 7. 第一阶段不要只设一个阈值

定义：

\[
G_j>\epsilon
\]

认为 branch “仍具有持续 progress”。

统一 sweep：

```text
epsilon = 0.05
          0.10
          0.15
          0.20  m/s
```

要求：

> 最终结构分类不能只在某一个非常特殊的 epsilon 下成立。

如果结果对 epsilon 极其敏感，则 Gate F0 不通过。

---

# 8. 四种目标结构

## F0-A：Longitudinal Sufficient

当前 corridor 仍可通过等待 / 减速 / 恢复前进完成任务。

\[
G_0>0
\]

解释：

> **当前 corridor 可继续维持，横向 maneuver 不是必要条件。**

## F0-B：Lateral Necessary

\[
G_0\approx0,\quad G_L>0
\]

解释：

> **当前 corridor 已无法继续产生有效 progress，但 alternative corridor 可以。**

因此横向 maneuver 是 necessity。

## F0-C：Lateral Optional

\[
G_0>0,\quad G_L>0
\]

解释：

> 当前 lane 可以继续完成任务，左 lane 也可行。

因此变道是 preference，不是 necessity。

## F0-D：Contingency / Wait

\[
G_0\approx0,\quad G_L\approx0
\]

解释：

> 当前和替代 corridor 暂时都没有持续 progress branch。

此时应等待 / 保持安全，而不是强行横向 maneuver。

---

# 9. 第一轮四个 archetype

| Case | 场景 | 预期结构 |
|---|---|---|
| A | 行人短暂横穿，1.5–2.5 s 后离开 | Longitudinal Sufficient |
| B | 静态故障车永久堵住当前 lane，左 lane 可用 | Lateral Necessary |
| C | 慢速前车，当前 lane 可持续跟驰，左 lane 可超车 | Lateral Optional |
| D | 静态车堵路，同时左 lane 暂不可安全进入 | Contingency / Wait |

---

# 10. 最小实现：不要一开始做连续最优控制

Gate F0 只需要判断 branch 是否存在，不需要求最优轨迹。

第一版使用 motion primitives。

---

# 11. Ego 纵向运动模型

\[
s_{t+1}
=
s_t+v_t\Delta t+\frac12a_t\Delta t^2
\]

\[
v_{t+1}
=
\max(0,v_t+a_t\Delta t)
\]

建议：

```text
dt = 0.5 s
Hmax = 8 s
```

加速度 primitive：

```text
a ∈ {-4.0, -2.0, 0.0, +1.5} m/s²
```

最大速度优先使用道路 speed_limit；若 pilot 中读取不稳定，可暂用 12 m/s，但正式批量实验前必须冻结。

---

# 12. 横向 primitive

第一版只定义：

```text
KEEP
CHANGE_LEFT
```

CHANGE_LEFT 使用固定 3.0 s 五次多项式 lane-change：

\[
d(t)
=
d_0
+
(d_L-d_0)
(10r^3-15r^4+6r^5)
\]

其中：

\[
r=t/T_{LC}
\]

这一步只判断左侧 branch 是否物理可行，不研究最佳换道轨迹。

---

# 13. Corridor 生成

直接使用 CARLA Map / OpenDRIVE：

```python
wp = carla_map.get_waypoint(ego_location)
```

得到：

```text
C0 = current lane
CL = wp.get_left_lane()
```

只保留：

```text
同向
Driving lane
lane-change topology 合法
```

禁止：

```text
跨实线
逆向 lane
sidewalk
shoulder
```

如果没有合法左 lane，则该样本不用于 B/C/D。

---

# 14. Corridor 坐标

沿每条 corridor centerline 建立：

\[
\Gamma_j(s)
\]

每个 Ego primitive 用：

```text
s = longitudinal progress
d = lane-relative lateral offset
```

表示。

这样直接得到 \(P_j(H)\)。

---

# 15. Dynamic occupancy

第一轮直接使用 CARLA GT actor future，不做 prediction network。

对 scripted scenario actor 记录 8 s GT future pose：

\[
\mathcal O_i(t)
\]

碰撞判断使用：

```text
actor bounding box
+
ego bounding box
+
统一 safety margin
```

主实验：

```text
safety margin = 0.5 m
```

后续 sensitivity 可看：

```text
0.3 / 0.5 / 0.8 m
```

---

# 16. 为什么第一轮必须用 GT future

当前只验证：

```text
Feasible Future Structure
是否有决策意义
```

如果同时加入预测误差，实验失败后无法判断到底是结构假设失败还是 prediction 失败。

所以 Gate F0：

```text
GT future = oracle / upper-bound analysis
```

---

# 17. Feasible branch 搜索

对每个 corridor：

```text
初始化 Ego state
↓
枚举 longitudinal acceleration primitives
↓
生成未来状态
↓
检查：
    road validity
    speed
    dynamic feasibility
    collision
↓
保留 feasible states
↓
计算每个 H 下最大 s
```

输出：

\[
P_j(2),P_j(4),P_j(6),P_j(8)
\]

---

# 18. 搜索规模

```text
dt = 0.5 s
8 s = 16 steps
```

不能全组合 \(4^{16}\)，所以使用 Beam Search：

```text
beam width = 100
```

每一步：

```text
扩展 4 个 acceleration primitive
→ feasibility check
→ 按 progress / speed bucket 保留状态
```

按速度分桶：

```text
0–2 m/s
2–5 m/s
5–8 m/s
8–12 m/s
>12 m/s
```

每 bucket 保留 top 20，避免只留下激进加速状态，保留停车、等待、跟驰、恢复前进等未来。

---

# 19. 当前已有场景怎样复用

当前 Town12 已有：

```text
HardBreak
ParkingCutIn
VehicleTurning
PedestrianCrossing
```

优先复用：

```text
PedestrianCrossing
```

用于 Temporary Closure / Reopen。

HardBreak 可作为 Longitudinal Maintainable 的补充，但不等同于 persistent blocker。

建议仅新增：

```text
StaticBlocker_FreeLeft
StaticBlocker_BlockedLeft
```

如果现有 HardBreak 无法形成稳定“慢车但仍可跟驰”，再新增：

```text
SlowLead_FreeLeft
```

不要修改已有 Gate 6 数据，Gate F0 新建独立 scenario set。

---

# 20. Pilot：先只做两个场景

第一步：

```text
PedestrianCrossing
vs
StaticBlocker_FreeLeft
```

各 5 个随机 seed，共 10 runs。

只检查：

### Pedestrian

```text
P0(H)
短暂受限
但远端重新增长
```

### Static Blocker

```text
P0(H) 饱和
PL(H) 持续增长
```

如果这一步都不成立，立即停止，不扩展四类。

---

# 21. Pilot 必须输出的图

每个 run 输出 2 张：

## 图 1：BEV Feasible Structure

画：

```text
road
current lane
left lane
dynamic actor GT future occupancy
Ego feasible sampled trajectories
```

用于人工确认可行 branch 计算是否符合场景直觉。

## 图 2：Progress Frontier

横轴：

\[
H
\]

纵轴：

\[
P_j(H)
\]

画：

```text
P0(H)
PL(H)
```

这是 Gate F0 最关键的图。

---

# 22. Pilot 判定

### PedestrianCrossing

希望看到：

\[
P_0(8)>P_0(6)
\]

即：

\[
G_0>0
\]

### StaticBlocker_FreeLeft

希望看到：

\[
G_0\approx0,\quad G_L>0
\]

如果在合理 epsilon 范围内稳定区分，则进入完整 Gate F0。

否则 STOP。

---

# 23. 完整 Gate F0 数据量

四类：

```text
A Temporary Closure
B Persistent Block + Alternative
C Slow Lead + Alternative
D Persistent Block + Alternative unavailable
```

每类：

```text
30 runs
```

总计：

```text
120 runs
```

---

# 24. 推荐随机化范围

## A：Temporary Closure

```text
ego_speed         = 5–10 m/s
ped crossing_t    = 0.5–2.0 s
ped speed         = 1.0–2.0 m/s
initial distance  = 10–30 m
```

## B：Static Blocker

```text
ego_speed          = 5–10 m/s
blocker distance   = 15–35 m
left lane gap      = 保证可行
```

## C：Slow Lead

```text
ego_speed        = 7–12 m/s
lead_speed       = 2–6 m/s
lead distance    = 10–30 m
left lane        = 可用
```

## D：Blocked Alternative

```text
与 B 相同
+
left rear vehicle speed = 8–15 m/s
left rear gap           = 5–20 m
```

具体范围允许根据 CARLA geometry 做一次 pilot 修正，但正式 120-run 前必须冻结。

---

# 25. 每个 run 保存字段

```text
run_id
seed
scenario_type

ego_initial_speed
ego_lane_id

target_actor_id
target_actor_type
target_actor_initial_distance

left_lane_available

P0_2
P0_4
P0_6
P0_8

PL_2
PL_4
PL_6
PL_8

G0
GL

class_pred

num_feasible_C0
num_feasible_CL

min_clearance_C0
min_clearance_CL

epsilon
H
```

---

# 26. 四分类逻辑

```python
alive_0 = G0 > epsilon
alive_L = GL > epsilon
```

分类：

```text
alive_0=True,  alive_L=False
→ Longitudinal Sufficient

alive_0=False, alive_L=True
→ Lateral Necessary

alive_0=True,  alive_L=True
→ Lateral Optional

alive_0=False, alive_L=False
→ Contingency / Wait
```

---

# 27. Gate F0 主指标

## Metric 1：Structure Classification Accuracy

四类人工设计场景标签已知。

目标：

```text
Accuracy >= 90%
```

## Metric 2：Sensitivity Stability

对：

```text
epsilon = 0.05 / 0.10 / 0.15 / 0.20
```

以及：

```text
Hmax = 6 / 8 / 10 s
```

检查 classification flip rate。

希望：

```text
< 10%
```

## Metric 3：Cross-Scene Structural Reuse

第二阶段加入物理机制不同的：

```text
PedestrianCrossing
VehicleCrossing
Temporary road occupation
```

如果都属于“Temporary Closure → Reopen”，应映射到同一 Longitudinal Sufficient 结构。

这才重新验证：

\[
X_A\neq X_B
\]

但：

\[
\mathcal F(X_A)\sim\mathcal F(X_B)
\]

---

# 28. Gate F0 PASS / PARTIAL / FAIL

## PASS

同时满足：

```text
1. Pilot 两类能稳定区分
2. 四类 accuracy >= 90%
3. epsilon / horizon 小范围变化不敏感
4. cross-physical scenarios 可以映射到相同 feasible structure
```

则可写：

> **未来 progress-viable feasible structure 具有明确的 maneuver-necessity semantics。**

下一步才进入：

```text
Gate F1：
Feasible Future Structure
vs
Cost-based Planner
```

## PARTIAL

若：

```text
A/B 可以区分
C/D 边界不稳定
```

说明可行空间可以刻画“暂时阻塞 vs persistent dead-end”，但还不足以完整刻画 maneuver necessity。

## FAIL

若：

```text
Pedestrian
和
Static Blocker
都无法稳定区分
```

或分类高度依赖 epsilon / H，则停止扩大实验。

---

# 29. 第一版代码结构建议

```text
gate_f0/
├── config/
│   └── gate_f0.yaml
├── scenarios/
│   ├── temporary_crossing.py
│   ├── static_blocker_free_left.py
│   ├── slow_lead_free_left.py
│   └── static_blocker_blocked_left.py
├── feasible/
│   ├── corridor_builder.py
│   ├── longitudinal_primitives.py
│   ├── lane_change_primitive.py
│   ├── occupancy_gt.py
│   ├── collision_check.py
│   ├── beam_search.py
│   └── progress_frontier.py
├── scripts/
│   ├── 00_smoke_corridor.py
│   ├── 01_smoke_occupancy.py
│   ├── 02_run_two_case_pilot.py
│   ├── 03_run_gate_f0.py
│   ├── 04_sensitivity.py
│   └── 05_report.py
├── results/
│   ├── pilot/
│   ├── full/
│   └── gate_f0_summary.csv
└── figures/
```

不要直接修改 PlanT 核心代码。

---

# 30. 推荐配置

```yaml
simulation:
  dt: 0.5
  horizon_sec: 8.0

ego:
  accel_primitives: [-4.0, -2.0, 0.0, 1.5]
  default_speed_limit_mps: 12.0

lane_change:
  enabled: true
  duration_sec: 3.0
  direction: left

beam:
  width: 100
  speed_buckets_mps: [0, 2, 5, 8, 12, 100]
  keep_per_bucket: 20

collision:
  safety_margin_m: 0.5
  use_gt_actor_future: true

progress:
  horizons_sec: [2, 4, 6, 8]
  primary_interval_sec: [6, 8]
  epsilon_sweep_mps: [0.05, 0.10, 0.15, 0.20]

pilot:
  seeds_per_case: 5

full:
  seeds_per_case: 30
```

---

# 31. 最小执行顺序

## Step 0：验证 corridor

任意双车道路段：

```text
读取 C0
读取 CL
绘制 centerline
```

确认方向一致、lane id 正确、没有跨到逆向 lane。

## Step 1：验证 GT occupancy

静态 actor：

```text
未来 8 s occupancy 固定
```

PedestrianCrossing：

```text
occupancy 随时间横穿 corridor
```

## Step 2：单 corridor beam search

无障碍：

```text
P0(H) 单调增长
```

加入静态障碍：

```text
P0(H) 在障碍物前饱和
```

这一步不过，禁止继续。

## Step 3：两场景 Pilot

```text
PedestrianCrossing × 5
StaticBlocker_FreeLeft × 5
```

输出 10 张 Progress Frontier 和 10 张 BEV feasible structure 图。

## Step 4：Pilot Gate

若：

```text
Pedestrian:
G0 > epsilon

Static Blocker:
G0 <= epsilon
GL > epsilon
```

在合理 epsilon 范围内稳定，则扩展四类；否则 STOP。

## Step 5：完整 120-run

```text
4 类 × 30
```

输出：

```text
accuracy
confusion matrix
G0 / GL distribution
flip rate
```

## Step 6：Cross-Scene Reuse

优先复用已有 VehicleTurning，或者新增 TemporaryVehicleCrossing。

验证：

> 物理对象不同，但只要当前 corridor 同样“短时关闭后重新开放”，是否得到与 Pedestrian 类似的 progress-frontier structure。

---

# 32. 最关键的结果图

完整 Gate F0 最终重点看 4 张图：

1. 四类 archetype 的 \(P_0(H),P_L(H)\) 典型曲线；
2. \((G_0,G_L)\) 二维散点；
3. 四分类 confusion matrix；
4. epsilon / horizon sensitivity。

其中 \((G_0,G_L)\) 图最重要：

```text
右下：current alive / alt dead
左上：current dead / alt alive
右上：both alive
左下：both dead
```

如果四类能自然落在四个区域，说明核心假设很直观。

---

# 33. Gate F0 最希望看到的结果

理想结果不是“某条轨迹更安全”，而是：

> **完全不同的物理驾驶场景，能够被未来可行空间自然压缩成少量具有明确决策含义的结构状态。**

例如：

```text
PedestrianCrossing
VehicleCrossing
Temporary occupation
```

虽然场景不同，但都表现为：

```text
Temporary Closure
→ Reopen
→ Current corridor remains progress-viable
```

而：

```text
Static vehicle
Road blockage
Construction obstruction
```

可能表现为：

```text
Persistent Dead-End
+
Alternative branch alive
```

这才是新的：

\[
Cross	ext{-}Scenario\ Feasible\ Structure
\]

---

# 34. 与之前研究的关系

之前：

\[
X
\rightarrow
Planner
\rightarrow
\Delta W
\]

再比较：

\[
\Delta W_A\approx\Delta W_B
\]

结果发现容易被 road-following、车辆运动学和纵向 progress 解释。

现在：

\[
X
\rightarrow
\mathcal F(X)
\]

直接比较：

```text
场景允许什么未来
```

而不是：

```text
某个 planner 最后选了什么
```

如果 Gate F0 成立，则新的研究对象从：

```text
Trajectory Response Equivalence
```

正式转为：

```text
Progress-Viable Future Structure
```

---

# 35. 一句话执行目标

> **先用 CARLA GT + 最小 motion primitive + 双 corridor 搜索，验证 Pedestrian 的“短时关闭后恢复”和 Static Blocker 的“当前 branch 永久失效、左侧 branch 可用”能否仅通过 \(P_j(H)\) / \(G_j\) 自然区分；只有这一最小命题成立，才扩展到四类 maneuver necessity 和后续论文方法。**
