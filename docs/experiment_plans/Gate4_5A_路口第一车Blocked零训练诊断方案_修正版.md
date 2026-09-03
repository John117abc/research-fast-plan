# Gate 4.5A：路口第一车 Blocked 的零训练诊断方案（修正版）

> 适用阶段：当前 `CARLA + PlanT 2.0 + Exact / Relation-v0` 对照实验  
> 目的：在**不重新训练、不修改 Relation-v0、不引入新模块**的前提下，定位当前观察到的：
>
> **“自车作为路口第一辆车时容易停住不走；如果前面有车，一般不会出现停住不走。”**
>
> 当前只区分两个主要机制：
>
> 1. **H1：规则关系缺失 / Rule Permission 不充分**
> 2. **H2：交互关系过度保守 / Interaction Relation 误判**
>
> 控制层不再作为主要研究分支，只保留最基本日志做保险检查。
>
> 本阶段只做诊断，不做论文结论。

---

# 1. 为什么再次修正 Gate 4.5A

上一版诊断方案仍有三个问题。

---

## 1.1 `creep heuristic` 会覆盖最终 `desired_speed`

当前配置为：

```text
path+wps
```

因此：

```text
pred_speed = None
```

PlanT 在线控制走 waypoint 分支。

原始逻辑大致为：

```python
desired_speed = np.linalg.norm(
    pred_wps[2] - pred_wps[3]
) * 4.0

mean_speed = np.linalg.norm(
    pred_wps[:-1] - pred_wps[1:],
    axis=-1,
).mean() * 4.0

if gt_velocity < 0.01:
    desired_speed = min(mean_speed, 0.1)
```

也就是说：

> **车辆一旦已经停住，最终 `desired_speed` 会被 creep heuristic 强制限制到 `0~0.1 m/s`。**

因此：

```text
只记录最终 desired_speed
```

无法直接判断：

> planner 原本到底是想走，还是 waypoint 本身就几乎完全静止。

所以必须额外记录 creep 覆盖前的原始量。

---

## 1.2 当前 blocked 基本可以归到 Planner 层

纵向控制器的逻辑中：

```text
hazard_brake=True
→ throttle=0
→ brake=True
```

而当：

```text
hazard_brake=False
```

即使 target speed 很小，也会把 target speed 抬到 `minimum_target_speed` 后尝试给油。

结合 creep：

如果长期出现：

```text
ego_speed ≈ 0
mean_speed_raw < 0.05
```

则意味着：

> **模型预测出来的 waypoint 本身已经几乎不向前延伸。**

因此当前研究重点不需要再在 PID / controller 上展开。

控制层只保留：

```text
throttle
brake
hazard_brake
```

作为确认日志。

---

## 1.3 在线不应该记录 `affects_ego`

在线 `PlanT_agent.py` 并不是依靠：

```text
traffic_light["affects_ego"]
```

来判断当前控制 Ego 的交通灯。

真正流程是：

```python
_waypoint_planner.run_step(...)
```

直接返回：

```text
next_light_dist
next_traffic_light
next_stop_dist
next_stop_sign
```

然后只有：

```text
next_traffic_light is not None
and next_light_dist < 30
```

时，才把对应交通灯加入 `label_raw`。

因此在线最可靠的规则关系信息是：

```text
next_traffic_light
next_light_dist
next_stop_sign
next_stop_dist
```

而不是不存在或不稳定的 `affects_ego` 字段。

---

# 2. 当前真正要验证的问题

当前现象：

```text
无前车：
自车作为路口第一辆车
→ 更容易 blocked

有前车：
前车开始通过路口
→ 自车通常也能继续走
```

我们现在只区分下面两个机制。

---

# 3. 假设 H1：Rule Permission 缺失

当前 PlanT 对交通灯的输入机制本质上是：

```text
Red / Yellow
→ traffic_light token 存在

Green
→ traffic_light token 消失
```

所以绿灯不是：

```text
显式 Green token
```

而是：

```text
约束对象消失
```

Exact 模型和 Relation-v0 都共享这个基本机制。

但 Relation-v0 可能因为大量 object 精确信息被压缩后，更依赖：

```text
“是否有某种明确的可通行关系”
```

当自车处于路口第一车位置时：

```text
Red/Yellow token 消失
```

并不等价于显式告诉模型：

```text
“当前允许进入路口”
```

因此可能出现：

```text
灯已 Green
附近也没有明显危险对象
但 planner 仍输出近乎静止 waypoint
```

