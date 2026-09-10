# Gate B0：面向驾驶决策的行为等价闭包验证方案

> **用途**：直接交给其他 AI / 工程代理执行。  
> **当前软件基础**：CARLA 0.9.16、现有 `gate_f0` 可行未来搜索引擎、20 Hz 全世界录制器、Lane-PID、自车纵向运动原语、3 s 五次多项式换道原语、GT occupancy、beam search、progress frontier、现有 F1/F2/F3 场景与 Dev-108 数据。  
> **本 Gate 不训练 PlanT，不训练新的神经网络，不比较 Relation 模型与 Exact 模型。**

---

# 0. 先冻结研究问题与创新边界

## 0.1 当前论文创新判断

当前方向**具有论文级创新潜力**，但创新点不能写成以下任意一种：

- “使用可达集/可行域做自动驾驶决策”；
- “用动作后果帮助规划”；
- “使用双模拟学习状态表示”；
- “不同场景之间迁移知识”；
- “动作条件未来预测提高泛化”。

这些方向已有明确相关工作。

当前更有希望形成核心创新的是：

> **面向驾驶决策的动作条件可行—补救行为等价状态抽象**：  
> 不根据场景类别、专家轨迹相似度或终端标签定义状态关系，而根据“相同候选动作对安全、可达、任务进展和后续补救能力产生的后果”判断两个物理状态是否在驾驶决策上等价；并进一步要求这种等价性在施加相同动作后仍能保持，即具有近似行为闭包性。

当前候选对象记为：

\[
R(X)
\]

它不是 `Optional / Necessary / Contingency` 标签，也不是单个 TTC、距离、进展量，而是由**动作条件可行后果**塑造的连续状态抽象。

## 0.2 与已有工作的边界

必须明确区分：

1. **可达集/驾驶走廊工作**已经会计算哪些走廊可行，并从中选优；本研究不是再发明一个走廊搜索器。
2. **Field of Safe Motion** 已把驾驶者是否保留无碰撞“出路”与可达性联系起来；本研究不是仅判断有没有安全 escape route。
3. **后继表示/场景迁移**已经研究跨场景复用状态转移知识；本研究不是只做“相似场景迁移”。
4. **双模拟表示学习**已经用“相同行为后果”定义状态相似；本研究需要给出驾驶任务中特有的、可操作的行为后果定义。
5. **2026 年动作条件世界模型**已经显式建模候选动作下的未来场景；本研究不是预测完整未来场景，而是研究**哪些未来能力在不同动作下被保留、削弱或消失，以及这种结构能否形成跨物理机制的决策等价状态**。
6. **2026 年安全因果表示工作**已经用状态/动作对长期 reward 与 safety cost 的影响 + 双模拟正则做 OOD 泛化；本研究要强调的是**偏好/奖励之前的可行性与补救能力结构**，而不是长期 reward/cost consequence。

因此当前论文主张暂定为：

> 高维物理场景中可能存在由候选动作的可行未来后果所定义的低复杂度行为等价结构。该结构若具有跨物理机制的一致性和动作闭包性，则可作为后续学习型驾驶模型的状态抽象基础。

**本 Gate 只验证“这种状态抽象是否真的具有行为闭包性”，暂不宣称已经提高端到端泛化。**

---

# 1. Gate B0 的唯一研究问题

验证：

\[
R(X_A)\approx R(X_B)
\]

是否不仅表示两个状态“当前看起来关系相似”，还意味着对相同动作 \(u\)：

\[
R(T(X_A,u))\approx R(T(X_B,u))
\]

其中：

- \(X_A,X_B\)：两个物理状态；
- \(u\)：相同自车动作原语；
- \(T(X,u)\)：施加动作后得到的后继状态；
- \(R(\cdot)\)：动作条件可行后果表示。

如果“不同物理机制但当前关系相似”的状态在施加相同动作后仍然保持相似，才有资格称为**近似行为等价**。

---

# 2. 为什么现在必须做这个 Gate

已有实验已经得到：

1. PlanT / Waymo 阶段说明：
   \[
   \text{轨迹相似}\neq\text{Driving Relation}
   \]
   因为大量相似性退化为低阶纵向动力学。

2. F1/F2 说明：不同物理场景可以出现相似的 feasible-future structure，同一物理机制也可以出现不同结构。

3. F3-A 说明：只用粗标签 `Optional / Necessary / Contingency` 学统一表示，在完全未见机制下失败。

