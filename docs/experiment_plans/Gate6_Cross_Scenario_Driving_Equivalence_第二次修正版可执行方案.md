# Gate 6：Cross-Scenario Driving Equivalence Existence
## 第二次修正版可执行方案（Town12 Discovery → Town13 Validation）

> **研究目标**
>
> 本 Gate 不设计新的 Relation，不训练 Relation-v1，不用 TTC / clearance / permission 等人工特征定义“关系”。
>
> 只验证：
>
> **不同物理驾驶场景之间，是否存在不等同于 scene category、能够跨场景重复出现的驾驶决策响应结构。**
>
> 如果存在，再进入后续“低复杂度验证”和“Relation 定义”；如果不存在，则暂停当前核心假设，不继续强行设计 Relation。

---

# 0. 固定实验基座

Gate 6 全程使用 Gate 5 已冻结的：

```text
PlanT-Reference
official checkpoint：30 epoch
input representation：Exact
input_ego_speed：False
input_bev：True

Relation-v0：OFF
NoStop：OFF
Gate4.5B mask：OFF
Gate4.5C force-drop：OFF
其他 intervention：OFF
```

固定：

```text
commit
checkpoint
config
controller
route planner
CARLA build
scenario runner
```

Gate 6 过程中不得修改 baseline forward 行为。

---

# 1. 第一轮固定场景组

根据当前 benchmark 真实 annotation，第一轮使用：

| Group | Scenario Type | 物理机制 |
|---|---|---|
| A | `HardBreakRoute` | 前车急刹 / 纵向交互 |
| B | `ParkingCutIn` | 横向切入 |
| C | `VehicleTurningRoute` | 对向/横向车辆冲突 |
| D | `PedestrianCrossing` | 行人横穿 |

实验分工：

```text
Town12 = Discovery
Town13 = Validation
```

暂时保留：

```text
DynamicObjectCrossing
```

作为后续未参与 Discovery 的额外 scenario validation。

---

# 2. Gate 6 总体流程

```text
Step 6.0
建立 Town12 / Town13 去重 manifest
        ↓
Step 6.1
Town12 greedy 选择少量高覆盖 route
        ↓
Step 6.2
每类先 smoke ≥2 个真实 scenario instance
        ↓
Step 6.3
语义验收：
HardBreak / VehicleTurning 等确实形成预定物理交互
        ↓
Step 6.4
冻结：
scenario classes
Discovery routes
target instances
        ↓
Step 6.5
实现 active_scenario / target_actor 映射
        ↓
Step 6.6
实现完整 forward snapshot logger
        ↓
Step 6.7
整路线运行，scenario active 期间 5 Hz 采集
        ↓
Step 6.8
Offline Replay
        ↓
【Replay PASS 后暂停并反馈】
        ↓
Step 6.9
actor removal → dominant actor
        ↓
Step 6.10
统一 intervention
        ↓
Step 6.11
Planning Response Signature
        ↓
Step 6.12
Different-Scene / Similar-Response
+
Same-Scene / Different-Response
        ↓
Step 6.13
Town13 Validation
        ↓
Step 6.14
Expert / 独立 planner validation
        ↓
Gate 6 PASS / FAIL
```

---

# 3. Step 6.0：建立去重 Manifest

扫描：

```text
leaderboard/data/routes_training.xml
leaderboard/data/routes_validation_split/*.xml
leaderboard/data/bench2drive_split/*.xml
```

主要保留：

```text
Town12
Town13
```

---

## 3.1 Manifest 字段

输出：

```text
gate6/town12_manifest.csv
gate6/town13_manifest.csv
```

字段：

```text
unique_instance_id
scenario_group
scenario_type
town
route_id
trigger_x
trigger_y
trigger_yaw
source_file
```

---

## 3.2 去重规则

构造：

```text
unique_instance_id
=
town
+ route_id
+ scenario_type
+ trigger_x
+ trigger_y
+ trigger_yaw
```

然后：

```text
drop_duplicates(unique_instance_id)
```

后续统计的：

```text
scenario instance
```

必须是真正独立实例，不允许 split 文件重复计数。

---

# 4. Step 6.1：Greedy Route Coverage

第一轮不要逐 instance 单独跑 32 次。

改为：

