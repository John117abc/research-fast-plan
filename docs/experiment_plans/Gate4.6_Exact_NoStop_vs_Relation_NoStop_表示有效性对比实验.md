# Gate 4.6：Exact-NoStop vs Relation-NoStop 表示有效性对比实验

> **目的**：暂时移除当前已确认存在 stop-sign deadlock 的停车牌规则输入，降低共享工程问题对比较结果的干扰，直接检查：
>
> **Relation-v0 在只训练 5 epoch 的条件下，是否仍能保留接近 Exact 的基本驾驶能力。**
>
> 本实验验证的是 **Relation Representation Viability / Decision Sufficiency**，不是验证停车规则能力。

---

# 1. 术语说明

本方案中的“去除停止线”统一指：

```text
从 planner input 中移除 stop-sign / 停车牌规则 token（type=4）
```

不是：

```text
修改 CARLA 地图
删除物理停止线
修改 route
修改 stop-sign actor
修改 controller
```

后续日志和代码建议统一命名：

```text
remove_stop_sign_token
```

避免“停止线 / 停车牌”混用。

---

# 2. 核心问题

本实验只回答：

> **在 Exact 和 Relation 都不接收 type=4 stop-sign token，并且训练和在线保持一致的情况下，Relation-v0 是否还能达到与 Exact-NoStop 接近的基本闭环驾驶能力？**

不回答：

```text
Relation-v0 是否最终优于 Exact
停车牌规则最终如何表示
是否需要 R_rule
是否需要 Path Relevance
是否需要更长期训练
```

---

# 3. 实验组

完整设计为 2×2：

| Representation | Stop-sign token | 用途 |
|---|---:|---|
| Exact | ON | 原始 Exact 参考 |
| Relation-v0 | ON | 原始 Relation 参考 |
| Exact-NoStop | OFF | 新训练 |
| Relation-NoStop | OFF | 新训练 |

当前最关键比较：

```text
Exact-NoStop
vs
Relation-NoStop
```

---

# 4. 推荐执行方式

## Phase A：快速可行性验证

为了减少无效训练，本轮先只新训练：

```text
Exact-NoStop
Relation-NoStop
```

均训练：

```text
5 epoch
```

原有：

```text
Exact 5 epoch
Relation-v0 5 epoch
```

保留为历史参考。

如果 NoStop 对比出现明确正面信号，再进入 Phase B。

---

## Phase B：正式 2×2 对照

如果后续需要形成论文级证据，则在**同一版最终代码**下重新训练全部四组：

```text
Exact + Stop
Relation + Stop
Exact-NoStop
Relation-NoStop
```

当前 Gate 4.6 不要求立即执行 Phase B。

---

# 5. 最重要的公平性要求

Exact-NoStop 与 Relation-NoStop 必须保持：

```text
相同训练 split
相同训练数据
相同 epoch = 5
相同 batch size
相同 optimizer
相同 learning rate
相同 random seed
相同 PlanT backbone
相同 planning head
相同 route / road BEV
相同 controller
相同 input_ego_speed 设置
相同 checkpoint 选择规则
```

唯一主要差异：

```text
Exact-NoStop：
object representation = Exact

Relation-NoStop：
object representation = Relation-v0
```

两边都：

```text
remove_stop_sign_token = True
```

---

# 6. Stop-sign token 必须在训练和在线同时删除

禁止只在 inference 删除。

否则产生：

```text
train 时看过 type=4
test 时突然没有 type=4
```

形成额外 distribution shift。

因此必须保证：

```text
Training Dataset planner input
        ↓
删除 type=4

Online PlanT_agent planner input
        ↓
删除 type=4
```

两处必须调用同一个过滤函数。

---

# 7. 建议统一实现函数

建议新增一个共享函数，例如：

```python
def filter_planner_tokens(data_car, remove_stop_sign_token=False):
    if not remove_stop_sign_token:
        return data_car

    return [
        token for token in data_car
        if int(token[0]) != 4
    ]
```

具体 tensor / list 写法按当前代码实现调整。

要求：

> Dataset 与 PlanT_agent 共用同一份逻辑，避免 training representation 与 online representation 不一致。

---

# 8. 插入位置

必须在：

```text
官方 object / rule token 已经构造完成
        ↓
planner input 最终形成之前
```

执行过滤。

不要修改：

```text
CARLA GT
route planner
forecasting target
controller
stop-sign actor
cleared_stop_sign 原始状态机
```

本实验只改变：

```text
planner 实际看到的 token
```

---

# 9. Exact-NoStop 训练输入

原：

```text
[type, x, y, yaw, speed, width, length]
```

处理：

```text
如果 type == 4
→ 不进入 planner input

其他 token
→ 完全保持原 Exact 表示
```

禁止顺手删除：

```text
traffic light
vehicle
walker
其他 rule token
```

---

# 10. Relation-NoStop 训练输入

原 Relation-v0：

```text
[type,
 current_clearance,
 predicted_min_clearance,
 closing_rate,
 time_to_closest_approach,
 cos(bearing),
 sin(bearing)]
```

处理：

```text
如果 type == 4
→ 不进入 planner input

其他 token
→ Relation-v0 完全不变
```

本轮禁止增加：

```text
Path Relevance
Rule Permission
stop_completed
新 relation feature
```

---

# 11. 训练前 sanity check

两组各随机检查至少若干 batch。

必须确认：

## Exact-NoStop

```text
num_type4_tokens = 0
其他 type 正常
input_ego_speed 正常
features shape 正常
```

## Relation-NoStop

```text
num_type4_tokens = 0
Relation-v0 数值正常
其他 type 正常
input_ego_speed 正常
features shape 正常
```

同时确认：

