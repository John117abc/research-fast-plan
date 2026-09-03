# Gate 5：PlanT Baseline Qualification 详细可执行流程

> 目的：在正式开展 **Cross-Scenario Driving Equivalence** 实验前，确认当前 PlanT 基座本身可靠、配置清晰、关键逻辑没有被本地 patch 污染。
>
> 本 Gate 只做 **基座资格审查**，不训练 Relation、不做 OOD、不改新方法。
>
> 核心原则：
>
> 1. **先确认官方基座能正常工作；**
> 2. **再确认本地代码与官方差异；**
> 3. **任何关键基座问题未解决前，不进入后续 Driving Equivalence 实验。**

---

# 0. Gate 5 最终输出

完成后必须得到 4 份结果：

```text
A. PlanT 官方版本信息
B. 当前本地 patch 清单
C. 关键逻辑核对结果
D. PlanT-Reference 闭环 smoke 结果
```

最后只能给出：

```text
PASS
或
FAIL
```

只有：

```text
Gate 5 = PASS
```

才允许进入后续：

```text
Cross-Scenario Driving Equivalence Existence
```

---

# 1. Step 1：锁定官方 PlanT 2.0 Reference

## 1.1 记录官方代码信息

首先记录：

```text
repo:
commit hash:
branch/tag:
CARLA version:
Python version:
PyTorch version:
CUDA version:
```

如果你当前使用的是某个固定 commit，必须保存：

```bash
git rev-parse HEAD
git status
git log -1
```

输出保存到：

```text
gate5/official_version.txt
```

---

## 1.2 记录官方配置

至少保存：

```text
训练配置
评测配置
checkpoint 路径
model input representation
input_ego_speed
path / wps 输出形式
controller 相关配置
训练 split
训练 epoch
```

不要只截图 YAML。

建议直接复制实际运行使用的配置到：

```text
gate5/config/
```

---

## 1.3 检查官方 pretrained checkpoint

如果官方提供 pretrained checkpoint：

必须读取 checkpoint 内保存的 cfg / hparams。

至少核对：

```text
model.training.input_representation
model.training.input_ego_speed
training split
output type
checkpoint epoch
```

### 通过标准

```text
[ ] 官方 commit 已记录
[ ] 官方运行配置已保存
[ ] checkpoint 配置可读取
[ ] checkpoint 与代码结构兼容
```

### FAIL 条件

出现以下任意情况，先停止：

```text
checkpoint 无法加载
checkpoint cfg 与当前代码明显不兼容
官方 commit 无法确认
当前代码来源不明确
```

这类问题没解决前，不进入 Step 2。

---

# 2. Step 2：建立“本地代码 vs 官方代码”Patch 清单

这一阶段非常重要。

不要凭记忆判断修改过哪些地方。

## 2.1 生成 diff

如果当前代码基于官方 git：

```bash
git diff <official_commit> -- > gate5/local_vs_official.diff
```

如果当前有未提交修改：

```bash
git diff > gate5/uncommitted.diff
git status > gate5/git_status.txt
```

---

## 2.2 手工分类所有 patch

至少按以下类别整理：

| 类别 | 是否修改 | 文件 | 修改内容 | 是否影响正式 baseline |
|---|---|---|---|---|
| Relation-v0 |  |  |  |  |
| input_ego_speed |  |  |  |  |
| stop-sign |  |  |  |  |
| NoStop |  |  |  |  |
| debug log |  |  |  |  |
| Dataset |  |  |  |  |
| PlanT_agent |  |  |  |  |
| controller |  |  |  |  |
| checkpoint |  |  |  |  |
| route planner |  |  |  |  |
| 其他 |  |  |  |  |

---

## 2.3 将 patch 分成三类

### A. 允许保留

只影响日志、不改变模型行为：

```text
debug log
额外统计
结果保存
```

### B. 必须关闭

正式 baseline qualification 时必须关闭：

```text
Relation-v0
NoStop
Path mask
force drop type4
其他 intervention
```

### C. 必须单独确认

可能改变官方行为：

```text
input_ego_speed patch
stop-sign patch
Dataset key patch
controller patch
route planner patch
```

---

## 2.4 生成最终 patch 表

保存：

```text
gate5/patch_audit.md
```

### 通过标准

```text
[ ] 所有本地修改都有出处
[ ] Relation / NoStop / intervention 已关闭
[ ] debug-only patch 不影响 forward/control
[ ] 影响行为的 patch 已单独标记
```