4. F3-A3 说明：`block Necessary` 与 `stopped-lead Necessary` 虽然终端标签相同，但动作机会随时间演化明显不同，因此“终局可行性相同”不等于“驾驶关系相同”。

因此下一步不应该继续调网络，也不应该重新做 Relation vs Exact，而应先回答：

> **什么样的 Relation 真正满足动作后的行为一致性？**

---

# 3. 软件和数据：全部优先复用现有工程

## 3.1 必须复用

现有：

```text
gate_f0/
├── config/
├── scenarios/
├── recorder/world_recorder.py
├── ego/
├── feasible/
│   ├── corridor_builder.py
│   ├── longitudinal_primitives.py
│   ├── lane_change_primitive.py
│   ├── occupancy_gt.py
│   ├── collision_check.py
│   ├── beam_search.py
│   └── progress_frontier.py
├── results/
└── ...
```

以及：

- `gate_f0/road_segment.json`
- Town12 已冻结 208 m 双车道同向直道路段；
- 20 Hz world recorder 原始数据；
- 离线分析统一下采样到 `dt = 0.5 s`；
- `H = 10 s`；
- lane change duration = `3.0 s`；
- 现有纵向加速度原语：
  \[
  a\in\{-4,-2,0,+1.5\}\;m/s^2
  \]
- 真实 bbox + 既有 safety margin；
- 当前 `KEEP / CHANGING_LEFT / LEFT` 模式；
- 现有 F3 Dev-108：仅作为**开发/诊断集**。

## 3.2 本 Gate 禁止做的事

- 不重新训练 PlanT；
- 不训练 CNN/Transformer；
- 不使用旧 `Optional/Necessary/Contingency` 作为监督标签；
- 不为了让结果更好而修改现有场景参数；
- 不修改 F0/F1/F2 已冻结结果；
- 不根据 B0 结果事后改变本 Gate 的主指标；
- 不使用随机背景 TM 车辆；
- 不引入新的 TTC、距离阈值、规则分类器。

---

# 4. 新工程目录

新建：

```text
gate_b0/
├── config/
│   └── gate_b0.yaml
├── action_probe/
│   ├── action_set.py
│   ├── constrained_rollout.py
│   └── successor_state.py
├── consequence/
│   ├── action_consequence.py
│   ├── free_normalization.py
│   ├── relation_signature.py
│   └── relation_distance.py
├── closure/
│   ├── build_pairs.py
│   ├── one_step_closure.py
│   ├── two_step_closure.py
│   └── statistics.py
├── scripts/
│   ├── 00_freeze_env.sh
│   ├── 01_data_health.py
│   ├── 02_smoke_action_probe.py
│   ├── 03_build_signatures.py
│   ├── 04_build_pairs.py
│   ├── 05_run_one_step_closure.py
│   ├── 06_make_figures.py
│   ├── 07_run_two_step_closure.py
│   └── 08_confirmatory_generation.py
├── results/
│   ├── discovery/
│   └── confirmatory/
└── README_EXECUTION.md
```

原则：

> `gate_b0` 只调用 `gate_f0/feasible/` 的已有能力；除非发现明确 bug，否则不直接改原文件。需要的新功能优先通过 wrapper 实现。

---

# 5. 冻结动作集合：直接使用现有运动原语，不额外手写“驾驶语义动作”

为减少人工定义，动作探针直接来自当前离线搜索器的原始运动原语。

定义：

\[
u=(a_x,m)
\]

其中：

\[
a_x\in\{-4,-2,0,+1.5\}\;m/s^2
\]

横向模式：

\[
m\in\{\text{KEEP},\text{START\_LEFT}\}
\]

因此固定动作集合：

\[
|\mathcal U|=8
\]

具体为：

```text
U0 = KEEP       + ax=-4.0
U1 = KEEP       + ax=-2.0
U2 = KEEP       + ax= 0.0
U3 = KEEP       + ax=+1.5

U4 = START_LEFT + ax=-4.0
U5 = START_LEFT + ax=-2.0
U6 = START_LEFT + ax= 0.0
U7 = START_LEFT + ax=+1.5
```

当前冻结道路中 Ego 位于右侧行驶车道，左侧为唯一横向候选。

如果某状态左侧车道在拓扑上不存在，则 `START_LEFT` 使用 **topology mask**，不能把它当作“动作不可行”。

---

# 6. 动作探针持续时间

固定：