这时优先支持：

# **H1：缺少显式 Rule Permission**

---

# 4. 假设 H2：Interaction Relation 过度保守

另一种可能是：

绿灯以后，规则约束已经解除，但某个周围对象在 Relation-v0 中仍然表现为：

```text
min_clearance 很小
closing 很大
TCPA 很短
```

然而实际场景中：

```text
这个对象并不会进入 Ego 的未来行驶通道
```

例如：

- 横向道路上的车辆；
- 邻车道车辆；
- 路口附近但与 Ego route 无冲突的对象；
- bounding-circle / constant-velocity proxy 导致的虚假冲突。

这时模型可能形成：

```text
“路口附近危险 → 不走”
```

而当前车存在时：

```text
前车启动
```

又给了模型一个额外行为线索，因此能跟随通过。

这种情况优先支持：

# **H2：缺少 Path / Interaction Relevance**

---

# 5. 本阶段严格不做什么

Gate 4.5A 当前：

```text
不训练新模型
不改 Relation-v0
不改 Transformer
不改 planning head
不改 loss
不改 controller
不加动态安全包络
不加 uncertainty
不加 path relevance
不加 rule relation
```

唯一允许的修改：

```text
增加 debug log
```

目的：

> **先把 blocked 时 planner 为什么选择不前进看清楚。**

---

# 6. 使用现有 checkpoint

继续使用当前已有：

```text
Exact 5 epoch checkpoint
Relation-v0 5 epoch checkpoint
```

不要重新训练。

例如：

```bash
export EXACT_CKPT="..."
export REL_CKPT="..."
```

核验：

```bash
python - "$EXACT_CKPT" "$REL_CKPT" <<'PY'
import sys
import torch

for p in sys.argv[1:]:
    ckpt = torch.load(
        p,
        map_location="cpu",
        weights_only=False,
    )

    cfg = ckpt["hyper_parameters"]["cfg"]
    tr = cfg["model"]["training"]

    print(p)
    print(
        "input_representation =",
        tr.get("input_representation")
    )
    print(
        "input_ego_speed      =",
        tr.get("input_ego_speed")
    )
PY
```

确认：

```text
Exact:
input_representation = exact

Relation-v0:
input_representation = relation
```

---

# 7. 第一阶段固定 Traffic Manager Seed

为了尽可能复现同一个 blocked 场景：

```text
第一阶段固定：
TM seed = 100
```

不要一上来换多个 seed。

当前 evaluator 默认通常就是：

```text
--traffic-manager-seed=100
```

建议命令中显式写出：

```bash
--traffic-manager-seed=100
```

目的：

> **先让同一个失败场景尽量稳定重现。**

只有原因定位以后，再进入：

```text
TM seed = 100
101
102
103
104
```

验证现象是否稳定。

---

# 8. 优先诊断路线

优先：

```text
route25
route28
```

因为当前 Relation-v0 已经明显出现 blocked。

其中：

```text
route29
```

可以继续作为正常行为参照。

第一目标不是重新跑完整 benchmark。

第一目标是：

> 找到至少一个能稳定复现“路口第一车不走”的位置。

---

# 9. 当前最关键的 8 类日志

Gate 4.5A 不再记录大量无关字段。

重点只保留下面这些。

| 日志 | 作用 |
|---|---|
| `ego_speed` | 确认 blocked |
| `desired_speed_raw` | waypoint 局部速度意图 |
| `mean_speed_raw` | **判断 planner 是否真正输出停车，最关键** |
| `hazard_brake` | 确认为什么进入制动 |
| `next_light_state` | 当前相关灯状态 |
| `next_light_dist` | 当前灯距 Ego 多远 |
| `num_type5_tokens` | traffic light 是否真正进入模型 |
| `dangerous_relations` | 判断是否有周围 relation 对象压制模型 |

辅助保留：

```text
throttle
brake
pred_wps
pred_path
has_lead_vehicle
```

---

# 10. 修改 `_get_control()`：记录 creep 前原始量

找到当前：

```python
if pred_speed is not None:
    ...
else:
    desired_speed = ...
    mean_speed = ...

    if gt_velocity < 0.01:
        desired_speed = min(mean_speed, 0.1)
```

建议修改为：

