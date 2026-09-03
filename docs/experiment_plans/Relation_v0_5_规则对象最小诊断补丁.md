# Relation-v0.5：规则对象 Exact 保留的最小可验证补丁

> 适用对象：当前 `CARLA + PlanT 2.0 + Relation-v0` 快速验证工程  
> 目的：验证当前观察到的“**自车作为路口第一辆车时容易 blocked；有前车时通常能继续行驶**”是否主要来自 **traffic light / stop sign 被 Relation-v0 当作普通几何安全对象进行了错误关系化**。  
> 定位：这是一个 **诊断补丁（diagnostic patch）**，不是论文最终 Relation 定义，也不是新的核心创新。

---

# 1. 当前要验证的唯一假设

当前 Relation-v0 将所有 PlanT object token：

```text
[type, x, y, yaw, speed, width, length]
```

统一转换成：

```text
[type,
 current_clearance,
 predicted_min_clearance,
 closing_rate,
 time_to_closest_approach,
 cos(bearing),
 sin(bearing)]
```

但 PlanT 的 object type 中不仅有车辆/行人，也包括：

```text
type=4  stop_sign
type=5  traffic_light
```

而 `closing_rate / predicted_min_clearance / TCPA` 本质上是为 **Ego 与具有物理占用/运动关系的对象** 设计的。

对于交通灯和停止标志，真正重要的语义不是：

```text
“我和这个 object 的几何余量是多少？”
```

而更接近：

```text
“当前规则是否允许我继续？”
“这个规则约束与我的行驶路径是否相关？”
“我距离受控停止位置还有多远？”
```

因此先验证下面这个非常具体的假设：

> **H-rule：当前 Relation-v0 在路口第一车位置频繁 blocked，主要原因之一，是把交通灯/停止标志也转换成了 Ego-Agent 几何关系，导致模型丢失了原 PlanT 中用于自主判断路口通行条件的规则空间信息。**

---

# 2. 为什么这个补丁足够“最小”

本补丁只改变一件事：

```text
car / walker / emergency / static / static_car
        ↓
仍然使用 Relation-v0

traffic_light / stop_sign
        ↓
保留原始 Exact token
```

即：

```text
Relation-v0:
所有 object → relationize

Relation-v0.5:
动态/物理交互对象 → relationize
规则对象(type 4/5) → exact
```

其余全部保持不变：

- 同一 PlanT 2.0 backbone；
- 同一道路 BEV；
- 同一 route 输入；
- 同一 ego speed；
- 同一 planning head；
- 同一 controller；
- 同一训练数据；
- 同一 held-out Town；
- 同一 seed；
- 同一训练 epoch；
- 同一 augmentation 设置；
- 同一 loss。

因此 Relation-v0 与 Relation-v0.5 的主要差异只有：

> **规则对象是否被关系化。**

如果 Relation-v0.5 明显缓解“路口第一车停住不走”，就能定位当前 Relation-v0 的一个结构性缺项。

---

# 3. 当前 PlanT 2.0 中需要依赖的类型编号

当前固定版本中 object type 为：

```text
0 : padding
1 : car / static_car
2 : walker
3 : static
4 : stop_sign
5 : traffic_light
6 : emergency vehicle
```

本补丁只特殊处理：

```python
RULE_OBJECT_TYPES = {4, 5}
```

不要修改其他类型。

---

# 4. 补丁一：修改 `PlanT/relation_features.py`

在文件中保留你当前已有的：

```python
relationize_exact_row(...)
```

不要改其内部计算。

在文件末尾新增：

```python
RULE_OBJECT_TYPES = {4, 5}  # 4=stop_sign, 5=traffic_light


def relationize_row_by_mode(
    row,
    ego_speed_mps,
    ego_extent,
    mode="relation",
    horizon=HORIZON,
):
    """
    mode:
        exact
            所有对象保持原始 PlanT exact token。

        relation
            当前 Relation-v0：所有对象都转换为关系 token。

        relation_rule_exact
            Relation-v0.5：
            stop_sign / traffic_light 保留 exact；
            其他对象继续使用 Relation-v0。
    """
    if mode == "exact":
        return list(row)

    if mode == "relation_rule_exact":
        type_id = int(round(float(row[0])))

        if type_id in RULE_OBJECT_TYPES:
            # 训练 row 可能有 8 列（最后一列 id），
            # 在线 row 为 7 列；均原样保留。
            return list(row)

        return relationize_exact_row(
            row,
            ego_speed_mps=ego_speed_mps,
            ego_extent=ego_extent,
            horizon=horizon,
        )

    if mode == "relation":
        return relationize_exact_row(
            row,
            ego_speed_mps=ego_speed_mps,
            ego_extent=ego_extent,
            horizon=horizon,
        )

    raise ValueError(f"Unknown input representation mode: {mode}")
```