> **优先选择能一次覆盖最多目标 scenario instance 的 Town12 route。**

---

## 4.1 Greedy 目标

目标覆盖：

```text
HardBreakRoute       ≥8
ParkingCutIn         ≥8
VehicleTurningRoute  ≥8
PedestrianCrossing   ≥8
```

每轮选择：

```text
能新增最多“尚未覆盖目标 instance”的 route
```

直到四类达到目标。

---

## 4.2 Route 选择规则

路线选择只能基于：

```text
scenario inventory / coverage
```

不能基于：

```text
PlanT 输出好不好
pred_wps 是否相似
是否容易出现 candidate pair
```

路线集合必须在看到 planning response 之前冻结，避免 cherry-picking。

---

## 4.3 保存结果

输出：

```text
gate6/town12_discovery_routes.csv
```

字段：

```text
route_id
town
source_file
covered_hardbreak
covered_parkingcutin
covered_vehicleturning
covered_pedestrian
total_new_instances
selected_order
```

---

# 5. 统计独立性原则

同一 route 内的多个 scenario：

```text
不是完全 IID
```

因为它们共享：

```text
Town
地图
天气
Ego 历史
route context
```

因此必须同时保存：

```text
route_id
scenario_instance_id
```

后续论文统计时：

> **scenario instance 是最小实验单位，但 route 需要作为分组变量保留。**

必要时做：

```text
grouped statistics
或
route-level bootstrap
```

---

# 6. Step 6.2：Scenario Smoke Test

在正式采集前，每类先 smoke：

```text
≥2 个真实 instance
```

固定：

```text
PlanT-Reference
TM seed = 100
intervention = OFF
```

记录：

```text
scenario_group
scenario_type
unique_instance_id
route_id
triggered
target_actor_present
completed
collision
blocked
carla_crash
runtime
notes
```

输出：

```text
gate6/scenario_smoke.csv
```

---

# 7. Step 6.3：必须做“语义验收”

Smoke 不只是看：

```text
scenario 有没有触发
```

还必须确认：

> **这个 scenario 的真实运行行为确实代表我们想研究的物理交互机制。**

---

## 7.1 HardBreakRoute

必须确认：

```text
1. lead actor 真正出现
2. lead actor 在 Ego 前方形成纵向交互
3. lead actor 确实发生 braking / deceleration
4. lead actor 能进入 PlanT object token
5. Ego planning 对该 actor 有实际响应
```

如果大量 instance：

```text
lead actor 太远
未形成纵向交互
或根本没进入模型输入
```

则：

> 不强行保留 HardBreakRoute，重新选择纵向交互 scenario。

---

## 7.2 VehicleTurningRoute

必须确认：

```text
1. turning vehicle 真实出现
2. 它确实构成 Ego 决策中的主要动态交互
3. 场景不是主要被 stop-sign / traffic-light 支配
4. turning vehicle 能进入 PlanT token
```

如果大量 instance 实际由规则 token 主导：

> 第一轮优先替换为 `DynamicObjectCrossing`。

---

## 7.3 ParkingCutIn / PedestrianCrossing

确认：

```text
target actor 真实形成 lateral / crossing interaction
进入 PlanT token
不是只“出现”但与 Ego 无实际交互
```

---

# 8. Smoke 后冻结实验集合

语义验收通过后，冻结：

```text
4 个 scenario class
Town12 Discovery route 集合
每类目标 instance 集合
```

冻结后：

```text
不因后续 response 好坏而更换 route / instance
```

如果某个 instance 因技术原因失败：

```text
CARLA crash
scenario 未触发
actor 缺失
```

只能按预先定义的顺序，用 manifest 中下一个同类 instance 替换。

---

# 9. Step 6.4：Scenario Active Window 必须由运行时状态定义

不能根据 XML trigger 点人工猜：

```text
前后几秒就是 scenario window
```

因为同一 route 中：

```text
同 type 可能出现多次
多个 scenario 可能重叠
```

---

## 9.1 每帧必须记录

利用当前代码中的：

```text
CarlaDataProvider.active_scenarios
actor 的 scenario 来源信息
```

建立：

```text
active_scenario_type
active_scenario_instance_id
target_actor_ids
target_token_indices
```

---

## 9.2 有效 snapshot 归属规则