\[
\Delta T_u = 1.0s
\]

离线 `dt=0.5s`，因此每个 probe 强制执行 2 个离散步。

动作探针只负责：

> “如果 Ego 现在首先执行这个动作 1 秒，会把自己带到怎样的后继状态？”

1 秒后不再强制相同动作，后续交给已有 feasible engine 搜索。

对于 `START_LEFT`：

- 1 秒后 lane change 尚未完成；
- 后继状态必须为：
  ```text
  mode = CHANGING_LEFT
  lane_change_elapsed = 1.0
  ```
- 后续搜索必须继续完成剩余 2 秒五次多项式换道；
- 不允许把 1 秒后的 Ego 瞬间投影到 LEFT lane。

这一点是硬要求。

---

# 7. 定义动作条件可行后果

对于状态 \(X\) 和动作 \(u\)，先强制执行 \(u\) 1 秒，再允许现有 beam search 自由寻找剩余 9 秒内的最优可行 continuation。

定义：

\[
Q_X(u)=
\max_{\tau\in\mathcal F(X|u)}
[s_\tau(H)-s_0]
\]

其中：

- \(H=10s\)；
- \(\mathcal F(X|u)\)：前 1 秒必须执行动作 \(u\)，之后满足道路、碰撞、动力学、corridor 语义的所有 future；
- 如果前 1 秒动作本身已经碰撞或后续无任何可行 continuation：
  \[
  M_X(u)=0
  \]
- 否则：
  \[
  M_X(u)=1
  \]

## 7.1 Free baseline

为了排除“某动作本身减速/换道就天然少走”的影响，对每个状态、每个动作计算匹配 free baseline：

\[
Q_{\text{free}}(u)
\]

free baseline 条件：

- Ego 初始状态完全相同；
- road / route / lane geometry 完全相同；
- 动作 \(u\) 完全相同；
- 只移除该场景记录在 `target_actor_ids` 中的关键交互 actor；
- 不删除道路边界；
- 不改变 Ego 动力学；
- 不改变 lane-change duration。

归一化：

\[
V_X(u)=
\frac{Q_X(u)}{Q_{\text{free}}(u)}
\]

正常情况下：

\[
0\le V_X(u)\le1
\]

健康检查：

- 若 \(V>1.02\)，标记为异常并停止该样本进入正式统计；
- 若 `Q_free <= 0`，说明 free baseline 或动作实现有 bug；
- 正式距离计算前允许仅为浮点误差做：
  \[
  V\leftarrow\mathrm{clip}(V,0,1)
  \]
  但原始值必须保留。

---

# 8. 初始候选关系表示

不再使用三分类。

定义：

\[
R_0(X)=\{M_X(u),V_X(u)\}_{u\in\mathcal U}
\]

即 8 个动作 ×：

- feasibility mask；
- normalized future progress。

总共 16 个数。

它回答：

> 当前状态下，Ego 先做不同动作，会保留多少任务有效未来？

注意：

- `R0` 只是**候选最小表示**；
- 本 Gate 的目的之一就是验证它是否足以形成行为闭包；
- 如果失败，不允许立刻加 TTC / clearance / actor type 等规则特征；
- 应先分析“缺失的是哪一种动作后果”。

---

# 9. 关系距离

对动作 \(u\)，定义：

\[
\delta_u(X_i,X_j)=
\begin{cases}
0, & M_i=0,M_j=0\\
1, & M_i\ne M_j\\
|V_i-V_j|, & M_i=1,M_j=1
\end{cases}
\]

因此：

\[
0\le\delta_u\le1
\]

定义平均距离：

\[
d_{\text{mean}}(X_i,X_j)=
\frac1{|\mathcal U|}
\sum_{u\in\mathcal U}\delta_u
\]

以及严格距离：

\[
d_{\max}(X_i,X_j)=
\max_{u\in\mathcal U}\delta_u
\]

主分析同时保存两者，但：

- 排序主指标：`d_mean`
- 安全/最坏动作诊断：`d_max`

---

# 10. 后继状态构造

对状态 \(X\) 和动作 \(u\)：

\[
X'_u=T(X,u)
\]

后继时刻：

\[
t'=t_0+1.0s
\]

必须同步更新：

### Ego

- world pose；
- road-aligned \(s,d\)；
- speed；
- acceleration；
- yaw；
- lane mode；
- lane-change elapsed；
- bbox。

### 其他 actor

直接使用现有 20 Hz 录制中的：