```python
if pred_speed is not None:
    pred_speed = pred_speed.detach().squeeze().cpu()
    pred_speed = F.softmax(pred_speed, dim=0)
    pred_speed = pred_speed.numpy()

    pred_speed = np.array(
        [
            0.0,
            4.0,
            8.0,
            10.0,
            13.88888888,
            16.0,
            17.77777777,
            20.0,
        ]
    ) * pred_speed

    desired_speed_raw = float(sum(pred_speed))
    mean_speed_raw = None

    desired_speed = desired_speed_raw

else:
    desired_speed_raw = float(
        np.linalg.norm(
            pred_wps[2] - pred_wps[3]
        ) * 4.0
    )

    mean_speed_raw = float(
        np.linalg.norm(
            pred_wps[:-1] - pred_wps[1:],
            axis=-1,
        ).mean() * 4.0
    )

    desired_speed = desired_speed_raw

    # 原官方 creep
    if gt_velocity < 0.01:
        desired_speed = min(
            mean_speed_raw,
            0.1,
        )
```

随后：

```python
hazard_brake = desired_speed < 0.05

throttle, brake = (
    self.lon_pid.get_throttle_and_brake(
        hazard_brake,
        desired_speed,
        gt_velocity,
    )
)
```

如果你不想改变原变量调用形式，也可以仅额外定义：

```python
hazard_brake_debug = desired_speed < 0.05
```

然后原调用保持不变。

---

# 11. 为什么 `mean_speed_raw` 是当前最重要的量

车辆已经停住时：

```text
gt_velocity < 0.01
```

最终：

```text
desired_speed
=
min(mean_speed_raw, 0.1)
```

如果：

```text
mean_speed_raw < 0.05
```

则：

```text
desired_speed < 0.05
```

进一步：

```text
hazard_brake = True
```

因此：

\[
\boxed{
mean\_speed\_raw < 0.05
}
\]

可以近似理解为：

> **planner 输出的整条 waypoint 序列几乎没有向前推进。**

这个量比最终 `desired_speed` 更能反映模型本身的驾驶意图。

---

# 12. 在 `run_step()` 中记录真实 Route Traffic Light 状态

`_waypoint_planner.run_step()` 已经返回：

```python
_, _, _, \
next_light_dist, \
next_traffic_light, \
next_stop_dist, \
next_stop_sign, \
speed_limit = self._waypoint_planner.run_step(
    tick_data["gps"]
)
```

因此直接构造：

```python
if next_traffic_light is not None:
    next_light_state = str(
        next_traffic_light.state
    )
    next_light_id = int(
        next_traffic_light.id
    )
else:
    next_light_state = None
    next_light_id = None
```

同时记录：

```python
next_light_dist_debug = (
    float(next_light_dist)
    if next_light_dist is not None
    else None
)
```

同理可辅助记录：

```text
next_stop_dist
next_stop_sign 是否存在
```

但第一轮分析重点放 traffic light。

---

# 13. 不再记录 `affects_ego`

当前 Gate 4.5A：

```text
不要读取：
x.get("affects_ego")
```

原因：

在线当前相关规则对象已经由：

```text
waypoint planner
```

提供：

```text
next_traffic_light
next_stop_sign
```

这一信息比 `affects_ego` 更直接。

---

# 14. 记录最终进入模型的 type=5 token 数

在 `get_input_batch()` 中：

```text
data_car
```

完成官方 object 构造以及 Relation 转换以后，统计：

```python
num_type5_tokens = sum(
    int(round(float(row[0]))) == 5
    for row in data_car
)

num_type4_tokens = sum(
    int(round(float(row[0]))) == 4
    for row in data_car
)
```

重点验证：

```text
Red / Yellow：
next_light_state = Red / Yellow
num_type5_tokens > 0

Green：
next_light_state = Green
num_type5_tokens = 0
```

这是当前最重要的规则输入机制检查之一。

---

# 15. 记录 Relation-v0 中最危险的 5 个对象

只对：

```text
input_representation = relation
```

执行。

当前 relation token 假设为：

```text
[
 type,
 current_clearance,
 predicted_min_clearance,
 closing_rate,
 TCPA,
 cos(bearing),
 sin(bearing)
]
```

第一版按：

```text
predicted_min_clearance
```

从小到大排序。

示意：

```python
relation_objs = []

for row in data_car:
    type_id = int(
        round(float(row[0]))
    )

    # rule object 暂不放入
    # “危险物理对象”排序
    if type_id in (4, 5):
        continue

    relation_objs.append({
        "type": type_id,
        "current_clearance": float(row[1]),
        "min_clearance": float(row[2]),
        "closing": float(row[3]),
        "tcpa": float(row[4]),
        "cos_bearing": float(row[5]),
        "sin_bearing": float(row[6]),
    })

dangerous_relations = sorted(
    relation_objs,
    key=lambda x: x["min_clearance"],
)[:5]
```