只有同时满足：

```text
1. 目标 scenario 当前 active
2. 当前 frame 能映射到唯一 unique_instance_id
3. 至少一个属于该 scenario 的 target actor 已进入 PlanT object tokens
```

该帧才记为：

```text
valid snapshot
```

---

## 9.3 Scenario overlap

如果同一 frame：

```text
两个目标 scenario 同时 active
```

标记：

```text
scenario_overlap = True
```

第一轮 Pilot：

```text
不进入 single-dominant-actor 样本池
```

但日志仍保留。

---

# 10. Step 6.5：Forward Snapshot Logger

原则：

> **只加日志，不改 forward。**

Snapshot 保存位置固定为：

```text
所有官方 filtering 完成
↓
object token 已形成
↓
idxs 已形成
↓
route_original 已形成
↓
speed_limit 已形成
↓
BEV tensor 已形成
↓
【snapshot】
↓
model.forward(...)
```

---

# 11. Snapshot 必须保存完整 forward 输入

当前官方模型实际需要：

```text
x_objs
idxs
route_original
speed_limit
BEV
```

每个 snapshot 还保存：

```text
pred_wps_online
pred_path_online
```

推荐：

```text
.pt
```

保存时：

```text
tensor.detach().cpu()
```

但必须保持：

```text
dtype
shape
token order
batch dimension
```

不变。

---

# 12. Snapshot Metadata

同时保存 JSON：

```text
frame
timestamp
town
route_id
scenario_group
scenario_type
unique_instance_id
scenario_active
scenario_overlap

ego_world_x
ego_world_y
ego_world_yaw
ego_speed_mps

TM_seed
checkpoint
commit
```

动态 actor 至少记录：

```text
actor_id
actor_local_idx
actor_type
token_idx
belongs_to_target_scenario
x_ego
y_ego
yaw_rel_deg
speed_kmh
width_m
length_m
```

---

# 13. BEV 原则

当前已确认：

```text
BEV 只含静态地图
road
sidewalk
lane marking
```

不含：

```text
vehicle
pedestrian
dynamic occupancy
```

因此后续 actor intervention：

```text
BEV 保持完全不变
```

是合法的。

---

# 14. Step 6.6：整路线 Snapshot 采集

不再：

```text
每个 instance 单独跑一次
```

而是：

```text
完整运行冻结后的 Discovery routes
```

在 route 内根据：

```text
active_scenario_instance_id
```

自动切出目标 scenario window。

---

## 14.1 采样频率

目标：

```text
5 Hz
```

即约：

```text
每 0.2 s 一个 snapshot
```

如果当前 evaluator 20 Hz：

```text
每 4 frame 保存一次
```

---

## 14.2 采集阶段只排除

```text
scenario inactive
collision 后
route 已结束
CARLA 异常
```

不要根据：

```text
TTC
clearance
distance
pred_wps
```

筛选。

---

# 15. Step 6.7：Offline Replay Consistency Gate

这是 Gate 6 最关键工程 Gate。

新增：

```text
tools/gate6/replay_snapshot.py
```

流程：

```text
读取 snapshot
↓
加载 PlanT-Reference
↓
model.eval()
↓
torch.inference_mode()
↓
使用保存的：
x_objs
idxs
route_original
speed_limit
BEV
↓
forward
↓
pred_wps_offline
↓
与 pred_wps_online 对比
```

---

# 16. Replay 前确认

当前已确认模型：

```text
无跨帧 hidden state
无 KV cache
无 temporal memory
GRU 只在单次 forward 内部解码
```

因此不需要保存上一帧模型状态。

---

# 17. Replay 测试规模

随机抽：

```text
>=20 个 snapshot
```

并覆盖：

```text
4 类场景
多个 route
多个 unique_instance_id
不同交互阶段
```

记录：

```text
max_abs_error
mean_abs_error
```

输出：

```text
gate6/replay_check.csv
```

---

# 18. Replay PASS

要求：

```text
pred_wps_offline ≈ pred_wps_online
```

误差只能属于：

```text
浮点级差异
```

不允许出现明显 waypoint 轨迹差异。

---

# 19. Replay FAIL

如果不一致：

```text
立即停止后续 dominant actor / intervention
```

排查：