## 4.1 为什么不直接修改 `relationize_exact_row()`

不要在原函数内部写：

```python
if type == traffic_light:
    ...
```

原因是我们必须保留当前 Relation-v0，便于复现实验。

最终应有三个可明确切换的模式：

```text
exact
relation
relation_rule_exact
```

---

# 5. 补丁二：修改训练路径 `PlanT/dataset.py`

原方案中已经有：

```python
from relation_features import relationize_exact_row
```

改为：

```python
from relation_features import relationize_row_by_mode
```

找到当前 Relation-v0 的代码，原来类似：

```python
if self.cfg_train.get("input_representation", "exact") == "relation":
    ego_obj = labels_data_all[0]

    if "extent" not in ego_obj:
        raise RuntimeError("Ego object has no extent; cannot build relation features.")

    input_objects = [
        relationize_exact_row(
            row,
            ego_speed_mps=sample["ego_speed"],
            ego_extent=ego_obj["extent"],
        )
        for row in input_objects
    ]
```

替换为：

```python
representation = self.cfg_train.get("input_representation", "exact")

if representation in ("relation", "relation_rule_exact"):
    ego_obj = labels_data_all[0]

    if "extent" not in ego_obj:
        raise RuntimeError(
            "Ego object has no extent; cannot build relation features."
        )

    input_objects = [
        relationize_row_by_mode(
            row,
            ego_speed_mps=sample["ego_speed"],
            ego_extent=ego_obj["extent"],
            mode=representation,
        )
        for row in input_objects
    ]
```

## 5.1 插入位置不要改变

仍然保持当前方案原则：

```text
PlanT 原始 object 构造
        ↓
forecasting target matching
        ↓
最后一步只改变 planner input
        ↓
remove id
        ↓
sample["input"]
```

不要提前 relationize，否则会污染官方 forecasting target matching。

---

# 6. 补丁三：修改在线推理 `PlanT/PlanT_agent.py`

原 import：

```python
from relation_features import relationize_exact_row
```

改为：

```python
from relation_features import relationize_row_by_mode
```

找到当前在线 Relation-v0 变换：

```python
if self.input_representation == "relation":
    ...
```

替换为：

```python
if self.input_representation in ("relation", "relation_rule_exact"):
    if len(label_raw) == 0:
        raise RuntimeError("No CARLA bounding-box data available.")

    ego_obj = label_raw[0]

    if "extent" not in ego_obj:
        raise RuntimeError("Ego bounding box has no extent.")

    data_car = [
        relationize_row_by_mode(
            row,
            ego_speed_mps=input_data["speed"],
            ego_extent=ego_obj["extent"],
            mode=self.input_representation,
        )
        for row in data_car
    ]

features = data_car
```

注意：

```text
训练和在线必须使用同一个 relation_features.py
```

不要只改 Dataset 不改 Agent。

---

# 7. `PlanT/model.py` 不需要修改

不要增加新的 embedding，不要改 Transformer。

原因：

三种模式最终仍然保持：

```text
[type + 6 continuous values]
```

并且 PlanT 本身针对不同 object type 使用不同的线性 embedding。

因此：

```text
type 1/2/3/6
```

对应 embedding 学到 Relation 语义；

```text
type 4/5
```

对应 embedding 学到 Exact 语义。

这正适合当前“最小诊断”目的。

---

# 8. 配置不增加新字段

仍然使用：

```yaml
training:
  input_representation: exact
```

只是在训练 Relation-v0.5 时通过命令行改成：

```text
model.training.input_representation=relation_rule_exact
```

因此三个实验分别是：

```text
Exact：
input_representation=exact

Relation-v0：
input_representation=relation

Relation-v0.5：
input_representation=relation_rule_exact
```

---

# 9. 必须先做单元测试

编辑：

```text
tests/test_relation_features.py
```

在原测试基础上追加：

