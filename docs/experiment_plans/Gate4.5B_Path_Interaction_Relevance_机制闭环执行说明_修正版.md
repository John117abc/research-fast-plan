# Gate 4.5B：Path / Interaction Relevance 机制闭环执行说明（修正版）

> 目标：在**不训练新模型、不改网络结构、不改 Relation-v0 数值定义**的前提下，通过一次最小在线干预验证：
>
> **off-path false threat 是否直接导致 Relation-v0 的 waypoint 收缩与 blocked。**

---

## 1. 当前机制假设

Gate 4.5A 已强烈支持：

```text
相邻车道 / 后方对象
→ 几何 relation 被判为高危险
→ 但实际不进入 Ego 未来行驶通道
→ planner waypoint 收缩
→ Ego blocked
```

当前待验证假设：

> **H2：Relation-v0 缺少 Path / Interaction Relevance。**

Gate 4.5B 只做因果干预，不做正式方法设计。

---

# 2. 固定实验条件

A/B 两个 run 必须全部使用**同一版修改后的代码**。

```text
route = route25
TM seed = 100
checkpoint = 当前 Relation-v0 5 epoch checkpoint
Relation-v0 = 不变
controller = 不变
模型参数 = 不变
训练 = 不进行
```

只允许一个差异：

```text
Run A：mask = OFF
Run B：mask = ON
```

旧 Gate 4.5A 数据保留作为历史复现记录，但**不作为本次正式 A/B 的 Run A**。

---

# 3. Corridor 必须使用 Route Waypoints

## 3.1 禁止使用

```text
pred_path
pred_wps
```

原因：

blocked 时 planner 输出本身会收缩。

如果用 `pred_path / pred_wps` 构造 corridor，会产生：

```text
planner collapse
→ corridor collapse
→ 更多 object 被判 off-path
→ mask 进一步增强
```

形成自反馈，失去因果意义。

---

## 3.2 唯一允许的数据源

```text
Ego future corridor = route waypoints
```

使用当前 waypoint planner / route planner 中已有的未来 route waypoints。

建议范围：

```text
forward_length = 20 ~ 30 m
corridor_half_width = 2.5 m
```

本次实验固定：

```text
corridor_half_width = 2.5 m
```

允许通过 env/config 覆盖，但 Gate 4.5B 本轮**不做参数扫描**。

---

# 4. 最小 in_path 判定

对每个 object 计算其中心点到未来 route polyline / route waypoint 集合的最小距离：

\[
d_{path}(i)
=
\min_j
\|p_i-p_{route,j}\|
\]

判定：

```python
in_path = d_path <= corridor_half_width
```

本轮：

```python
corridor_half_width = 2.5
```

注意：

> 本阶段只要求稳定识别明显的相邻车道 / off-path false threat，不追求最终几何模型。

---

# 5. 干预集合必须严格最小

禁止：

```text
删除全部 off-path objects
```

只允许从当前帧 **top-5 dangerous relations** 中选择干预对象。

一个 object 只有同时满足：

```text
1. 属于 top-5 dangerous relations
2. in_path == False
3. 不是 lead vehicle
```

才允许 mask。

即：

```python
mask_object = (
    is_top5_dangerous
    and (not in_path)
    and (not is_lead_vehicle)
)
```

---

# 6. Lead Vehicle 判定

优先复用现有 lead vehicle 判定。

如果现有代码无法逐 object 判断，则使用本次 debug-only 兜底条件：

```python
is_lead_vehicle = (
    obj_type == 1
    and 0.0 < x < 30.0
    and abs(y) < 2.5
)
```

要求：

> 必须逐对象判断。

不要使用：

```text
has_lead_vehicle = True
```

然后把所有 vehicle 都保护起来。

---

# 7. 无 CARLA object id 时的日志处理

当前 `data_car` 若没有稳定 object id：

```text
object_idx = 当前帧 data_car 中的索引
```

即可。

日志字段命名为：

```text
object_idx
```

不要写成永久 `object_id`，避免误认为其支持跨帧 tracking。

本实验只需要帧内定位，不要求跨帧身份一致。

---

# 8. Mask 后必须重新生成 Planner Features

这是实现中的关键检查项。

如果原逻辑类似：

```python
features = data_car[:, :N]
```

发生在 mask 之前，那么后续即使：

```python
data_car = masked_data_car
```

模型仍可能继续使用旧的 `features`。

因此必须保证顺序为：

```python
# 1. Relation-v0 已计算完成
data_car = ...

# 2. debug mask
if mask_enabled:
    data_car = apply_path_relevance_mask(data_car, ...)

# 3. mask 后重新构造 features
features = build_features_from(data_car)

# 4. forward
model(features, ...)
```

核心验收标准：

> **送入 PlanT forward 的 object features 必须来自 mask 后的 data_car。**

不要只修改 `data_car` 而继续使用 mask 前已经缓存的 `features`。

---

# 9. 建议的最小伪代码