\[
t_0+1.0s
\]

真实世界状态，并以该时刻重新建立离线局部坐标。

当前所有正式 critical actor 均为 scripted deterministic actor，因此：

> B0 discovery 阶段允许使用原始 GT future replay；不需要因 Ego probe 改变其他 actor 轨迹。

这是一项明确实验假设，必须记录在结果中：

> 当前 Gate 验证的是“在非响应式交通参与者条件下的行为闭包”。

后续真实交互/响应式 world model 属于下一阶段，不混入本 Gate。

---

# 11. 行为闭包检验

若两个状态初始：

\[
R_0(X_i)\approx R_0(X_j)
\]

则对所有双方都可施加的相同动作 \(u\)，计算：

\[
R_0(T(X_i,u)),\quad R_0(T(X_j,u))
\]

定义一阶后继平均距离：

\[
D_1^{mean}(i,j)=
\frac1{|\mathcal U_{ij}|}
\sum_{u\in\mathcal U_{ij}}
d_{\text{mean}}(T(X_i,u),T(X_j,u))
\]

以及最坏动作距离：

\[
D_1^{max}(i,j)=
\max_{u\in\mathcal U_{ij}}
d_{\text{mean}}(T(X_i,u),T(X_j,u))
\]

其中 \(\mathcal U_{ij}\) 为两状态拓扑上都允许、并能够生成后继状态的动作集合。

另外定义闭包漂移：

\[
\Delta_{\text{closure}}
=D_1^{mean}-d_{\text{mean}}(X_i,X_j)
\]

解释：

- 初始距离小，后继距离也小：支持行为闭包；
- 初始距离小，但某些相同动作后迅速分离：说明当前 `R0` 过粗，两个状态不能称为真正行为等价；
- 初始距离大但后继变近：只作为诊断，不改变初始等价定义。

---

# 12. 数据：先用 Dev-108 做 discovery，不新增数据

当前 F3 的 108 条数据已经参与过开发，不再具有 blind test 地位，正适合本阶段做 discovery。

要求为每条样本补充：

```text
state_id
run_id
case_id
fine_mechanism
coarse_mechanism
param_group_id
ego_speed
ego_s
ego_lane_id
target_actor_ids
decision_frame
```

## 12.1 机制层级

至少保留两级。

### fine mechanism

例如：

```text
pedestrian_cross
vehicle_cross
cross_stall
slow_lead
stopped_lead
static_blocker
temporary_occupancy
blocked_left_platoon
...
```

按现有 9 cells 的真实定义填写，不要重新合并数据。

### coarse mechanism

统一为：

```text
cross
lead
block_or_occupancy
```

主分析以 coarse mechanism 为准，fine mechanism 用于检查覆盖度。

---

# 13. 候选等价对：禁止手工挑例子

## 13.1 计算全部 pair

108 条状态全部两两组合。

先计算：

```text
d0_mean
d0_max
same_coarse_mechanism
same_fine_mechanism
same_param_group
ego_speed_diff
```

## 13.2 Cross-mechanism candidate

候选“跨机制等价对”必须同时满足：

1. `coarse_mechanism_i != coarse_mechanism_j`
2. `param_group_id_i != param_group_id_j`
3. 两者是 cross-mechanism 空间中的 mutual nearest neighbors
4. `d0_mean` 位于全部 cross-mechanism pair 的最低 10%

记为：

\[
P_{eq}
\]

禁止人为删掉“看着不合理”的 pair。

若：

\[
|P_{eq}|<15
\]

则 Gate B0 discovery 直接记为：

> 当前 R0 尚未形成足够的跨机制候选等价状态。

不要继续做神经网络。

---

# 14. 两类对照

## 14.1 随机跨机制对照

从全部：

```text
coarse_i != coarse_j
```

pair 中随机采样 10000 次 bootstrap，与 \(P_{eq}\) 数量一致。

得到：

\[
P_{random-cross}
\]

## 14.2 同机制、初始距离匹配对照

对于每个 \(P_{eq}\) pair，寻找：

```text
coarse_i == coarse_j
```

且：

```text
|d0_control - d0_eq| <= 0.02
|mean_ego_speed_control - mean_ego_speed_eq| <= 1.0 m/s
```

的 pair。

若多个，选 `d0` 最近者。

记为：

\[
P_{same-matched}
\]

目的：

> 在“初始关系相似程度相当”的前提下，检查跨物理机制 pair 的后继闭包是否比同机制 pair 更差。