```python
from relation_features import relationize_row_by_mode


ego_extent = [2.2, 0.9, 0.7]

# --------------------------------------------------
# 1. 普通 car 在 relation_rule_exact 下必须被关系化
# --------------------------------------------------
car = [1, 20.0, 0.0, 0.0, 0.0, 1.8, 4.4]

car_out = relationize_row_by_mode(
    car,
    ego_speed_mps=10.0,
    ego_extent=ego_extent,
    mode="relation_rule_exact",
)

assert car_out != car, (car, car_out)
assert car_out[0] == car[0]


# --------------------------------------------------
# 2. stop_sign 必须完全保持 Exact
# --------------------------------------------------
stop_sign = [4, 12.0, 1.0, 90.0, 0.0, 0.5, 0.5]

stop_out = relationize_row_by_mode(
    stop_sign,
    ego_speed_mps=10.0,
    ego_extent=ego_extent,
    mode="relation_rule_exact",
)

assert stop_out == stop_sign, (stop_sign, stop_out)


# --------------------------------------------------
# 3. traffic_light 必须完全保持 Exact
# --------------------------------------------------
traffic_light = [5, 15.0, -1.5, 0.0, 0.0, 0.5, 0.5]

tl_out = relationize_row_by_mode(
    traffic_light,
    ego_speed_mps=10.0,
    ego_extent=ego_extent,
    mode="relation_rule_exact",
)

assert tl_out == traffic_light, (traffic_light, tl_out)


# --------------------------------------------------
# 4. 训练数据的 8 列 row 也必须保留最后 object id
# --------------------------------------------------
traffic_light_train = [5, 15.0, -1.5, 0.0, 0.0, 0.5, 0.5, -1]

tl_train_out = relationize_row_by_mode(
    traffic_light_train,
    ego_speed_mps=10.0,
    ego_extent=ego_extent,
    mode="relation_rule_exact",
)

assert tl_train_out == traffic_light_train
assert len(tl_train_out) == 8

print("Relation-v0.5 rule-exact tests passed.")
```

运行：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

python tests/test_relation_features.py
```

必须出现：

```text
Relation-v0.5 rule-exact tests passed.
```

否则不要训练。

---

# 10. 再做一个 1 epoch smoke test

仍然使用与当前 Exact / Relation 完全相同配置。

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

export DS="$WORK_DIR/data/PlanT2_DS"
export SEED=1
export WANDB_MODE=offline
export CHECKPOINT_ADDON=relation_rule_exact_smoke

python PlanT/lit_train.py \
  user=local \
  gpus=1 \
  use_caching=false \
  model.training.input_ego_speed=true \
  overfit=5 \
  model.training.max_epochs=1 \
  model.training.batch_size=8 \
  model.training.num_workers=2 \
  model.training.augment=false \
  model.training.augment_parked=false \
  model.training.input_representation=relation_rule_exact \
  model.pre_training.forecastLoss_weight=0 \
  expname=relation_rule_exact_smoke
```

通过标准：

- dataloader 正常；
- forward 正常；
- loss 正常；
- checkpoint 正常；
- 无 NaN / inf。

---

# 11. 正式 Pilot：只训练一个 Relation-v0.5

**不要重新设计 split。**

直接沿用你刚刚 Gate 4 使用的：

```text
同一训练集
同一 HOLDOUT_TOWN
同一 seed
同一 5 epoch
```

当前截图为 Town05 OOD，则继续使用同一个 Town05 split。

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

export DS="$WORK_DIR/data/PlanT2_DS"
export HOLDOUT_TOWN=Town05
export SEED=1
export WANDB_MODE=offline
export CHECKPOINT_ADDON=relation_rule_exact_holdout

python PlanT/lit_train.py \
  user=local \
  gpus=1 \
  use_caching=false \
  model.training.input_ego_speed=true \
  model.training.max_epochs=5 \
  model.training.batch_size=128 \
  model.training.num_workers=4 \
  model.training.augment=false \
  model.training.augment_parked=false \
  model.training.input_representation=relation_rule_exact \
  "model.training.exclude_towns=[$HOLDOUT_TOWN]" \
  model.pre_training.forecastLoss_weight=0 \
  expname=relation_rule_exact_holdout
```

训练结束后立即复制：

```bash
cp PlanT/checkpoints/last_1.ckpt \
   PlanT/checkpoints/relation_rule_exact_holdout_last_1.ckpt