如果你本地 Relation-v0 列顺序不同：

> **严格以本地 `relation_features.py` 为准。**

---

# 16. `get_input_batch()` 推荐返回 debug 信息

为了避免在 `_get_control()` 中拿不到 `data_car`，可以让 `get_input_batch()` 额外返回 debug 信息。

例如：

```python
return input_batch, {
    "num_type5_tokens": num_type5_tokens,
    "num_type4_tokens": num_type4_tokens,
    "dangerous_relations": dangerous_relations,
}
```

然后 `_get_control()`：

```python
input_batch, relation_debug = (
    self.get_input_batch(
        label_raw,
        input_data,
    )
)
```

如果不想改函数返回格式，也可以：

```python
self._latest_relation_debug = {...}
```

本轮只是 debug，优先选择对现有代码侵入最小的方式。

---

# 17. 记录是否存在前车

这个字段只用于验证当前观察：

```text
有前车时通常能走
```

不参与模型输入。

第一版简单定义：

```python
has_lead_vehicle = False

for row in data_car:
    type_id = int(
        round(float(row[0]))
    )

    if type_id != 1:
        continue

    # Exact 下 x/y 是真实相对位置，
    # Relation 下已经不是 x/y，
    # 所以最好在 relationize 之前
    # 从 raw data_car 判断。
```

建议：

> **在 relationize 之前保存一份 `data_car_exact_raw`，专门做 debug。**

例如：

```python
data_car_exact_raw = [
    list(row)
    for row in data_car
]
```

然后：

```python
for row in data_car_exact_raw:
    type_id = int(
        round(float(row[0]))
    )

    if type_id != 1:
        continue

    x = float(row[1])
    y = float(row[2])

    if (
        x > 0.0
        and x < 30.0
        and abs(y) < 2.5
    ):
        has_lead_vehicle = True
        break
```

这只是粗日志，不作为论文指标。

---

# 18. 推荐 JSONL 日志结构

建议：

```text
outputs/gate45a/
```

下面：

```text
exact_route25_tm100.jsonl
relation_route25_tm100.jsonl
exact_route28_tm100.jsonl
relation_route28_tm100.jsonl
```

每帧记录：

```python
record = {
    "frame": int(
        GameTime.get_frame()
    ),

    "ego_speed": float(
        gt_velocity
    ),

    "desired_speed_raw": (
        float(desired_speed_raw)
        if desired_speed_raw is not None
        else None
    ),

    "mean_speed_raw": (
        float(mean_speed_raw)
        if mean_speed_raw is not None
        else None
    ),

    "desired_speed_after_creep": float(
        desired_speed
    ),

    "hazard_brake": bool(
        hazard_brake
    ),

    "throttle": float(
        throttle
    ),

    "brake": bool(
        brake
    ),

    "next_light_id": next_light_id,

    "next_light_state": (
        next_light_state
    ),

    "next_light_dist": (
        next_light_dist_debug
    ),

    "num_type5_tokens": int(
        relation_debug[
            "num_type5_tokens"
        ]
    ),

    "num_type4_tokens": int(
        relation_debug[
            "num_type4_tokens"
        ]
    ),

    "has_lead_vehicle": bool(
        relation_debug[
            "has_lead_vehicle"
        ]
    ),

    "dangerous_relations": (
        relation_debug[
            "dangerous_relations"
        ]
    ),

    "pred_wps": (
        pred_wps.tolist()
        if pred_wps is not None
        else None
    ),

    "pred_path": (
        pred_path.tolist()
        if pred_path is not None
        else None
    ),
}
```

然后：

```python
with open(
    debug_log_path,
    "a",
) as f:
    f.write(
        json.dumps(record)
        + "\n"
    )
```

---

# 19. 第一阶段运行方式

固定：

```text
TM seed = 100
```

Exact：

```bash
export PLANT_CHECKPOINT="$EXACT_CKPT"

python \
leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes="$ROUTE_25_XML" \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/gate45a_exact_route25.json \
  --timeout=300 \
  --traffic-manager-seed=100
```

Relation：