如果跨机制 pair 与同机制 pair 一样稳定，说明物理机制身份本身并不是闭包的决定因素。

---

# 15. Discovery Gate 的冻结判据

以下判据在运行结果前冻结。

## G0：工程健康

必须全部满足：

- 108/108 样本 relation signature 可计算；
- 不存在 NaN / sentinel；
- `Q_free > 0`；
- `V_raw > 1.02` 的样本数 = 0；
- 20 Hz → 0.5 s 时间对齐正确；
- successor actor state 与 recorder 的 `t0+1s` 完全一致；
- lane-change successor 保持 `CHANGING_LEFT`，不能瞬移。

否则：

\[
\boxed{STOP}
\]

先修工程，不看科学结果。

## G1：存在候选跨机制等价状态

必须：

\[
|P_{eq}|\ge15
\]

并至少覆盖：

- 3 种 fine-mechanism pair；
- 2 种 coarse-mechanism 组合。

否则：

\[
\boxed{R0\text{ 的跨机制重复性不足}}
\]

## G2：一阶行为闭包

主比较：

\[
\operatorname{median}D_1^{mean}(P_{eq})
\]

与随机跨机制对照。

要求：

\[
\operatorname{median}D_1^{mean}(P_{eq})
\le
0.60\times
\operatorname{median}D_1^{mean}(P_{random-cross})
\]

并使用 10000 次 permutation test：

\[
p<0.01
\]

同时：

\[
\operatorname{median}D_1^{max}(P_{eq})
<
\operatorname{median}D_1^{max}(P_{random-cross})
\]

## G3：机制不应造成明显额外闭包损失

对匹配后的 pair：

\[
\rho=
\frac{
\operatorname{median}D_1^{mean}(P_{eq})
}{
\operatorname{median}D_1^{mean}(P_{same-matched})+\epsilon
}
\]

要求：

\[
\rho\le1.25
\]

解释：

> 在初始关系距离匹配后，跨机制状态的行为闭包不能显著差于同机制状态。

## G4：必须保留“同机制但决策结构不同”的分离能力

在 same-coarse-mechanism pair 中取初始 `d0_mean` 的最高 25%：

\[
P_{same-diff}
\]

要求：

\[
\operatorname{median}D_1^{mean}(P_{same-diff})
\ge
2\times
\operatorname{median}D_1^{mean}(P_{eq})
\]

防止所有状态都被压成“差不多”。

---

# 16. 一阶 PASS 后才做两阶闭包

若 G0-G4 PASS，再执行：

\[
X\xrightarrow{u_1}X'\xrightarrow{u_2}X''
\]

所有动作仍来自相同 8 个动作原语。

为了避免手工挑 action sequence：

- 对每个候选 pair；
- 穷举双方共同有效的 \(u_1,u_2\)；
- 理论最大 64 条 sequence；
- 对无效 sequence 使用 mask，不纳入平均。

定义：

\[
D_2^{mean}
\]

与随机跨机制对照。

两阶 Gate：

\[
\operatorname{median}D_2^{mean}(P_{eq})
\le
0.70\times
\operatorname{median}D_2^{mean}(P_{random-cross})
\]

且：

\[
p<0.01
\]

两阶不是为了追求绝对小距离，而是检查：

> “当前近似等价”是否在连续相同动作下保持明显高于随机状态的结构一致性。

如果一阶 PASS、两阶 FAIL：

> 说明 R0 只能解释局部一阶行为，尚不足以作为稳定状态抽象。

---

# 17. B0-0：冻结环境

执行：

```bash
bash gate_b0/scripts/00_freeze_env.sh
```

必须输出：

```text
gate_b0/results/discovery/env_freeze/
├── git_commit.txt
├── pip_freeze.txt
├── carla_version.txt
├── road_segment_sha256.txt
├── gate_f0_core_sha256.txt
├── gate_b0_config_sha256.txt
└── timestamp.txt
```

若当前目录不是 git repo：

- 不伪造 commit；
- 将所有关键 `.py/.yaml/.json` 计算 sha256。

---

# 18. B0-1：数据健康检查

运行：

```bash
python gate_b0/scripts/01_data_health.py
```

检查：