```

设置：

```bash
export REL_RULE_CKPT="$WORK_DIR/PlanT/checkpoints/relation_rule_exact_holdout_last_1.ckpt"
```

---

# 12. 必须检查 checkpoint 配置

```bash
python - "$REL_RULE_CKPT" <<'PY'
import sys
import torch

p = sys.argv[1]
ckpt = torch.load(p, map_location="cpu", weights_only=False)
cfg = ckpt["hyper_parameters"]["cfg"]
tr = cfg["model"]["training"]

print("checkpoint:", p)
print("input_representation =", tr.get("input_representation"))
print("input_ego_speed      =", tr.get("input_ego_speed"))
PY
```

必须看到：

```text
input_representation = relation_rule_exact
input_ego_speed      = True
```

否则不要进入闭环。

---

# 13. 闭环评测：第一轮只跑最有诊断价值的 3 条路线

不要马上把全部 benchmark 重新跑一遍。

优先使用刚才已经观察到明显差异的：

```text
route25
route28
route29
```

原因：

```text
route25：
Relation-v0 = 9.65% blocked
→ 明显失败样本

route28：
Relation-v0 = 39.31% blocked, 0 collision
Exact       = 100% completion，但有碰撞/停车违规
→ 最典型 Safety–Progress trade-off

route29：
Exact / Relation-v0 均 100% completion，行为几乎完全相同
→ 非回归控制样本
```

如果你当前 Gate 4 的 route XML 是逐 route 文件：

```bash
export PLANT_CHECKPOINT="$REL_RULE_CKPT"

# 将下面路径替换为你刚才实际使用的同一批 Gate 4 XML
python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes="$ROUTE_25_XML" \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/rule_exact_route25.json \
  --timeout=300

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes="$ROUTE_28_XML" \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/rule_exact_route28.json \
  --timeout=300

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes="$ROUTE_29_XML" \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/rule_exact_route29.json \
  --timeout=300
```

如果你使用的是一个 XML 内含多个 route，则保持**与刚才 Gate 4 完全相同的评测方式**，不要为了本补丁重新组织路线。

---

# 14. 这轮必须记录什么

建立下面的对照表：

| route | Exact | Relation-v0 | Relation-v0.5 Rule-Exact |
|---|---|---|---|
| 25 | 45.29% blocked, 0碰撞 | 9.65% blocked, 0碰撞 | 待测 |
| 28 | 100%完成；1碰撞+2停车违规 | 39.31% blocked, 0碰撞 | 待测 |
| 29 | 100%完成，0.6碰撞 | 100%完成，0.6碰撞 | 待测 |

同时记录：

```text
route_completion
driving_score
collision_vehicle
collision_pedestrian
collision_static
red_light
stop_sign
blocked
```

另外增加一列人工观察：

```text
是否出现：
“自车作为路口第一辆车，在允许通行后仍持续不走”
```

记录成：

```text
first_at_intersection_blocked = yes / no
```

---

# 15. 如何解释结果

## 结果 A：25 / 28 的 blocked 明显缓解，29 保持正常

例如出现：

```text
Relation-v0：
route25 / 28 经常路口第一车停住

Relation-v0.5：
能明显恢复自主通过路口
并且 route29 仍能正常完成
```

这是当前最希望看到的结果。

支持：

> **当前 Relation-v0 的主要缺陷之一不是“关系抽象本身不能开车”，而是把 rule object 错误压缩成了 Ego-Agent 几何关系。不同驾驶实体需要不同类型的关系表示。**

下一步应当正式引入：

```text
R_interaction
    Ego ↔ vehicle / pedestrian / obstacle

R_rule
    Ego ↔ traffic light / stop sign / right-of-way constraint