```bash
export PLANT_CHECKPOINT="$REL_CKPT"

python \
leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes="$ROUTE_25_XML" \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/gate45a_relation_route25.json \
  --timeout=300 \
  --traffic-manager-seed=100
```

route28 同理。

---

# 20. 第一阶段不要先追求多次统计

首先目标是：

```text
抓到一个稳定 blocked 案例
```

然后分析：

```text
Green 前后
3~10 秒
```

重点看：

```text
next_light_state
num_type5_tokens
mean_speed_raw
dangerous_relations
has_lead_vehicle
```

---

# 21. H1：Rule Permission 的判定标准

如果 blocked 时出现：

```text
next_light_state = Green

num_type5_tokens = 0

ego_speed ≈ 0

mean_speed_raw < 0.05
持续若干秒
```

同时：

```text
dangerous_relations
中没有明显极端危险对象
```

例如：

```text
min_clearance 并不小
closing 不明显
TCPA 不短
```

那么：

# **优先支持 H1**

即：

> 当前模型在规则约束解除后，没有获得足够明确的“允许进入路口”驾驶关系。

后续应该验证：

```text
显式 R_rule
```

而不是恢复 Exact traffic-light token。

---

# 22. 如果 H1 成立，下一版应是什么

暂定：

```text
R_rule
=
[
 permission,
 distance_to_rule_boundary,
 route_relevance
]
```

其中：

```text
Red:
permission = 0

Yellow:
permission = 0 / caution

Green:
permission = 1
```

关键点：

> **Green 必须显式存在。**

因为我们真正想表达的不是：

```text
traffic light 的 x/y/yaw/width/length
```

而是：

```text
“当前这个规则对我的动作意味着什么？”
```

这才符合论文核心思想。

---

# 23. H2：Interaction Relation 的判定标准

如果 blocked 时出现：

```text
next_light_state = Green

num_type5_tokens = 0

ego_speed ≈ 0

mean_speed_raw < 0.05
```

同时：

```text
dangerous_relations
中存在一个或多个明显极端对象
```

例如：

```text
min_clearance 很小
closing 明显
TCPA 很短
```

但通过场景画面 / GT 检查发现：

> 这些对象实际上不会进入 Ego 的未来运动通道。

那么：

# **优先支持 H2**

即：

> 当前 Relation-v0 只表达几何接近，却缺少“这个对象是否真正与我的未来路径发生冲突”的关系。

---

# 24. 如果 H2 成立，下一版应是什么

不要优先继续优化：

```text
clearance
TCPA
bounding circle
```

而是加入：

# **Path / Interaction Relevance**

即回答：

> **对象未来占用是否会进入 Ego 的未来运动通道？**

概念上：

\[
AgentFutureOccupancy
\cap
EgoRouteCorridor
\]

第一版可以利用：

```text
CARLA GT
+
constant velocity
+
route corridor
```

构造一个简单 proxy。

目标不是一次做到最终论文版，而是验证：

```text
加入 path relevance 后，
路口第一车 blocked 是否明显减少。
```

---

# 25. 控制层只做最小确认

如果出现：

```text
mean_speed_raw > 0.05
```

甚至：

```text
mean_speed_raw 明显较高
```

但车辆仍然长期不动，

再检查：

```text
hazard_brake
throttle
brake
```

但这不作为当前主要研究假设。

只要：

```text
mean_speed_raw < 0.05
```

且长期 blocked，

就优先认为：

```text
planner 本身输出了停车行为。
```

---

# 26. Exact 和 Relation 必须对同一位置比较

不要只分析 Relation。

同一个 route / seed 下：

```text
Exact 为什么会走？
Relation 为什么不走？
```

重点比较：

```text
mean_speed_raw
next_light_state
num_type5_tokens
dangerous relation
```

特别希望看到：

```text
Green 后：

Exact:
mean_speed_raw 上升
→ 开始前进

Relation:
mean_speed_raw 继续接近 0
→ blocked
```

这比只看最终 completion 更有诊断价值。

---

# 27. 第一阶段原因定位后，再做多 TM seed

只有当你已经知道：

```text
H1 或 H2 哪个更可能
```

之后，才开始：

```text
TM seed = 100
101
102
103
104
```

重复同一路线。

统计：

```text
P(blocked)
```

并记录：

```text
first_at_intersection
has_lead_vehicle
```

目的是验证：

> 当前发现不是 TM seed=100 的偶然事件。

---

# 28. 多 seed 阶段建议统计

例如：