1. Dev-108 是否全能定位 decision frame；
2. 每条记录是否至少拥有 decision 后 10 s GT；
3. 所有 target_actor_ids 在 horizon 内是否可追踪；
4. Ego / actor bbox 是否完整；
5. `road_id/lane_id` 是否正确；
6. recorder 时间戳是否严格单调；
7. 20 Hz 是否存在明显丢帧；
8. downsample 后是否精确对应 0.5 s。

输出：

```text
gate_b0/results/discovery/data_health.json
gate_b0/results/discovery/data_health.csv
```

---

# 19. B0-2：单状态 action probe smoke

先只挑 4 个现有样本：

```text
static blocker
stopped lead
cross stall
lead optional
```

每个只跑 8 个 action probes。

输出每个动作：

```text
state_id
action_id
ax
lateral_mode
first_1s_feasible
successor_s
successor_v
successor_d
successor_mode
lane_change_elapsed
Q
Q_free
V_raw
V_clipped
num_feasible_continuations
```

人工只检查工程正确性，不评价“结果漂不漂亮”。

必查：

- `START_LEFT` 1 秒后仍在 `CHANGING_LEFT`；
- brake action 的速度确实下降；
- +1.5 action 的速度上升但不超过速度上限；
- free baseline 只删除 target_actor；
- blocker case 中不同动作的 V 有合理差异；
- 无障碍 case 中 V 接近 1。

Smoke PASS 后才批量运行。

---

# 20. B0-3：生成 108 条 R0 signature

运行：

```bash
python gate_b0/scripts/03_build_signatures.py
```

输出：

```text
gate_b0/results/discovery/signatures.csv
gate_b0/results/discovery/action_consequence_long.csv
```

`signatures.csv` 至少包含：

```text
state_id
coarse_mechanism
fine_mechanism
param_group_id

M_U0 V_U0
M_U1 V_U1
...
M_U7 V_U7

datarow_valid
health_reason
```

长表保存每个 action 的详细中间量。

---

# 21. B0-4：自动构造 pair

运行：

```bash
python gate_b0/scripts/04_build_pairs.py
```

输出：

```text
all_pairs.csv
candidate_equivalent_pairs.csv
same_mechanism_matched_pairs.csv
pair_build_summary.json
```

任何 pair selection 都必须由脚本自动完成。

禁止人工编辑 `candidate_equivalent_pairs.csv`。

---

# 22. B0-5：一阶闭包

运行：

```bash
python gate_b0/scripts/05_run_one_step_closure.py
```

对于每个 candidate pair 和每个共同动作：

1. 分别执行相同动作 1 s；
2. 构造两个 successor state；
3. 对 successor 重新计算完整 8 动作 `R0`；
4. 计算 successor relation distance；
5. 缓存，避免重复计算。

输出长表：

```text
closure_action_level.csv
```

字段：

```text
pair_id
state_i
state_j
coarse_i
coarse_j
fine_i
fine_j
d0_mean
d0_max
probe_action
successor_valid_i
successor_valid_j
d1_action_mean
d1_action_max
```

pair summary：

```text
closure_pair_summary.csv
```

字段：

```text
pair_id
d0_mean
d0_max
d1_mean
d1_max
closure_drift
pair_type
```

---

# 23. B0-6：必须输出的图

生成独立图片，不做复杂拼图。

## 图 1：初始关系距离分布

- cross mechanism
- same mechanism

只用于描述。

## 图 2：候选等价对 vs 随机跨机制对的 D1 分布

这是主图。

## 图 3：d0 → d1 散点图

横轴：

\[
d_0
\]

纵轴：

\[
D_1^{mean}
\]

按 `coarse mechanism pair` 区分。

目的是检查低 d0 是否普遍保持低 d1，而不是被某一机制组合单独贡献。

## 图 4：matched comparison

对每个 candidate pair：

```text
cross-mechanism d1
same-mechanism matched d1
```

画 paired comparison。

## 图 5：典型 action signature

只在统计完成后，从以下规则自动选：

- closure 最稳定的 3 个 pair；
- closure 漂移最大的 3 个 pair；

禁止人工挑“最好看的”。

显示：

```text
V(U0)...V(U7)
```

及相同动作后的 successor signature。

---

# 24. 失败后的分支规则

## Case A：G1 FAIL

说明当前：

\[
R_0(X)=\{M,V\}_{8 actions}
\]

本身没有形成足够跨机制重复状态。

结论：

> 当前“动作条件归一化 progress”仍不足以作为 Relation。

停止，不训练网络。

## Case B：G1 PASS，但 G2/G3 FAIL

说明：