```

但最终论文不能长期保留 rule object 的 Exact token。

Relation-v0.5 只是告诉我们：

> **Rule Relation 是必须存在的一类关系。**

之后再设计低维：

```text
permission / constraint state
distance to controlled boundary
route/path relevance
```

等正式规则关系。

---

## 结果 B：25 / 28 基本没有改善

例如：

```text
Relation-v0 ≈ Relation-v0.5
仍然路口第一车 blocked
```

则 H-rule 不得到支持。

此时不要继续在红绿灯关系上投入。

下一优先检查：

```text
Path / Interaction Relevance
```

即：

> 当前 Relation-v0 只知道“对象离我近、正在接近”，但不知道“这个对象是否真的会进入我的未来运动通道”。

下一版应优先验证：

```text
对象未来占用 × Ego route corridor
```

而不是继续增加规则变量。

---

## 结果 C：blocked 减少，但碰撞明显增加

这不能判定补丁成功。

说明原 Relation-v0 的保守性被解除，但：

```text
Safety ↓
Progress ↑
```

仍然没有解决：

```text
Safety + Progress
```

此时需要进一步检查：

- 规则 token 恢复后是否让模型过度恢复 Exact 行为；
- 周车 interaction relation 是否仍然不足；
- 5 epoch 是否尚未收敛。

---

## 结果 D：route29 明显退化

如果原本两者都能 100% completion 的 route29 在 v0.5 中明显失败：

```text
说明混合表示本身可能引入训练困难或实现问题。
```

优先排查工程，不要把 25/28 的任何改善直接解释成研究结论。

---

# 16. 这轮实验能证明什么、不能证明什么

## 可以回答

### Q1

```text
traffic light / stop sign 被统一关系化
是否是当前路口第一车 blocked 的主要原因之一？
```

### Q2

```text
Driving Relation 是否需要按照“交互关系 / 规则关系”分类型表达？
```

### Q3

```text
当前 Relation-v0 的失败，是“关系思想完全错误”，
还是“关系集合不完整 / 关系类型设计不合理”？
```

---

## 不能回答

这轮不能证明：

```text
1. 低维关系一定提高 OOD 泛化；
2. 当前 relation 已经是最终最小充分表示；
3. 动态安全包络已经定义正确；
4. 端到端长尾失败是因为精确状态；
5. traffic light / stop sign 最终应该保留 Exact。
```

尤其第 5 点：

> 如果 Relation-v0.5 成功，**最终正确结论不是“规则对象不要关系化”**，而是“规则对象需要一种不同于几何安全余量的 Rule Relation”。

---

# 17. 这轮结束后的决策树

```text
                         Relation-v0.5
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
路口第一车 blocked 明显缓解                  基本不改善
          │                                       │
          ↓                                       ↓
确认 Relation-v0 缺 Rule Relation          Rule Relation 不是首要矛盾
          │                                       │
          ↓                                       ↓
设计正式低维 R_rule                    下一步验证 Path Relevance
          │
          ↓
重新验证 Safety + Progress
          │
          ↓
再进入参数 OOD / Scenario Holdout
```

---

# 18. 当前阶段不要做的事情

本补丁验证结束以前，不建议同时加入：

```text
SURE-Plan uncertainty
动态安全包络
reachable set
概率占用
Action Effect
新的 planner
新的 loss
新的 RL
```

否则如果 blocked 改善，将无法判断到底是哪项设计起作用。

当前最重要的是：

> **一次只验证一个“驾驶关系到底缺了什么”的假设。**

---

# 19. 最终执行 Checklist

## 代码

- [ ] `relation_features.py` 新增 `relationize_row_by_mode`
- [ ] type 4/5 在 `relation_rule_exact` 下原样保留
- [ ] Dataset 改为支持 `relation_rule_exact`
- [ ] Agent 改为支持 `relation_rule_exact`
- [ ] 不修改 `model.py`

## 验证

- [ ] 单元测试通过
- [ ] 1 epoch smoke 通过
- [ ] checkpoint 配置确认为 `relation_rule_exact`
- [ ] 使用同一个 Town05 holdout
- [ ] 使用同一个 seed=1
- [ ] 使用同一个 5 epoch pilot
- [ ] 不改变其他训练配置

## 闭环

- [ ] route25
- [ ] route28
- [ ] route29
- [ ] 记录 Safety + Progress
- [ ] 人工记录 `first_at_intersection_blocked`

---

# 20. 这一补丁的核心价值

这一轮不是为了“提高分数”。

它要回答的是一个比单个分数更重要的问题：

> **当前低维关系表示为什么在有前车时能够工作，而在需要自车独立判断路口通行条件时容易失败？**

如果仅恢复规则对象的原始表示就能显著解除这种失败，那么下一阶段就有了明确方向：

```text
Driving-Relevant Relation
≠ 单一几何安全关系

至少需要区分：

1. 交通参与者交互关系
2. 交通规则关系
```

这将使后续“真正决定驾驶行为的低维可复用关系结构”从概念讨论，继续收敛成可以由闭环实验逐项验证的关系体系。
