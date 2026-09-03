# Gate 4.5C：Stop-Sign Token Deadlock 因果闭环执行方案（修正版）

> 目标：在**不训练新模型、不改网络结构、不改 Relation-v0、不启用 Path mask**的前提下，验证：
>
> **持续存在的 `type=4` 停车牌 token 是否与 PlanT 当前 `cleared_stop_sign` 清除条件共同形成死锁，并直接导致 route25 的 blocked。**

---

# 1. 当前新发现

代码检查发现：

```text
cleared_stop_sign 的自然清除条件要求：

distance_to_stop_sign < 3 m
```

其中：

```text
distance_to_stop_sign
```

基于停车牌 `trigger_volume` 计算。

但当前卡点中：

```text
type=4 stop-sign token 持续存在
→ planner 不愿继续向前
→ Ego 无法进入 <3 m 清除范围
→ cleared_stop_sign 永远不触发
→ type=4 token 永远不消失
→ planner 继续受到停车牌约束
```

因此当前可能存在：

```text
persistent stop token
        ↓
planner 无法继续前进
        ↓
无法满足 natural clear condition
        ↓
token 无法消失
        ↓
继续停车
```

即：

> **Stop-Sign Token Deadlock**

---

# 2. 对上一版 Gate 4.5C 的修正

上一版使用：

```text
next_stop_dist <= 0.5 m
AND
ego_speed < 0.1 m/s
AND
持续 >= 1 s
```

来定义：

```text
stop_satisfied
```

该方案现在停止使用。

原因：

> 当前怀疑的死锁本身就是 Ego 无法自然进入停车牌清除距离，因此继续要求更严格的 `<=0.5 m` 会复制原死锁，使干预无法触发。

本阶段不再模拟：

```text
“停车义务已经合法完成”
```

而只做：

> **检测 planner 已进入停车牌死锁后，外部强制移除 type=4 token，观察死锁是否立即解除。**

---

# 3. 当前唯一待验证假设

定义：

> **H3：持续存在的 `type=4` 停车牌 token 是 route25 当前 blocked 的直接必要因素之一；它与 `cleared_stop_sign` 的自然清除条件共同形成闭环死锁。**

本阶段只验证这个机制。

不回答：

```text
Relation 最终是否需要 R_rule
停车牌规则最终如何编码
Path Relevance 是否仍有长期价值
stop sign 原始工程逻辑如何正式修复
```

---

# 4. 固定实验条件

正式实验只比较：

```text
Run C0：force_drop_type4 = OFF
Run C1：force_drop_type4 = ON
```

固定：

```text
route = route25
TM seed = 100
checkpoint = 当前 Relation-v0 5 epoch checkpoint
controller = 不变
Relation-v0 = 不变
Path mask = OFF
模型参数 = 不变
训练 = 不进行
```

C0 / C1 必须使用：

```text
同一版 Gate 4.5C 代码
```

唯一差异：

```text
force_drop_type4
```

---

# 5. Deadlock 判定

本阶段不要人为猜新的停车距离阈值。

只检测：

> **车辆已在停车牌影响区长期近乎静止，同时停车牌 token 仍持续存在，而且自然清除距离没有继续明显缩小。**

推荐固定条件：

```text
type4_count > 0

ego_speed < 0.1 m/s
持续 >= 2.0 s

distance_to_stop_sign >= 3.0 m

过去 2.0 s 内：
|distance_now - distance_2s_ago| < 0.2 m
```

即：

```python
deadlock_detected = (
    type4_count > 0
    and low_speed_duration >= 2.0
    and distance_to_stop_sign >= 3.0
    and abs(distance_now - distance_2s_ago) < 0.2
)
```

本轮固定参数：

```text
speed_threshold = 0.1 m/s
deadlock_duration = 2.0 s
clear_distance = 3.0 m
distance_change_threshold = 0.2 m
```

不做参数扫描。

---

# 6. 为什么必须要求“距离基本不再下降”

不能仅使用：

```text
ego_speed < 0.1
AND
type4_count > 0
```