> 当前看起来相似的动作后果状态，在执行同样动作以后会分离。

这是最关键的负结果。

不能通过增加网络容量解决。

下一步要分析：

- 缺的是哪一种后果；
- 是安全 margin？
- 是 recourse timing？
- 是动态 actor 响应？
- 是未来分支的多模态结构？

但不能直接手工叠加特征。

## Case C：G2/G3 PASS，但 G4 FAIL

说明：

> 表示可能过度压缩，把本来不同的驾驶状态合并。

不能称为有效 Relation。

## Case D：一阶 PASS、两阶 FAIL

说明：

> 当前 Relation 是局部近似等价，但缺乏多步闭包。

后续需要更丰富的 predictive state，而不是直接训练 planner。

## Case E：一阶与两阶均 PASS

可以得到当前阶段最强但仍有限的结论：

> 在当前 CARLA 受控、非响应式交通参与者条件下，存在跨物理机制重复出现的动作条件可行后果状态；这些状态不仅当前后果相似，而且在施加相同动作后仍保持显著的后继结构相似，支持其作为近似驾驶行为等价状态抽象的候选。

此时才进入 Confirmatory 数据集。

---

# 25. Confirmatory：只有 discovery PASS 后才执行

Dev-108 已经是开发集，不能继续当 blind test。

## 25.1 新 confirmatory 数据

优先复用现有 9 个 cell generator。

每个 cell 新建：

```text
h1 ... h8
```

共：

\[
9\times8=72
\]

条新状态。

要求：

- 参数在开始生成前写入 `confirmatory_params.csv`；
- 参数范围可以沿用已验证物理合理范围；
- 不允许看到 B0 relation 结果后修改某条参数；
- spawn / CARLA crash 可以按同一参数重试；
- 结构“不符合预期”不能改参数，因为 B0 已不使用旧结构标签。

## 25.2 一次性运行

确认：

```text
config hash
pair rule
Gate threshold
action set
distance
```

全部冻结后，一次性：

```text
generate 72
→ health
→ signature
→ pairs
→ one-step closure
→ two-step closure
→ verdict
```

不得看到一部分 confirmatory 结果后再调。

---

# 26. Confirmatory 最终判据

沿用 discovery 的 G0-G4 和 two-step Gate，不再修改阈值。

如果新数据通过：

\[
\boxed{\text{Gate B0 PASS}}
\]

如果失败：

\[
\boxed{\text{Gate B0 FAIL}}
\]

不能用 Dev 结果覆盖 confirmatory 失败。

---

# 27. 本 Gate 与“论文创新”之间的关系

## 27.1 如果 B0 FAIL

当前创新点还不能站住。

最多写成：

> 对动作条件可行未来结构的探索性研究。

不适合把“行为等价状态抽象”作为论文核心贡献。

## 27.2 如果 B0 PASS

可以形成第一条论文级贡献候选：

> **提出并验证一种面向驾驶决策的动作条件可行—补救行为等价状态抽象：不同物理机制下，只要候选动作保留的可行未来能力相似，其状态在相同动作作用后也呈现稳定的后继关系一致性。**

但这仍只是：

\[
\text{存在性 + 闭包性}
\]

还没有证明泛化收益。

后续至少还需要：

### Gate B1：从高维物理状态学习该状态抽象

目标：

\[
X_{\text{physical}}\rightarrow \hat R
\]

主测试：

- 未见物理机制；
- 相同 Relation；
- 不训练 planner。

### Gate B2：状态抽象是否真的降低跨场景学习复杂度

再比较：

\[
X\rightarrow planning
\]

与：

\[
X\rightarrow R\rightarrow planning
\]

但这一步必须使用真正 OOD 的 mechanism/composition split，不能回到普通随机切分。

### Gate B3：公开真实数据与闭环验证

优先：

- Waymo Motion：真实物理状态分布和 actor/map；
- nuScenes：补充真实数据；
- CARLA：受控 counterfactual + closed-loop；
- 后续若资源允许，可接公开闭环规划 benchmark。

---

# 28. 为什么这个方向仍可能有创新，而不是重复已有文献

当前最接近的几条已有路线分别解决：

1. **双模拟**：什么叫行为相似状态；
2. **后继表示**：如何利用未来转移结构迁移；
3. **可达集**：哪些驾驶走廊可行；
4. **Field of Safe Motion**：是否保留 collision-free out；
5. **动作条件世界模型**：某候选动作下完整未来场景如何演化；
6. **因果/双模拟驾驶表示**：状态动作对长期 reward/safety consequence 的 OOD 表示。