### FAIL 条件

如果出现：

```text
不知道某段代码为什么被改过
无法确认是否影响 planner input
无法确认 Dataset 与 online agent 是否一致
```

先停止。

不要带着未知 patch 进入后续实验。

---

# 3. Step 3：关键逻辑逐项资格审查

本阶段只检查最可能污染后续研究结论的关键逻辑。

---

# 3.1 input_ego_speed

你之前已经发现：

```text
model.py 读取 batch["input_ego_speed"]
Dataset 原始逻辑只产生 batch["ego_speed"]
```

因此必须检查当前代码。

## 检查内容

### Dataset

确认：

```text
sample["input_ego_speed"]
```

是否真正生成。

### batch

在 dataloader 中打印一次：

```text
batch.keys()
batch["input_ego_speed"].shape
```

### online agent

确认在线推理使用的 ego speed 与训练定义一致。

### checkpoint

读取：

```text
input_ego_speed = True / False
```

必须与训练、推理一致。

---

## PASS 条件

```text
训练：
有明确 input_ego_speed 定义

在线：
有完全一致的输入

checkpoint：
配置与代码一致
```

## FAIL 条件

出现以下任意情况立即停止：

```text
训练 true、在线 false
训练 false、在线 true
checkpoint 配置与运行 YAML 不一致
input_ego_speed key 临时硬补但语义不一致
```

---

# 3.2 Stop-sign lifecycle

这是 Gate 5 最关键检查项之一。

## 必须画出当前真实状态机

根据代码，不根据文档，明确：

```text
什么时候生成 type=4
什么时候 type=4 进入 planner input
Ego 何时被判定“完成停车”
cleared_stop_sign 如何置位
type=4 何时消失
何时 reset
```

输出成：

```text
gate5/stop_sign_state_machine.md
```

---

## 必须做一个最小运行日志

在一个包含 stop sign 的 route 上记录：

```text
frame
ego_speed
next_stop_id
next_stop_dist
cleared_stop_sign
num_type4_tokens
throttle
brake
```

观察完整过程：

```text
接近停车牌
→ 减速
→ 停车
→ 完成
→ 再起步
→ type4 消失
```

---

## PASS 条件

至少满足：

```text
type4 不会永久存在
完成停车后能进入 clear 状态
车辆能够正常恢复前进
状态机不会形成永久 deadlock
```

## FAIL 条件

如果仍出现：

```text
车辆已停车
type4 持续存在
cleared_stop_sign 永远无法触发
同一位置长期 blocked
```

则：

# Gate 5 直接 FAIL

此时必须先修 baseline。

不要进入 Cross-Scenario Equivalence。

---

# 3.3 Planner input token 检查

至少统计：

```text
vehicle
walker
traffic light
stop sign
route
road / BEV
```

确认：

```text
token type 编号
feature 维度
Dataset 训练端
PlanT_agent 在线端
```

一致。

尤其检查：

```text
training representation
==
online representation
```

---

## PASS 条件

随机抽若干 frame：

```text
type 分布合理
feature shape 一致
没有训练端有、在线端没有的字段
没有在线端额外增加特征
```

---

# 3.4 Path / Waypoint output

记录：

```text
pred_path
pred_wps
desired_speed_raw
mean_speed_raw
```

确认：

```text
模型输出没有 shape / scale 异常
waypoint spacing 与车辆实际运动大致一致
```

本 Gate 不要求完美驾驶。

只要求输出逻辑正常。

---

# 3.5 Controller

确认：

```text
planner 输出正常时
controller 能够实际驱动车辆
```

至少记录：

```text
target speed
throttle
brake
steer
hazard_brake
```

排除：

```text
planner 正常
但 controller 把车踩死
```

---

# 4. Step 4：官方 / Reference Baseline Smoke Test

不要一开始跑完整 benchmark。

先做最小闭环资格验证。

---

## 4.1 推荐路线

优先选择：

```text
route29
```

作为正常参照。

然后增加：

```text
route25
route28
```

用于检查曾经出现问题的位置。

如果官方有更标准的 smoke route，可优先使用官方 route。

---

## 4.2 固定评测条件

建议：

```text
TM seed = 100
```

第一轮资格验证只固定一个 seed。

使用：

```text
PlanT-Reference checkpoint
Relation = OFF
NoStop = OFF
Path mask = OFF
force_drop_type4 = OFF
其他 intervention = OFF
```