```text
loss 正常下降
无 NaN / Inf
无 KeyError
```

---

# 12. Checkpoint 检查

训练完成后必须从 checkpoint cfg 核对：

```text
input_representation
remove_stop_sign_token
input_ego_speed
split
epoch
```

不要只看 YAML 文件名。

建议 checkpoint 名称明确区分：

```text
exact_nostop_5ep.ckpt
relation_v0_nostop_5ep.ckpt
```

---

# 13. 第一阶段闭环评测

固定：

```text
TM seed = 100
```

优先只跑：

```text
route25
route28
route29
```

原因：

```text
route25：已确认 stop-sign deadlock 强干扰
route28：Relation-v0 原先明显 blocked
route29：Exact / Relation 原先行为接近，可作 non-regression 参考
```

每个 checkpoint 均使用完全相同的 routes 和 seed。

---

# 14. 必须记录的指标

每个 route 至少记录：

```text
status
route completion %
blocked
collision vehicle
collision pedestrian
collision static
运行时长
最大速度
mean_speed_raw
pred_wps
```

另外记录：

```text
num_type4_tokens
```

用于确认：

```text
Exact-NoStop = 0
Relation-NoStop = 0
```

---

# 15. 停车违规如何处理

因为本实验主动删除了停车牌规则输入：

```text
stop-sign violation
```

仍然记录，但**不作为本轮 Relation 表示有效性的主要判据**。

原因：

> 本轮主动剥离了对应规则信息，目的不是考察停车牌守规能力。

但是：

```text
vehicle collision
pedestrian collision
static collision
```

仍然属于关键安全指标，不能忽略。

---

# 16. 第一阶段最核心比较

对每条 route 直接比较：

```text
Exact-NoStop
vs
Relation-NoStop
```

重点看四件事：

### ① Progress

```text
是否完成
route completion %
是否 blocked
```

### ② Safety

```text
collision 是否明显恶化
```

### ③ Planner Behavior

```text
mean_speed_raw
pred_wps 是否持续收缩
是否出现异常 stop/go oscillation
```

### ④ Behavior Equivalence

特别看 route29：

```text
Relation-NoStop 是否仍能保持与 Exact-NoStop 接近的闭环行为
```

---

# 17. Gate 4.6 结果解释

## 情况 A：Relation-NoStop 明显弱于 Exact-NoStop

例如持续出现：

```text
Exact-NoStop 能完成
Relation-NoStop 明显 blocked

或

Relation-NoStop collision 明显更多
```

则当前结论：

> **Relation-v0 尚不足以保留基本 decision-relevant information。**

此时不要继续增加大量规则 feature。

优先重新检查：

```text
Relation-v0 本身的信息充分性
5 epoch training sufficiency
relation normalization
token distribution
```

---

## 情况 B：Exact-NoStop 与 Relation-NoStop 基本接近

例如：

```text
completion / progress 接近
blocked 无系统差异
collision 无明显恶化
route29 行为仍接近
```

则得到重要的 early viability 信号：

> **Relation-v0 在移除 stop-sign 工程干扰后，能够保留相当程度的基本驾驶决策信息。**

这支持继续研究：

```text
Driving Relational Bottleneck
```

而不是继续往 Relation-v0 中逐条加入交通规则。

---

## 情况 C：Relation-NoStop ID 略差，但 OOD 相对更稳

如果后续出现：

```text
ID：Relation 略有损失
OOD：Relation degradation 更小
```

这是最值得继续验证的结果之一。

它直接对应当前核心假设：

> **减少 scene-specific exact information，是否能够换取更稳定的跨场景经验复用。**

---

# 18. 单 seed 不能形成最终结论

TM seed=100 只用于：

```text
快速 viability 判断
```

如果 Exact-NoStop / Relation-NoStop 在第一阶段表现接近或出现正面信号，则继续：

```text
TM seed =
100
101
102
103
104
```

对相同 routes 重跑。

再比较：

```text
P(completion)
P(blocked)
collision
平均 route progress
方差
```

只有多 seed 后才讨论稳定差异。

---

# 19. 本实验暂时禁止事项

Gate 4.6 完成前不要加入：

```text
R_rule
stop_completed
permission
Path Relevance
动态安全包络
SURE-Plan
uncertainty
Action Effect
30 epoch
新 planner
RL
LLM / VLM
```

同时不要正式修改：

```text
cleared_stop_sign
```

避免再次混入新的变量。

---

# 20. 当前执行顺序

```text
Step 1
加入统一 remove_stop_sign_token 开关
        ↓
Step 2
Dataset / PlanT_agent 共用同一过滤逻辑
        ↓
Step 3
确认训练和在线 num_type4_tokens=0
        ↓
Step 4
训练 Exact-NoStop 5 epoch
        ↓
Step 5
训练 Relation-NoStop 5 epoch
        ↓
Step 6
核对 checkpoint cfg
        ↓
Step 7
TM seed=100
        ↓
Step 8
跑 route25 / route28 / route29
        ↓
Step 9
比较 Exact-NoStop vs Relation-NoStop
        ↓
Step 10
判断 A / B / C
        ↓
Step 11
若存在正面 viability 信号
→ 再做 TM seed 100~104
```

---

# 21. Gate 4.6 最终只回答一句话

> **在公平移除 stop-sign 规则输入后，Relation-v0 是否仍能以明显少于 Exact scene-specific state 的表示，支撑与 Exact 接近的基本闭环驾驶能力？**

这一结果决定下一步是：

```text
继续研究低维 Driving Relation
```

还是：

```text
重新审视 Relation-v0 是否丢失了过多 decision-relevant information
```

不要在本轮根据单个失败场景继续增加新的规则关系。