```text
x_objs
idxs
route_original
speed_limit
BEV
token order
batch shape
eval / dropout
tensor dtype
```

直到 replay 通过。

---

# 20. 第一阶段停止点

当前先只执行：

```text
1. Town12/Town13 去重 manifest
2. Town12 greedy route coverage
3. 四类各 smoke ≥2 instance
4. 语义验收
5. 冻结 Discovery routes / instances
6. active_scenario + target_actor 映射
7. 完整 forward snapshot logger
8. 整路线 5 Hz 采集
9. >=20 snapshot offline replay
```

然后：

# 暂停并反馈结果

本轮先不要继续：

```text
dominant actor
intervention
signature
pair
```

---

# 21. Replay PASS 后：Dominant Actor

对每个有效 snapshot 中所有动态 actor：

```text
分别删除 actor token
↓
PlanT forward
↓
pred_wps_remove_i
```

定义：

```text
D_i = RMS(pred_wps_remove_i - pred_wps_base)
```

排序：

```text
D1 >= D2 >= D3 ...
```

---

## 21.1 single-dominant pilot 阈值

固定：

```text
D1 >= 0.20 m
AND
D1 / max(D2, 0.05) >= 1.5
```

如果通过率很低：

```text
先报告 D1 / D1D2 分布
不要直接调阈值
```

---

# 22. 每个 instance 选 Decision States

从 single-dominant 有效状态中：

```text
early
early-middle
late-middle
late
```

每个 instance 约：

```text
4 states
```

相邻状态：

```text
优先 >=1.0 s
最低 >=0.5 s
```

---

# 23. Step 6.10：统一 5 类 Intervention

对 dominant actor：

```text
I1：沿自身朝向前移 2 m
I2：沿自身朝向后移 2 m
I3：speed ×1.20
I4：speed ×0.80
I5：remove actor
```

这些仅是：

```text
实验探针
```

不是 Relation feature。

---

# 24. I1 / I2 坐标实现

Token：

```text
x：Ego 局部前向
y：Ego 局部左向
yaw：相对 Ego yaw，degree
```

因此：

```python
theta = deg2rad(yaw_deg)

dx = 2.0 * cos(theta)
dy = 2.0 * sin(theta)
```

前移：

```text
x' = x + dx
y' = y + dy
```

后移：

```text
x' = x - dx
y' = y - dy
```

---

# 25. I1 / I2 Sanity Check

批量执行前，先找：

```text
正前方、与 Ego 同向车辆
```

应满足：

```text
yaw_rel ≈ 0°
```

前移 2m 后：

```text
x 增加约 2m
y 基本不变
```

通过后才能批量运行。

---

# 26. I3 / I4

Token speed：

```text
km/h
```

因此：

```text
I3 = speed_kmh ×1.20
I4 = speed_kmh ×0.80
```

若：

```text
speed ≈0
```

则该干预影响很弱。

只记录：

```text
speed_intervention_effective
```

本轮不修改干预定义。

---

# 27. Step 6.11：Planning Response Signature

Baseline：

```text
W0 = pred_wps_base
```

五个 intervention：

```text
W1...W5
```

定义：

```text
ΔWk = Wk - W0
```

Signature：

```text
S(X)
=
[
vec(ΔW1),
vec(ΔW2),
vec(ΔW3),
vec(ΔW4),
vec(ΔW5)
]
```

注意：

```text
S(X) != Driving Relation
```

只是 response probe。

---

# 28. Pair Similarity

先排除：

```text
signature_norm 最低 20%
```

然后计算：

```text
cosine_similarity
```

以及：

```text
magnitude_ratio
=
min(||SA||,||SB||)
/
max(||SA||,||SB||)
```

---

# 29. Different-Scene / Similar-Response

要求：

```text
scenario_group(A) != scenario_group(B)
unique_instance_id(A) != unique_instance_id(B)
```

Pilot 阈值：

```text
cosine >=0.90
magnitude_ratio >=0.50
```

取：

```text
Top 20
```

并要求：

```text
>=3 种 scene-pair 组合
```

---

# 30. Same-Scene / Different-Response

要求：

```text
scenario_group 相同
unique_instance_id 不同
```

选：

```text
response similarity 最低 10~20 对
```

作为负对照。

---

# 31. Confound Check

