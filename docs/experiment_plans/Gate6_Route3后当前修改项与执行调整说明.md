# Gate 6：Route3 后当前修改项与执行调整说明

> 本文只记录 Route3 Smoke 后需要立即修正的 Gate 6 执行项。
>
> 当前原则：**暂停售跑 Route14 / Route1，先修路线选择、实例映射、Forward Snapshot 与 Replay。**

---

# 1. Route3 当前结论

Route3：

```text
PlanT-Reference
TM seed = 100
Town12

route completion = 62.67%
最终 blocked
CARLA 无 crash
运行约 70 min
```

当前暴露出三个问题：

```text
1. 整条路线过长，目标 scenario 可能位于路线后段；
   PlanT 提前 blocked 后，尾部目标实例无法采到。

2. 当前日志无法稳定回答：
   “某个 actor / token 属于哪个具体 scenario instance”。

3. 当前尚未保存完整 model.forward 输入，
   后续 Offline Replay / Intervention 无法可靠执行。
```

因此：

> **当前不继续补跑 Route14 / Route1。**

---

# 2. 修改项一：Route Selector 改为“可到达覆盖优先”

原 greedy 只考虑：

```text
每条 route 包含多少目标 scenario instance
```

现在改为同时考虑：

```text
目标 instance 数
+
scenario trigger 在 route 中的位置
+
route 总长度 / 预计执行时间
```

---

## 2.1 新增 trigger progress

对每个 scenario instance 计算：

```text
trigger_progress ∈ [0,1]
```

表示该 trigger 在整条 route 中的大致进度。

例如：

```text
0.20 = route 前 20%
0.75 = route 后 75%
```

---

## 2.2 第一轮路线优先级

优先选择：

```text
目标场景数量多
+
目标 trigger 集中在前 50%~60%
+
route 相对较短
```

不再因为：

```text
route 总实例数最多
```

就直接优先。

---

## 2.3 新输出

重新生成：

```text
gate6/town12_discovery_routes_reachable.csv
```

至少记录：

```text
route_id
route_length
scenario_type
unique_instance_id
trigger_progress
reachable_target_count
total_target_count
estimated_runtime
```

---

# 3. 修改项二：Runtime Scenario-Instance Mapping 必须先实现

不能再仅依靠 XML trigger 点人工猜 scenario window。

必须建立：

```text
XML scenario instance
↔
runtime scenario
↔
actor
↔
PlanT token
```

的映射链。

---

## 3.1 Manifest 增加字段

增加：

```text
scenario_xml_name
```

继续保留：

```text
route_id
scenario_type
trigger_x
trigger_y
trigger_yaw
unique_instance_id
```

---

## 3.2 首选运行时映射键

优先：

```text
route_id
+
scenario_xml_name
```

映射：

```text
runtime active scenario
→ unique_instance_id
```

trigger 坐标只作为：

```text
二次校验
去重
异常排查
```

---

## 3.3 先做最小映射验证

不要先重跑长路线。

找一条较短、目标 scenario 靠前的 route，打印：

```text
XML:
route_id
scenario_xml_name
scenario_type
unique_instance_id

Runtime:
active scenario name
actor_id
actor scenario source
PlanT token index
```

确认：

```text
scenario_xml_name
↔
runtime scenario
```

能够稳定对应。

---

## 3.4 如果 XML name 不能唯一映射

升级为：

```text
route_id
+
scenario_xml_name
+
trigger_x/y/yaw
```

如果仍然无法稳定匹配：

> **暂停 Gate 6，继续沿 RouteScenario / ScenarioManager 排查 instance-level 标识。**

---

# 4. 修改项三：实现完整 Forward Snapshot Logger

以后每次 CARLA 运行都必须留下可供离线分析的数据。

Snapshot 保存位置固定为：

```text
所有官方 filtering 完成
↓
x_objs / idxs 已形成
↓
route_original 已形成
↓
speed_limit 已形成
↓
BEV 已形成
↓
【保存 snapshot】
↓
model.forward(...)
```

---

## 4.1 必须保存的 Forward Payload

```text
x_objs
idxs
route_original
speed_limit
BEV
```

同时保存：

```text
pred_wps_online
pred_path_online
```

保持：

```text
dtype
shape
token order
batch dimension
```

不变。

---

## 4.2 必须保存 actor / token 映射

每帧记录：

```text
actor_id
actor_type
scenario_xml_name
unique_instance_id
token_idx
x
y
yaw
speed
width
length
```

---

## 4.3 Ego / Route 信息

保存：

```text
frame
timestamp
route_id
route_progress
ego_speed
ego_world_pose
scenario_active
scenario_overlap
```