---

## 4.3 每条 route 至少记录

```text
route completion
blocked
collision
red-light violation
stop-sign violation
运行时间
CARLA crash
```

同时保存：

```text
ego_speed
pred_wps
mean_speed_raw
type4 count
next light / stop
controller output
```

---

# 5. Step 5：Gate 5 资格判定

不要只看 Driving Score。

Gate 5 判断的是：

> **这个 PlanT 基座是否足够稳定、正确，可以作为后续研究工具。**

---

# 5.1 PASS

满足以下条件可以 PASS：

```text
1. 官方代码 / checkpoint 来源明确
2. 本地 patch 已完全审计
3. 训练 / 在线 input 一致
4. input_ego_speed 逻辑明确
5. stop-sign lifecycle 能正常闭环
6. token / route / BEV / path+wps 无明显错误
7. controller 能正确执行 planner 输出
8. 至少少量代表 route 可以正常闭环运行
9. 没有系统性 CARLA / pipeline 崩溃
```

此时冻结：

```text
PlanT-Reference
```

---

# 5.2 FAIL：必须立即停止后续研究

出现以下任意一项，建议立即停止 Driving Equivalence 实验：

## FAIL-A：输入不一致

```text
training representation != online representation
```

或：

```text
input_ego_speed train / inference 不一致
```

---

## FAIL-B：核心规则状态机死锁

例如：

```text
stop-sign lifecycle 仍存在稳定 deadlock
```

---

## FAIL-C：controller 污染 planner 判断

例如：

```text
planner 明显向前预测
但 controller 系统性不执行
```

---

## FAIL-D：官方 pretrained baseline 无法正常闭环

如果：

```text
官方 checkpoint
+
官方 / reference 配置
```

在多个基本 route 上持续：

```text
严重 blocked
明显异常输出
无法完成基础驾驶
```

则当前 PlanT 基座不适合继续承担后续研究。

---

## FAIL-E：高度不稳定

例如：

```text
同配置同 seed
重复运行差异极大
```

且不是 CARLA 明确随机因素导致。

这种情况下后续等价性分析很难可信。

---

# 6. 如果 Gate 5 FAIL，怎么处理

不要继续 Relation 研究。

按下面顺序处理：

```text
FAIL
↓
判断是代码问题还是模型本身问题
↓
代码问题
→ 修复并重新 Gate 5

模型本身问题
→ 检查官方 checkpoint / official setup
↓
如果官方 setup 仍明显不可用
→ 停止 PlanT 作为主基座
→ 重新选择 baseline
```

---

# 7. 如果 Gate 5 PASS，冻结 PlanT-Reference

冻结内容：

```text
commit hash
checkpoint
config
CARLA version
Python / PyTorch
controller
route planner
input representation
input_ego_speed
所有启用 / 禁用 patch
```

保存到：

```text
gate5/PlanT-Reference.md
```

后续任何实验都从该 reference 派生。

---

# 8. Gate 5 完成后需要反馈给我的结果

请至少提供以下内容：

## A. 版本信息

```text
commit
checkpoint
config
```

## B. patch audit

```text
当前本地有哪些修改
哪些关闭
哪些保留
```

## C. input_ego_speed

```text
官方值
当前值
训练端
在线端
```

## D. stop-sign lifecycle

```text
代码逻辑
一段实际运行日志
是否正常 clear
```

## E. smoke test

至少：

| Route | Completion | Blocked | Collision | Stop Violation | CARLA Crash |
|---|---:|---:|---:|---:|---|
| route25 |  |  |  |  |  |
| route28 |  |  |  |  |  |
| route29 |  |  |  |  |  |

---

# 9. 当前 Gate 5 不做的事情

禁止：

```text
重新训练 Relation
修改 Relation-v0
做 Scenario Holdout
做 Cross-Scenario Equivalence
加入新 relation feature
做 PCA / SVD
设计 Learned Relation
上 VAD / UniAD
```

当前只确认：

> **PlanT 是否是一个可靠的实验基座。**

---

# 10. 最终判定模板

完成后只写：

```text
Gate 5 Result:
PASS / FAIL

Critical Issues:
1.
2.
3.

Can PlanT be used as the reference platform?
YES / NO

Reason:
...
```

如果你反馈的结果中出现任何 **FAIL-A ～ FAIL-E** 类型的问题，应立即停止后续实验，先处理基座，不继续往下做。