本研究当前试图解决的是它们之间尚未直接等价的问题：

> **能否用“动作对未来可行能力和补救空间的影响”定义驾驶状态等价，而不依赖具体场景类别、专家动作、奖励函数或完整未来场景重建，并证明这种等价在动作作用下具有闭包性？**

这是当前应该守住的创新边界。

若以后研究退化成：

- 仅预测未来 BEV；
- 仅预测动作 reward；
- 仅计算 reachable corridor；
- 仅使用 bisimulation loss；
- 仅做 cross-scene transfer；

则创新会明显变弱。

---

# 29. 参考文献脉络（执行阶段必须精读）

1. Ferns, Panangaden, Precup. **Metrics for Finite Markov Decision Processes.** UAI 2004.  
   用途：状态行为等价、双模拟距离、状态聚合理论基础。

2. Zhang et al. **Deep Bisimulation for Control.** ICLR 2021.  
   用途：控制相关潜在表示、任务无关信息不变性。

3. Xiao et al. **Action-based Representation Learning for Autonomous Driving.** CoRL 2021.  
   用途：动作监督表示与端到端驾驶中的虚假相关问题。

4. Kochdumper & Bak. **Real-Time Capable Decision Making for Autonomous Driving Using Reachable Sets.** ICRA 2024. DOI: `10.1109/ICRA57147.2024.10610689`.  
   用途：可达驾驶走廊、离散变道事件、避免把 reachable corridor 当成创新。

5. Lu et al. **Scenario-level knowledge transfer for motion planning of autonomous driving via successor representation.** Transportation Research Part C, 2024, 169:104899. DOI: `10.1016/j.trc.2024.104899`.  
   用途：跨场景状态转移知识复用，明确“场景迁移”不是空白。

6. Waymo. **The Field of Safe Motion: Operationalizing Affordances in the Field of Safe Travel Using Reachability Analysis.** 2026.  
   用途：安全 affordance、collision-free escape route、reachability。

7. Zhao et al. **Safe Decision-Making via Adaptive Causal Representation for Autonomous Driving.** IEEE TNNLS, 2026. DOI: `10.1109/TNNLS.2026.3708993`.  
   用途：长期 reward/safety consequence、bisimulation regularization、OOD 泛化；必须重点区分。

8. **DriveWorld-VLA: Unified Latent-Space World Modeling with Vision-Language-Action for Autonomous Driving.** arXiv:`2602.06521`, 2026.  
   用途：动作条件未来想象，避免把“action-conditioned future”本身当创新。

9. **DA-WAM: Decision-Aligned Future Latents for Driving World Models.** arXiv:`2608.19085`, 2026.  
   用途：每条候选轨迹独立预测 action-conditioned future latent，并直接用于轨迹评分；是当前非常接近的竞争方向。

---

# 30. 最终执行顺序

严格执行：

```text
B0-0 冻结环境
  ↓
B0-1 Dev-108 数据健康
  ↓
B0-2 4-state action probe smoke
  ↓
B0-3 108-state R0 signatures
  ↓
B0-4 自动 pair 构造
  ↓
B0-5 一阶闭包
  ↓
G0-G4 verdict
  ↓
若 FAIL：停止并定位 Relation 定义
若 PASS：
  ↓
B0-7 两阶闭包
  ↓
若 FAIL：停止
若 PASS：
  ↓
冻结所有定义和阈值
  ↓
生成 72 条全新 confirmatory
  ↓
一次性 confirmatory
  ↓
最终 Gate B0 PASS / FAIL
```

---

# 31. 给执行 AI 的最后约束

1. **不要为了通过 Gate 改结果。**
2. **不要自动新增关系特征。**
3. **不要把旧三分类当 ground truth。**
4. **不要人工挑 pair。**
5. **不要把 scripted actor 的非响应式假设写成真实世界结论。**
6. **任何 bug 修复必须记录 diff、理由、影响范围，并重跑受影响的全部样本。**
7. **所有中间结果必须落盘，不只保存最终平均值。**
8. **如果实验得到负结果，按负结果报告，不继续堆网络。**
9. **本 Gate 的成功标准是“跨物理机制的动作后行为闭包”，不是规划得分。**
10. **Gate B0 结束前，不进入 PlanT、端到端训练或公开数据大规模学习。**