---

# 5. 修改项四：Scenario Active Window 改为运行时定义

有效 snapshot 只有同时满足：

```text
1. 目标 scenario 当前 active
2. 当前 frame 能映射到唯一 unique_instance_id
3. 目标 scenario actor 已进入 PlanT token
```

才进入目标 scenario 数据集。

如果：

```text
多个目标 scenario 同时 active
```

标记：

```text
scenario_overlap = True
```

第一轮：

```text
不进入 single-dominant 样本池
```

但原始日志保留。

---

# 6. 修改项五：Smoke 判定标准调整

Smoke 不再要求：

```text
整条 route 必须完成
```

Smoke 只验证：

```text
1. scenario 是否真实触发
2. target actor 是否出现
3. target actor 是否进入 PlanT token
4. runtime instance 是否能稳定映射
5. 该 scenario 是否形成预期物理交互
```

五项满足：

```text
Smoke PASS
```

即使整条 route 后续 blocked：

```text
不影响已经完成验证的 instance
```

---

# 7. 四类场景的 Smoke 语义要求

## 7.1 HardBreakRoute

确认：

```text
lead actor 出现
lead actor 位于 Ego 前方
lead actor 真实 braking / deceleration
Ego 对该 actor 有规划响应
```

---

## 7.2 ParkingCutIn

确认：

```text
目标车辆发生真实 lateral cut-in
进入 PlanT token
对 Ego planning 产生实际影响
```

---

## 7.3 VehicleTurningRoute

确认：

```text
turning vehicle 是主要动态交互对象
不是 stop-sign / traffic-light 在主导当前决策
```

如果该类多数 instance 语义验收失败：

```text
C → DynamicObjectCrossing
```

此时后续 unseen scenario validation 预先改为：

```text
StaticCutIn
或
CrossingBicycleFlow
```

替换规则必须在 response analysis 前冻结。

---

## 7.4 PedestrianCrossing

确认：

```text
pedestrian 真实横穿 / 接近 Ego future path
进入 PlanT token
对 planning 产生实际影响
```

---

# 8. 修改项六：先做短路线 Pilot，不继续长路线 Smoke

当前执行顺序改为：

```text
Step 1
重新计算“可到达覆盖”路线

Step 2
选择 1 条：
较短
+
目标 scenario 靠前
的 Town12 route

Step 3
实现 runtime scenario-instance mapping

Step 4
实现完整 forward snapshot logger

Step 5
跑一次短 route pilot

Step 6
确认：
scenario
→ actor
→ token
→ snapshot
完整链路成立

Step 7
随机 snapshot 做 offline replay
```

---

# 9. Offline Replay 仍然是硬 Gate

Replay 输入：

```text
x_objs
idxs
route_original
speed_limit
BEV
```

输出：

```text
pred_wps_offline
```

比较：

```text
pred_wps_offline
≈
pred_wps_online
```

要求：

```text
仅浮点级误差
```

---

## Replay FAIL

如果明显不一致：

```text
立即停止：
dominant actor
intervention
signature
pair analysis
```

先修 Replay。

---

# 10. 当前明确暂停的工作

现在不要执行：

```text
Route14 长路线 smoke
Route1 长路线 smoke
dominant actor
intervention
response signature
pair search
Town13 validation
Expert validation
```

---

# 11. 当前最新执行顺序

```text
A. 修改 route selector
   → reachable coverage

B. Manifest 增加 scenario_xml_name
   → runtime instance mapping

C. 实现 Forward Snapshot Logger

D. 找一条短且目标场景靠前的 Town12 route

E. 做一次 Pilot Smoke

F. 验证：
   scenario → actor → token → snapshot

G. >=20 snapshots Offline Replay

H. Replay PASS 后暂停并反馈
```

---

# 12. 当前 PlanT 基座判定

Route3：

```text
62.67% 后 blocked
```

当前：

```text
不判 PlanT-Reference FAIL
```

原因：

```text
Gate 6 需要的是局部 scenario planning probe，
不是要求每条长 route 100% completion。
```

但是，如果经过：

```text
短路线
+
目标场景靠前
+
正确 runtime mapping
```

以后，PlanT 仍在大量目标 scenario 到达前系统性 blocked：

> **应重新评估 PlanT 是否适合作为该类 Gate 6 场景的 planning probe。**

---

# 13. 下一次需要反馈的结果

请优先反馈：

```text
1. 新 reachable route coverage 表
2. 选中的短 pilot route
3. scenario_xml_name ↔ runtime scenario 映射结果
4. snapshot 实际保存字段
5. replay_check.csv
```

在这五项确认前，不继续 Gate 6 后半段。