```python
# --------------------------------------------------
# A. 获取 planner input 的 Relation-v0 objects
# --------------------------------------------------
data_car = relation_objects

# --------------------------------------------------
# B. 获取 route waypoints
# 禁止使用 pred_path / pred_wps
# --------------------------------------------------
route_points = get_future_route_waypoints(
    forward_length=30.0
)

# --------------------------------------------------
# C. 只在 Run B 开启 mask
# --------------------------------------------------
if path_mask_enabled:

    dangerous_indices = get_top5_dangerous_indices(data_car)

    keep_mask = [True] * len(data_car)

    for idx in dangerous_indices:

        obj = data_car[idx]

        d_path = min_distance_to_route(
            obj_position=obj.xy,
            route_points=route_points
        )

        in_path = d_path <= corridor_half_width

        is_lead = (
            obj.type == 1
            and 0.0 < obj.x < 30.0
            and abs(obj.y) < 2.5
        )

        should_mask = (
            (not in_path)
            and (not is_lead)
        )

        log_object(
            object_idx=idx,
            d_path=d_path,
            in_path=in_path,
            is_lead=is_lead,
            masked=should_mask
        )

        if should_mask:
            keep_mask[idx] = False

    data_car = apply_keep_mask(data_car, keep_mask)

# --------------------------------------------------
# D. 必须在 mask 后重新构造 features
# --------------------------------------------------
features = build_features_from(data_car)

# --------------------------------------------------
# E. 原模型 forward
# --------------------------------------------------
pred = model(features, ...)
```

---

# 10. 必须记录的日志

## 10.1 Planner 级

```text
frame
ego_speed
desired_speed_raw
mean_speed_raw
hazard_brake
throttle
brake
pred_wps
```

---

## 10.2 Object 级

对 top-5 dangerous objects 记录：

```text
frame
object_idx
type
x
y
current_clearance
predicted_min_clearance
closing_rate
tcpa
d_path
in_path
is_lead
masked
```

---

## 10.3 数量级

```text
num_objects_before_mask
num_objects_after_mask
num_dangerous
num_masked
```

---

# 11. 正式实验设计

## Run A：Baseline

```text
route25
TM seed = 100
Relation-v0 checkpoint
path_mask_enabled = False
corridor_half_width = 2.5
```

目的：

> 使用新版代码重新复现原 blocked。

---

## Run B：Intervention

```text
route25
TM seed = 100
Relation-v0 checkpoint
path_mask_enabled = True
corridor_half_width = 2.5
```

只 mask：

```text
top-5 dangerous
AND
in_path == False
AND
non-lead
```

---

# 12. A/B 必须检查的唯一差异

执行前确认：

```text
checkpoint 相同
TM seed 相同
route 相同
controller 相同
Relation-v0 相同
代码版本相同
corridor 参数相同
```

唯一差异：

```text
Run A：mask OFF
Run B：mask ON
```

---

# 13. 机制闭环判定

## A. H2 因果成立

Run B 在 Run A 的同一 blocked 位置附近出现：

```text
1. 明确的 off-path dangerous object 被 mask
2. mean_speed_raw 明显上升
3. pred_wps 从收缩状态恢复向前展开
4. Ego 开始持续前进
5. 原 blocked 被解除或显著推迟
```

则机制链成立：

```text
off-path false threat
→ Relation-v0 错误压制
→ waypoint collapse / near-stop
→ blocked
```

干预后：

```text
remove off-path false threat
→ planner intent 恢复
→ waypoint 展开
→ progress 恢复
```

结论：

> **H2 完成机制级因果闭环。**

---

## B. H2 部分成立

如果：

```text
mean_speed_raw 明显恢复
pred_wps 有展开
车辆 progress 改善
但最终仍 blocked
```

则：

> **Path / Interaction Relevance 是重要因素，但不是唯一因素。**

此时再分析剩余 Rule / stop-sign / 其他 planner input。

---

## C. H2 不成立

如果 mask 已实际生效，但：

```text
mean_speed_raw 基本不变
pred_wps 仍持续收缩
车辆仍在原位置 blocked
```

则：

> **H2 不能解释当前主要 blocked。**

停止 Path Relevance 扩展，回到 Rule / stop-sign / token / training sufficiency 等方向继续诊断。

---

# 14. Gate 4.5B 成功后的下一步

只有 A 或 B 成立，才进入：

# Relation-v0.5：Path-Relevance Gating

正式逻辑优先采用：

```text
Precise Object State
        ↓
Relation-v0
        ↓
Path / Interaction Relevance
        ↓
过滤 decision-irrelevant objects
        ↓
PlanT
```

暂时不要直接：

```text
Relation-v0 + 第 7 个 handcrafted feature
```

之后再：

```text
重新训练最小 5 epoch
↓
route25 / route28 / route29
↓
Safety + Progress
↓
多 TM seed 稳定性验证
```

---

# 15. Gate 4.5B 当前禁止事项

本阶段不要加入：

```text
Rule Relation
动态安全包络
SURE-Plan
uncertainty
Action Effect
30 epoch
新 planner
RL
LLM / VLM
```

原则保持：

> **一次只验证一个假设。**

---

# 16. 执行前 Checklist

```text
[ ] corridor 只使用 route waypoints
[ ] 未使用 pred_path / pred_wps 构造 corridor
[ ] corridor_half_width 固定 2.5 m
[ ] 只检查 top-5 dangerous objects
[ ] 只 mask off-path + non-lead
[ ] lead vehicle 逐 object 判断
[ ] 无稳定 id 时日志使用 object_idx
[ ] mask 后重新生成 features
[ ] Run A / Run B 均使用新版代码
[ ] A/B 唯一差异是 mask OFF / ON
[ ] route25 + TM seed=100 固定
```

全部满足后再执行正式 Gate 4.5B。