| representation | TM seed | route | first-at-intersection blocked |
|---|---:|---|---|
| Exact | 100 | 25 | No |
| Exact | 101 | 25 | No |
| Relation | 100 | 25 | Yes |
| Relation | 101 | 25 | Yes |
| Relation | 102 | 25 | No |

最终可以计算：

\[
P(
blocked
\mid
Relation,
first\ at\ intersection
)
\]

和：

\[
P(
blocked
\mid
Exact,
first\ at\ intersection
)
\]

当前只作为诊断统计，不作为最终论文实验。

---

# 29. 当前 Gate 4.5A 的决策树

```text
                  路口第一车 blocked
                         │
                         ↓
              mean_speed_raw < 0.05 ?
                         │
                ┌────────┴────────┐
                │                 │
               Yes                No
                │                 │
                ↓                 ↓
        Planner 主动选择停车      再查控制层
                │
                ↓
        next_light_state = Green ?
                │
                ↓
    ┌──────────────────────────┐
    │                          │
无明显危险 Relation       有明显危险 Relation
    │                          │
    ↓                          ↓
H1: Rule Permission      H2: Interaction
        缺失                  过度保守
    │                          │
    ↓                          ↓
设计 R_rule            设计 Path Relevance
```

---

# 30. 本阶段可以回答什么

Gate 4.5A 可以回答：

```text
1. blocked 是否主要来自 planner 自身输出停车？
2. Green 后模型是否仍输出近乎静止 waypoint？
3. Green 时 type=5 token 是否已经消失？
4. blocked 时是否存在某个危险 relation 对象持续压制模型？
5. 当前首要缺项更像 Rule Relation 还是 Path Relevance？
```

---

# 31. 本阶段不能证明什么

不能证明：

```text
1. Rule Relation 一定是最终正确表示；
2. Path Relevance 一定是最终正确表示；
3. Relation 一定优于 Exact；
4. 低维关系已经证明提高 OOD；
5. 当前 relation 已经是最小充分关系；
6. 端到端长尾失败是因为精确物理状态。
```

---

# 32. 当前成功标准

Gate 4.5A 不看：

```text
Driving Score 提高多少
```

而看：

> **是否能把“第一辆车路口 blocked”的主要机制明确定位到 H1 或 H2。**

例如：

```text
Case A：

Green
type5 token = 0
mean_speed_raw ≈ 0
无危险 relation
→ H1
```

或者：

```text
Case B：

Green
type5 token = 0
mean_speed_raw ≈ 0

某横向车：
min_clearance 极小
TCPA 很短

但实际上不进入 Ego route
→ H2
```

只要能稳定得到这种证据，Gate 4.5A 就完成。

---

# 33. 当前推荐执行顺序

```text
1. 保留现有 Exact / Relation-v0 checkpoint
        ↓
2. 只加 debug log
        ↓
3. 固定 TM seed=100
        ↓
4. 重跑 route25 / route28
        ↓
5. 找稳定的第一车 blocked 路口
        ↓
6. 分析 Green 前后 3~10 秒
        ↓
7. 看 mean_speed_raw
        ↓
8. 区分 H1 / H2
        ↓
9. 只针对命中原因设计下一版最小补丁
        ↓
10. 再用多个 TM seed 验证稳定性
```

---

# 34. 当前不要做的事情

Gate 4.5A 结果出来以前，不建议同时加入：

```text
Rule Exact
SURE-Plan
动态安全包络
uncertainty
reachable set
Action Effect
30 epoch 正式训练
新的 planner
新的 RL
```

原因：

> **现在最重要的是知道 Relation-v0 为什么在“无前车、路口第一车”这个具体状态下选择停车。**

---

# 35. 这一轮对研究主线的意义

当前核心研究问题仍然是：

> **复杂驾驶场景中的精确物理状态虽然高度多样，但真正决定驾驶行为的关系结构是否可能低维且可复用？**

Relation-v0 当前已经验证了一部分：

```text
Ego ↔ Agent
几何 / 运动安全关系
```

但闭环失败开始反向告诉我们：

> **仅仅“距离 / 余量 / 接近 / TCPA / 方向”可能还不是足够的驾驶关系。**

Gate 4.5A 的价值就在于：

```text
不凭直觉继续加特征
```

而是让真实闭环失败告诉我们：

```text
下一类真正必要的关系
到底更像：

Rule Relation
还是
Path / Interaction Relation
```

这才是当前阶段最符合论文主线的推进方式。