因为车辆可能只是：

```text
正常减速
正常等待
正常停车
```

只有当：

```text
车辆近乎静止
+
停车牌 token 持续存在
+
距离长期不再向清除阈值靠近
```

时，才更符合：

```text
deadlock
```

而不是正常 stop behavior。

---

# 7. Run C1 的唯一干预

当：

```text
deadlock_detected == True
```

时：

```text
仅从 online planner input 删除 type=4 token
```

不要修改：

```text
cleared_stop_sign
stop sign GT
route planner
controller
Relation-v0
其他 object token
其他 rule token
```

即：

```python
if force_drop_type4 and deadlock_detected:
    planner_input = [
        token for token in planner_input
        if token.type != 4
    ]
```

---

# 8. 不要修改原始 cleared_stop_sign

本阶段非常重要：

> **不要直接修 `cleared_stop_sign` 代码。**

原因：

Gate 4.5C 当前是：

```text
因果诊断实验
```

不是：

```text
正式工程修复
```

如果同时：

```text
修改 clear condition
+
删除 type=4
```

就无法判断到底是哪一个改变使 planner 恢复。

因此本阶段：

```text
原 cleared_stop_sign 逻辑保持完全不变
```

---

# 9. Token 删除后必须重新生成 Planner Features

正确顺序：

```python
planner_input = original_input

if force_drop_type4 and deadlock_detected:
    planner_input = remove_type4(planner_input)

features = build_features_from(planner_input)

pred = model(features, ...)
```

必须确认：

> PlanT forward 实际使用的是删除 type=4 后重新构造的 features。

禁止：

```text
先生成 features
→ 再删除 token
→ forward 仍使用旧 features
```

---

# 10. Deadlock 触发后的处理

一旦某一帧：

```text
deadlock_detected = True
```

建议本轮直接锁存：

```python
debug_force_clear = True
```

之后保持：

```text
当前 stop sign 的 type=4 token 持续从 planner input 中删除
```

直到：

```text
当前 stop sign 已明显通过
或
next_stop_sign id 发生变化
```

不要每帧反复：

```text
删除
→ 恢复
→ 删除
→ 恢复
```

否则容易人为制造新的 token oscillation。

---

# 11. 必须记录的日志

## 11.1 Stop-sign 状态

```text
frame
ego_speed
next_stop_id
distance_to_stop_sign
distance_to_stop_sign_2s_ago
distance_delta_2s
low_speed_duration
type4_count_before
type4_count_after
deadlock_detected
debug_force_clear
```

---

## 11.2 Planner 状态

```text
desired_speed_raw
mean_speed_raw
pred_wps
hazard_brake
throttle
brake
```

---

## 11.3 Progress

```text
route_progress
vehicle_location
blocked_value
```

---

# 12. 正式实验

## Run C0：Baseline

```text
route25
TM seed = 100
Relation-v0 5 epoch checkpoint
Path mask = OFF
force_drop_type4 = OFF
```

目的：

> 用 Gate 4.5C 新代码重新复现原 stop-sign blocked。

---

## Run C1：Deadlock Intervention

```text
route25
TM seed = 100
Relation-v0 5 epoch checkpoint
Path mask = OFF
force_drop_type4 = ON
```

当满足：

```text
type4_count > 0
ego_speed < 0.1 m/s 持续 >= 2.0 s
distance_to_stop_sign >= 3.0 m
过去 2.0 s 距离变化 < 0.2 m
```

则：

```text
deadlock_detected = True
debug_force_clear = True
```

之后：

```text
仅从 planner input 删除 type=4 token
```

---

# 13. C0 / C1 唯一差异检查

执行前确认：

```text
[ ] 同一代码版本
[ ] 同一 route25
[ ] TM seed=100
[ ] 同一 Relation-v0 checkpoint
[ ] Path mask=OFF
[ ] controller 相同
[ ] Relation-v0 相同
[ ] cleared_stop_sign 原代码完全不改
[ ] deadlock detector 两边都运行
[ ] C0 只是不删除 token
[ ] C1 deadlock 后删除 type=4
```