Top cross-scene pairs 必须记录：

```text
ego speed
route command
local curvature
dominant actor distance
route_id
Town
```

检查相似性是否只是：

```text
同速度
同直线路段
同 route context
```

---

# 32. Town13 Validation

Town12 Discovery 得到 candidate 后：

```text
不重新调整 intervention
不重新调 similarity
不重新调 pair threshold
```

直接在 Town13 同四类场景中复现。

目标：

> Town12 发现的 response structure 是否跨环境仍存在。

---

# 33. Expert Validation

Town12 + Town13 有正面结果后，再对最强 candidate 使用：

```text
carla_garage/autopilot.py
```

或其他已确认可用的独立 expert。

验证：

> PlanT 认为相似的 cross-scene response，在独立 expert 下是否仍保持相似趋势。

---

# 34. Gate 6 Pilot PASS

至少满足：

```text
1. 四类场景真实可稳定运行
2. 每类 >=5 独立有效 instance
3. Replay PASS
4. single-dominant states 足够
5. >=15 个有效 cross-scene similar pairs
6. >=3 种 scene-pair 组合
7. 存在 same-scene different-response
8. sanity check 后大部分 Top pairs 合理
9. 不能由 ego speed / route geometry 单一解释
```

---

# 35. Gate 6 Full PASS

进一步要求：

```text
Town13 复现
+
Expert / 独立 planner 仍支持相当比例 candidate
```

此时只允许得出：

> **复杂物理驾驶场景中存在不完全等同于场景类别、并可跨环境重复出现的驾驶决策响应结构。**

仍不能写：

```text
Driving Relation 已被最终定义
```

---

# 36. Gate 6 FAIL / STOP

## FAIL-A

```text
response 基本完全按 scene category 分开
```

## FAIL-B

```text
cross-scene similarity 主要由 speed / route geometry 简单解释
```

## FAIL-C

```text
Town13 / Expert 大量否定 PlanT candidate
```

## FAIL-D

```text
大多数 state 不存在 single dominant actor
```

不直接否定总假设，但说明：

```text
single-agent probe 不适合
```

需要升级 multi-agent intervention。

## FAIL-E

```text
offline replay 无法稳定复现 online forward
```

必须先解决工程问题。

---

# 37. 当前目录建议

```text
gate6/
├── town12_manifest.csv
├── town13_manifest.csv
├── town12_discovery_routes.csv
├── scenario_smoke.csv
├── snapshots/
├── replay_check.csv
├── dominant_actor.csv
├── interventions/
├── signatures/
├── pair_candidates.csv
├── town13_validation.csv
├── expert_validation.csv
└── gate6_summary.md
```

---

# 38. 推荐脚本

```text
tools/gate6/
├── 01_build_manifest.py
├── 02_select_routes_greedy.py
├── 03_run_smoke.py
├── 04_collect_snapshots.py
├── 05_replay_snapshot.py
├── 06_find_dominant_actor.py
├── 07_generate_interventions.py
├── 08_build_signatures.py
├── 09_find_pairs.py
└── 10_make_report.py
```

---

# 39. 当前现在只执行到 Replay

请先完成：

```text
Step A
Town12/Town13 manifest

Step B
Town12 greedy route coverage

Step C
四类各 smoke ≥2 instance

Step D
完成语义验收并冻结 routes / instances

Step E
active_scenario / target_actor 映射

Step F
完整 forward snapshot logger

Step G
整路线 5 Hz snapshot

Step H
>=20 snapshot Offline Replay
```

然后暂停。

反馈：

```text
town12_manifest.csv
town12_discovery_routes.csv
scenario_smoke.csv
active_scenario 映射说明
snapshot 字段清单
replay_check.csv
```

Replay PASS 后，再继续 dominant actor / intervention / signature / pair。

---

# 40. 当前禁止事项

Gate 6 完成前不要：

```text
训练 Relation-v1
修改 Relation-v0
新增 TTC / clearance / permission
设计 learned bottleneck
做正式 OOD comparison
上 VAD / UniAD
用 PCA/SVD 定义 Relation
根据 planning-response 好坏事后更换 Discovery route
根据 candidate pair 结果修改 scenario class
```

当前只做：

# Cross-Scenario Driving Equivalence Existence Probe