唯一实验变量：

```text
type=4 token 是否在 deadlock 后被强制移除
```

---

# 14. H3 因果成立标准

C1 中如果出现：

```text
1. deadlock_detected=True
2. type4_count_before > 0
3. type4_count_after = 0
4. mean_speed_raw 从 stop/go 振荡转为明显更稳定
5. pred_wps 开始持续向前展开
6. Ego 开始继续前进
7. distance_to_stop_sign 开始重新下降
8. 原 blocked 被解除或显著推迟
```

则可以形成：

```text
persistent type=4
        ↓
planner release 不足
        ↓
Ego 无法继续靠近 natural clear threshold
        ↓
cleared_stop_sign 无法触发
        ↓
type=4 持续存在
        ↓
deadlock
```

外部干预：

```text
force remove type=4
        ↓
planner 恢复前进
        ↓
deadlock 被打破
```

结论：

> **Stop-Sign Token Deadlock 是 route25 当前 blocked 的主要直接机制。**

---

# 15. H3 部分成立标准

如果删除 type=4 后：

```text
mean_speed_raw 明显改善
pred_wps 更向前
Ego progress 提升
distance_to_stop_sign 继续下降
```

但最终：

```text
仍未完整通过
```

则：

> **persistent type=4 是重要因素，但不是唯一因素。**

下一步继续检查：

```text
training sufficiency
其他 rule token
planner input distribution
stop-sign 状态编码
```

---

# 16. H3 不成立标准

如果已经确认：

```text
deadlock_detected=True
type4 实际删除成功
planner features 已重新生成
```

但：

```text
mean_speed_raw 基本不变
pred_wps 振荡基本不变
Ego 仍停在同一位置
route progress 基本不变
```

则：

> **persistent type=4 不是当前 blocked 的主要因果来源。**

此时停止 Rule Completion / token-clear 扩展。

---

# 17. 如果 H3 不成立，下一步

优先检查：

```text
training sufficiency
```

不要直接跳：

```text
30 epoch
```

建议：

```text
5 epoch
→ 10~15 epoch
```

重新训练：

```text
Exact
Relation-v0
```

再比较：

```text
route25
route28
route29
```

重点判断：

> “停车牌 / 路口第一车后无法稳定起步”是否主要来自当前 5 epoch 模型欠训练。

---

# 18. 当前研究解释边界

即使 Gate 4.5C 成功，也不能直接写成：

> “Relation 缺少 Rule Permission，所以 blocked。”

因为当前已知：

```text
Exact
和
Relation
```

共享同一个：

```text
cleared_stop_sign
```

机制。

更严谨的阶段性解释应为：

```text
共享 stop-sign 状态机存在潜在 deadlock
+
Relation-v0 更容易陷入并维持该 deadlock
+
Exact 某些情况下仍能通过 planner 输出继续向前并跨过清除阈值
```

Gate 4.5C 首先只确认：

> **blocked 的直接机制是不是 persistent type=4 deadlock。**

确认以后，下一步才研究：

> **为什么 Exact 更容易从该状态恢复，而 Relation-v0 不容易。**

---

# 19. 当前禁止事项

Gate 4.5C 完成前不要：

```text
正式修改 cleared_stop_sign
加入 R_rule
恢复 Exact traffic-light / stop-sign 几何 token
重新做 Path-Relevance Gating
动态安全包络
SURE-Plan
uncertainty
Action Effect
30 epoch
新 planner
RL
LLM / VLM
```

原则：

> **一次只验证一个假设。**

---

# 20. Gate 4.5C 最终只允许三种结论

### A. H3 成立

```text
persistent type=4
→ natural clear condition 无法满足
→ deadlock
```

强制删除后恢复。

### B. H3 部分成立

删除后 planner / progress 明显改善，但仍有其他因素。

### C. H3 不成立

删除后行为基本不变。

只有 A / B 才继续研究：

```text
Stop-Sign Completion / Permission
```

的正式表示方式。
