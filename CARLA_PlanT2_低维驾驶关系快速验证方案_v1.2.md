# 基于 CARLA + PlanT 2.0 的“低维可复用驾驶关系”快速验证方案

> 修订版：v1.2（在 v1.1 基础上补充 Scenario Type × Town × Route/Frame/Sample 分布审计、Town/Scenario 双层 holdout 设计）

> 版本：2026-08-31
> 
> 目标：在**不先解决完整视觉感知、不先重新设计复杂动态安全包络**的前提下，用 CARLA 闭环驾驶快速验证以下核心研究假设是否值得继续投入：
>
> **人类驾驶并不依赖大量精确物理数值，却能够将有限经验迁移到高度多样的场景。这提示我们，支撑驾驶决策的核心信息可能存在一种低维、可复用、与自车行动相关的关系结构。机器仍可保留精确物理状态用于计算和严格安全验证，但决策学习是否可以更多地发生在这种关系空间中，并由此获得更好的跨场景/分布外泛化，是需要实验验证的问题。**

---

# 0. 先说结论：本方案为什么这样设计

当前不建议从零写 MLP、PPO 或完整端到端视觉模型。最合适的快速实验载体是 **PlanT 2.0**：它已经是一个能够在 CARLA 中闭环驾驶的、基于结构化目标输入的 Transformer planner；原始每个 object token 正好由：

```text
[type, x, y, yaw, speed, width, length]
```

组成，即 **1 个类别 + 6 个连续属性**。

因此我们可以做一个非常干净的控制变量实验：

```text
A. Exact-State PlanT 2.0
   CARLA 真值 → [x, y, yaw, speed, width, length] → 原 PlanT 2.0 → 路径/航点 → 控制

B. Relation PlanT 2.0
   CARLA 真值 → 关系变换 → [关系1...关系6] → 同一个 PlanT 2.0 → 路径/航点 → 控制
```

**Transformer、规划头、route 输入、道路 BEV、控制器全部保持一致，只改变动态/静态对象的表示。**

这可以把实验问题缩成：

> 在同一个已经具备驾驶能力的 planner 上，把“精确对象状态”换成“驾驶关系状态”，是否能在保持基本闭环驾驶能力的同时，在未见参数/未见区域/后续未见场景中表现出更好的迁移能力？

第一轮关系表示不追求最终理论完美。它只是一个 **Proxy Relation / 代理关系表示**，用于判断核心研究方向有没有信号。若有信号，再回头认真设计动态安全包络、概率占用、不确定性和 Action Effect；若没有，就尽早修改关系定义，而不是先做半年工程。

---

# 1. 我已经核实过的关键兼容性结论

## 1.1 PlanT 2.0 官方版本

本方案固定使用：

```text
Repository: autonomousvision/plant2
Commit:     6269e5a43c6f6b984d2bd97e3ec4a025ebefbeef
```

该仓库官方 README 明确将 PlanT 2.0 描述为：

- lightweight；
- object-centric；
- CARLA closed-loop planner；
- 支持通过 object-level representation 做 controlled perturbation；
- 已提供模型、数据和 Leaderboard/ScenarioRunner 相关代码。

## 1.2 一个必须注意的 CARLA 版本问题

你目前只有 **CARLA 0.9.16**。

但是我核对了 PlanT 2.0 官方仓库：

- `setup_carla.sh` 明确下载 **CARLA 0.9.15**；
- `environment.yml` 明确固定 `carla==0.9.15`；
- 官方快速运行路径也是按 0.9.15 配置的。

因此本方案**不建议强行拿你现有 0.9.16 去兼容 PlanT 2.0**。

最稳妥方案是：

```text
你现有 CARLA 0.9.16：保留，不动

新建：
~/research/plant2/carla/    → 单独安装 CARLA 0.9.15
```

这不会破坏你原来的 0.9.16。

> 为什么不直接改成 0.9.16？
>
> 因为我们当前目标是“快速验证研究假设”，而不是研究 CARLA/Leaderboard 兼容性。主动引入版本偏差，会把本来很干净的表示实验变成环境调试实验。

## 1.3 操作系统前提

下面完整流程以 **Ubuntu/Linux + NVIDIA GPU** 为准，因为：

- PlanT 2.0 官方脚本使用 `CarlaUE4.sh`；
- 官方 `environment.yml` 固定了 Linux/CUDA 相关依赖；
- 官方实验流程也是 Linux 环境。

### 在正式开始前先执行

```bash
uname -a
nvidia-smi
conda --version
python --version
df -h
```

如果 `uname -a` 不是 Linux，**不要直接照抄下面命令**。原生 Windows 可能可以通过手工适配运行，但那不是当前官方仓库已验证路径，不符合这次“尽量一次跑通”的目标。

建议磁盘预留较充足空间，因为需要：

- CARLA 0.9.15 + Additional Maps；
- PlanT 2.0 数据集压缩包约 8.77 GB，解压后还会扩大；
- 模型 checkpoint；
- 训练输出。

---

# 2. 整个实验分为 5 个 Gate，不要一次全做

严格按下面顺序进行：

```text
Gate 0：原版 PlanT 2.0 能否在 CARLA 里开起来？
                 ↓
Gate 1：关系特征计算是否正确？
                 ↓
Gate 2：Exact / Relation 两套数据是否能够正常训练？
                 ↓
Gate 3：两种表示是否都能完成基础闭环驾驶？
                 ↓
Gate 4：Relation 是否在 OOD / held-out 条件下更稳？
```

任何一个 Gate 没通过，先修这一层，不要往后堆模块。

---

# 3. Gate 0：完整复现原始 PlanT 2.0

这是最重要的第一步。

如果未经修改的 PlanT 2.0 都跑不起来，那么任何 Relation 实验都没有意义。

## 3.1 建工作目录

```bash
mkdir -p ~/research
cd ~/research
```

## 3.2 下载 PlanT 2.0，并固定 commit

```bash
git clone https://github.com/autonomousvision/plant2.git
cd plant2

git checkout 6269e5a43c6f6b984d2bd97e3ec4a025ebefbeef

git status
git rev-parse HEAD
```

最后一条应该输出：

```text
6269e5a43c6f6b984d2bd97e3ec4a025ebefbeef
```

然后建立自己的实验分支：

```bash
git checkout -b relation-pilot
```

以后所有修改都在这个分支进行。

---

## 3.3 单独安装 CARLA 0.9.15

不要动你原来的 0.9.16。

在 `plant2` 根目录：

```bash
chmod +x setup_carla.sh
./setup_carla.sh
```

官方脚本会创建：

```text
plant2/carla/
```

并下载：

- CARLA 0.9.15 Linux；
- AdditionalMaps 0.9.15；
- 执行 `ImportAssets.sh`。

检查：

```bash
ls carla/CarlaUE4.sh
ls carla/PythonAPI/carla
```

至少都应该存在。

### 如果下载脚本报 `wget: command not found`

Ubuntu：

```bash
sudo apt update
sudo apt install wget -y
```

然后重新运行：

```bash
./setup_carla.sh
```

---

## 3.4 创建官方 PlanT 2.0 Python 环境

不要自己猜 torch / transformers 版本，第一轮直接按官方 `environment.yml`。

```bash
cd ~/research/plant2
conda env create -f environment.yml
conda activate plant2
```

验证：

```bash
python - <<'PY'
import torch
import transformers
import carla
print('torch:', torch.__version__)
print('transformers:', transformers.__version__)
print('carla module:', carla.__file__)
print('cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu:', torch.cuda.get_device_name(0))
PY
```

官方环境当前固定的关键项包括：

```text
Python 3.10
PyTorch 2.6.0
Transformers 4.49.0
carla 0.9.15
```

如果 `torch.cuda.is_available()` 是 `False`，先不要继续训练。

---

## 3.5 建一个统一环境变量脚本

在仓库根目录创建：

```bash
nano env_plant2.sh
```

写入：

```bash
#!/usr/bin/env bash

export WORK_DIR="$HOME/research/plant2"
export CARLA_ROOT="$WORK_DIR/carla"
export SCENARIO_RUNNER_ROOT="$WORK_DIR/scenario_runner_autopilot"
export LEADERBOARD_ROOT="$WORK_DIR/leaderboard_autopilot"

export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:$LEADERBOARD_ROOT:$SCENARIO_RUNNER_ROOT:$WORK_DIR/PlanT:$WORK_DIR/carla_garage:$PYTHONPATH"

# 先关闭 PlanT 可视化，减少不必要的变量
export PLANT_VIZ=""

# 训练阶段不用在线上传 wandb
export WANDB_MODE=offline
```

保存后：

```bash
chmod +x env_plant2.sh
source env_plant2.sh
```

检查：

```bash
echo $CARLA_ROOT
echo $WORK_DIR
echo $PYTHONPATH
```

---

## 3.6 启动 CARLA 0.9.15

终端 A：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

$CARLA_ROOT/CarlaUE4.sh
```

如果服务器不接显示器，可以尝试：

```bash
$CARLA_ROOT/CarlaUE4.sh -RenderOffScreen
```

保持终端 A 不关闭。

终端 B 验证 Python 客户端：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

python - <<'PY'
import carla
client = carla.Client('localhost', 2000)
client.set_timeout(10.0)
world = client.get_world()
print('Connected.')
print('Map:', world.get_map().name)
PY
```

只有看到 `Connected.` 和地图名，才能进入下一步。

---

# 4. 下载官方 PlanT 2.0 checkpoint，先让原版车开起来

官方 Hugging Face 模型仓库目前包含 3 个 checkpoint，每个约 447 MB，总大小约 1.34 GB：

```text
epoch=029_final_1.ckpt
epoch=029_final_2.ckpt
epoch=029_final_3.ckpt
```

第一轮只下载一个即可。

## 4.1 使用 huggingface-cli 下载一个 checkpoint

在 `plant2` 环境：

```bash
cd ~/research/plant2
mkdir -p checkpoints/PlanT2

huggingface-cli download \
  SimonGer/PlanT2 \
  'epoch=029_final_1.ckpt' \
  --local-dir checkpoints/PlanT2
```

检查：

```bash
ls -lh checkpoints/PlanT2
```

应该看到约 447 MB 的 `.ckpt`。

设置：

```bash
export PLANT_CHECKPOINT="$WORK_DIR/checkpoints/PlanT2/epoch=029_final_1.ckpt"
```

---

## 4.2 原版闭环 smoke test

保证终端 A 中 CARLA 已经运行。

终端 B：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

export PLANT_CHECKPOINT="$WORK_DIR/checkpoints/PlanT2/epoch=029_final_1.ckpt"
export PLANT_VIZ=""

mkdir -p outputs/smoke

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes=leaderboard/data/longest6_split/longest6_00.xml \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/smoke/original_plant2.json \
  --timeout=300
```

### Gate 0 通过标准

至少满足：

1. agent 成功初始化；
2. checkpoint 成功加载；
3. CARLA 中 ego 能开始运行，而不是 setup crash；
4. evaluator 能生成 `outputs/smoke/original_plant2.json`；
5. 没有 Python API/CARLA 版本不匹配错误。

**不要先关心分数高低。第一步只验证官方 pipeline 完整可用。**

如果这里跑不通，不要修改 Relation 代码。

---

# 5. 下载 PlanT 2.0 官方训练数据

官方数据集：

```text
SimonGer/PlanT2_Dataset
```

当前公开文件：

```text
PlanT2_DS.zip
约 8.77 GB
```

下载：

```bash
cd ~/research/plant2
mkdir -p data/PlanT2_Dataset

huggingface-cli download \
  SimonGer/PlanT2_Dataset \
  PlanT2_DS.zip \
  --repo-type dataset \
  --local-dir data/PlanT2_Dataset
```

查看：

```bash
ls -lh data/PlanT2_Dataset/PlanT2_DS.zip
```

解压：

```bash
mkdir -p data/PlanT2_DS
unzip data/PlanT2_Dataset/PlanT2_DS.zip -d data/PlanT2_DS
```

然后必须检查目录结构，而不是直接猜 `DS`：

```bash
find data/PlanT2_DS -maxdepth 4 -type d -name boxes | head -20
find data/PlanT2_DS -maxdepth 4 -type d -name measurements | head -20
```

`PlanTDataset` 训练代码要求环境变量：

```text
$DS/data
```

下面必须存在大量 route 子目录，并且 route 内有：

```text
boxes/
measurements/
bev_no_car_semantics/
```

例如，如果解压后实际结构是：

```text
~/research/plant2/data/PlanT2_DS/data/...
```

那么：

```bash
export DS="$WORK_DIR/data/PlanT2_DS"
```

检查：

```bash
test -d "$DS/data" && echo "DS structure OK" || echo "DS PATH WRONG"
find "$DS/data" -type d -name boxes | wc -l
```

只有出现 `DS structure OK` 才继续。

---

# 6. 第一轮 Relation 不做复杂动态安全包络：用“代理关系”做证伪实验

这里非常重要。

我们现在不是要证明最终动态安全包络已经完成，而是先回答：

> **把精确对象状态变成一种与自车安全交互更直接相关的表示，是否值得继续？**

因此第一版关系由当前 CARLA 真值 + 简单匀速相对运动计算，完全不依赖未来真值，不产生 closed-loop information leakage。

## 6.1 原 PlanT token

原 PlanT 2.0 每个对象：

```text
[type,
 x,
 y,
 relative_yaw,
 speed,
 width,
 length]
```

## 6.2 第一版 Relation token

我们保持仍为 `type + 6 values`，这样 **PlanT/model.py 完全不需要改**：

```text
[type,
 current_clearance,
 predicted_min_clearance,
 closing_rate,
 time_to_closest_approach,
 cos(bearing),
 sin(bearing)]
```

解释：

### 1. current_clearance

当前对象与自车的几何净余量：

\[
M_0 = \|p\|-(r_{ego}+r_i)
\]

第一版用 bounding circle 近似，目的不是最终精确安全模型，而是快速建立关系变量。

### 2. predicted_min_clearance

假设未来短时内双方保持当前速度和朝向，计算预测窗口内最小净余量：

\[
M_{min}=\min_{\tau\in[0,H]}\|p+v_{rel}\tau\|-(r_{ego}+r_i)
\]

### 3. closing_rate

对象与自车之间的径向接近速度：

\[
c=-\frac{p^T v_{rel}}{\|p\|+\epsilon}
\]

约定：

```text
closing_rate > 0：正在接近
closing_rate < 0：正在远离
```

### 4. time_to_closest_approach

\[
\tau^*=clip\left(-\frac{p^T v_{rel}}{\|v_{rel}\|^2+\epsilon},0,H\right)
\]

表示未来短时内什么时候达到最近状态。

### 5-6. cos/sin(bearing)

保留对象相对自车的粗方向结构，但不再直接暴露精确 `x,y`。

这样可以区分：

- 前方冲突；
- 左侧冲突；
- 右侧冲突；
- 后方对象。

> 注意：这 6 个量不是最终论文定义。
>
> 它们只是第一版 **Proxy Relational Representation**。如果这一版都完全没有信号，则应该先重新思考关系，而不是马上加 SURE-Plan、可达集和复杂包络。
>
> **另外，这一轮为了完全复用 PlanT 2.0 的 `Linear(6, hidden)` 输入接口，Relation 也暂时保留 6 个连续量。因此第一轮首先检验的是“关系抽象是否更可复用”，并不能单独证明“维度更低”。低维性必须在第二阶段通过 6→5→4→3 项关系消融以及后续全局关系聚合来证明。**

---

# 7. 创建共享关系计算文件

新建：

```bash
nano PlanT/relation_features.py
```

完整写入：

```python
import math
import numpy as np

EPS = 1e-6
HORIZON = 4.0       # s，第一轮代理值
DIST_SCALE = 50.0   # m，与 PlanT 默认目标范围量级保持一致
SPEED_SCALE = 20.0  # m/s，归一化尺度


def _half_diagonal_from_wh(width: float, length: float) -> float:
    """由完整宽/长计算外接圆半径。"""
    return 0.5 * float(np.hypot(width, length))


def relationize_exact_row(row, ego_speed_mps, ego_extent, horizon=HORIZON):
    """
    将 PlanT 原始 object row 转为关系 row。

    输入 row：
        训练阶段：
        [type, x, y, yaw_deg, speed_kmh, width, length, id]

        在线推理：
        [type, x, y, yaw_deg, speed_kmh, width, length]

    ego_extent：CARLA BoundingBox.extent 风格：
        [half_length_x, half_width_y, half_height_z]

    输出列数和输入保持一致：
        [type,
         m_now_norm,
         m_min_norm,
         closing_norm,
         tcpa_norm,
         cos_bearing,
         sin_bearing,
         (optional id)]
    """
    if len(row) not in (7, 8):
        raise ValueError(f"Expected row with 7 or 8 columns, got {len(row)}")

    type_id = row[0]

    x = float(row[1])
    y = float(row[2])
    yaw_rad = np.deg2rad(float(row[3]))
    obj_speed_mps = float(row[4]) / 3.6
    width = float(row[5])
    length = float(row[6])

    # PlanT / CARLA 自车局部坐标：x 轴朝车头前方。
    p = np.array([x, y], dtype=np.float64)

    v_obj = obj_speed_mps * np.array(
        [np.cos(yaw_rad), np.sin(yaw_rad)],
        dtype=np.float64,
    )
    v_ego = np.array([float(ego_speed_mps), 0.0], dtype=np.float64)
    v_rel = v_obj - v_ego

    # CARLA extent 本身是半尺寸，所以自车外接圆半径直接 hypot(extent_x, extent_y)
    ego_radius = float(
        np.hypot(float(ego_extent[0]), float(ego_extent[1]))
    )
    obj_radius = _half_diagonal_from_wh(width, length)
    r_sum = ego_radius + obj_radius

    d_now = float(np.linalg.norm(p))
    m_now = d_now - r_sum

    # Constant-velocity closest point of approach
    vv = float(v_rel @ v_rel)
    if vv < EPS:
        tcpa = 0.0
    else:
        tcpa = float(
            np.clip(
                -float(p @ v_rel) / (vv + EPS),
                0.0,
                horizon,
            )
        )

    p_cpa = p + v_rel * tcpa
    m_min = float(np.linalg.norm(p_cpa) - r_sum)

    if d_now < EPS:
        closing = 0.0
    else:
        closing = float(-float(p @ v_rel) / (d_now + EPS))

    bearing = math.atan2(y, x)

    features = [
        float(np.clip(m_now / DIST_SCALE, -2.0, 2.0)),
        float(np.clip(m_min / DIST_SCALE, -2.0, 2.0)),
        float(np.clip(closing / SPEED_SCALE, -2.0, 2.0)),
        float(np.clip(tcpa / max(horizon, EPS), 0.0, 1.0)),
        float(np.cos(bearing)),
        float(np.sin(bearing)),
    ]

    output = [type_id, *features]

    # 训练数据里还有 object id；必须保留到原 forecasting target 完成匹配以后。
    if len(row) == 8:
        output.append(row[-1])

    return output
```

---

# 8. Gate 1：先给关系函数做单元测试

创建：

```bash
mkdir -p tests
nano tests/test_relation_features.py
```

写入：

```python
from relation_features import relationize_exact_row


ego_extent = [2.2, 0.9, 0.7]

# 1. 前方静止物体，自车 10 m/s：应该正在接近，未来最小余量下降
row_stationary = [1, 20.0, 0.0, 0.0, 0.0, 1.8, 4.4]
r1 = relationize_exact_row(row_stationary, 10.0, ego_extent)
assert r1[3] > 0.0, r1                    # closing > 0
assert r1[2] < r1[1], r1                  # min margin < current margin
assert r1[5] > 0.99 and abs(r1[6]) < 1e-3 # bearing 向正前方

# 2. 前车同速同向：closing 应接近 0，未来最小余量不明显恶化
row_same_speed = [1, 20.0, 0.0, 0.0, 36.0, 1.8, 4.4]
r2 = relationize_exact_row(row_same_speed, 10.0, ego_extent)
assert abs(r2[3]) < 1e-5, r2
assert abs(r2[2] - r2[1]) < 1e-5, r2

# 3. 右侧/侧向对象：bearing 的 sin 不应为 0
row_side = [1, 10.0, -10.0, 90.0, 36.0, 1.8, 4.4]
r3 = relationize_exact_row(row_side, 10.0, ego_extent)
assert abs(r3[6]) > 0.1, r3

print('All relation feature tests passed.')
print('stationary:', r1)
print('same speed:', r2)
print('side:', r3)
```

运行：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

python tests/test_relation_features.py
```

期望看到：

```text
All relation feature tests passed.
```

若失败，先不要碰训练代码。

---

# 9. 给配置加入 exact / relation 开关

编辑：

```bash
nano PlanT/config/model/PlanT.yaml
```

在 `training:` 下增加：

```yaml
  input_representation: exact

  # 第一阶段：地图域 holdout
  exclude_towns: []
  include_towns: []

  # 第二阶段预留：场景类型 holdout
  exclude_scenarios: []
  include_scenarios: []
```

不要删除其他原始配置。

最后类似：

```yaml
training:
  range: 50
  range_factor_front: 2
  input_ego_speed: False
  input_bev: True
  input_static_cars: True

  input_representation: exact
  exclude_towns: []
  include_towns: []
  exclude_scenarios: []
  include_scenarios: []
```

这里提前加入 Scenario filter，不代表第一轮马上做 Scenario Holdout，而是避免后面重新改 Dataset。当前 PlanT2 官方数据采集脚本本身就按 `data/<scenario_type>/<Town...route>/` 保存，因此 `scenario_type` 可以直接从 route 目录的父目录读取。

### 为什么暂时保留 `input_bev=True`？

我核对了 PlanT 2.0 的 BEV 生成代码：动态车辆、walker、红绿灯等相关绘制逻辑在当前版本中被注释掉，`bev_semantic_classes` 只保留：

- road；
- sidewalk；
- lane marking。

训练文件名本身也叫：

```text
bev_no_car_semantics
```

因此保留该 BEV 主要是在给模型道路结构，而不是让 Relation 模型从 BEV 旁路读取精确周车位置。

这正适合当前实验：

```text
道路与 route 信息：Exact / Relation 两组共享
动态/静态参与者表示：只通过 object token 改变
```

---

# 10. 修改训练 Dataset：只在最后一步把 exact row 换成 relation row

编辑：

```bash
nano PlanT/dataset.py
```

## 10.1 加 import

在文件顶部 import 区加入：

```python
from relation_features import relationize_exact_row
```

## 10.2 不要重写官方 object filtering

这是一个很重要的工程原则。

官方 Dataset 已经处理了：

- emergency vehicle；
- static object；
- static car；
- red/yellow traffic light；
- stop sign；
- 距离过滤；
- object id；
- forecasting target matching。

**不要第一天就把这些重写。**

我们应该让官方代码先正常构造：

```text
[type, x, y, yaw, speed, width, length, id]
```

并且完成 `output_objects_matched` 后，才替换输入表示。

## 10.3 插入关系变换

找到类似下面的位置：

```python
sample["output_floating"] = output_objects_matched
sample["output"] = output_objects_quantized

# remove id
input_objects = [x[:-1] for x in input_objects]

sample["input"] = input_objects
```

把它改成：

```python
sample["output_floating"] = output_objects_matched
sample["output"] = output_objects_quantized

# ------------------------------------------------------------
# Relation pilot: only transform planner INPUT after the original
# forecasting target matching has already used exact-state objects.
# ------------------------------------------------------------
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

# remove id
input_objects = [x[:-1] for x in input_objects]

sample["input"] = input_objects
```

### 为什么必须放在这里？

原始 PlanT 的 forecasting target 代码假设 `input_objects` 中第 1~4 个连续属性仍然是：

```text
x, y, yaw, speed
```

如果过早替换成 Relation，会污染官方 `output_objects_matched` 的生成逻辑。

所以：

```text
先走完原官方 target 逻辑
             ↓
最后只改 planner input
```

这是最小侵入的方式。

---

# 11. 修改在线 PlanT Agent：推理阶段必须做同样的 Relation 变换

训练和推理最怕一个问题：

```text
training representation != inference representation
```

所以 `PlanT_agent.py` 必须和 Dataset 共用同一个 `relation_features.py`。

编辑：

```bash
nano PlanT/PlanT_agent.py
```

## 11.1 加 import

```python
from relation_features import relationize_exact_row
```

## 11.2 setup 中读取 checkpoint 自带 representation 配置

找到：

```python
self.input_bev = ...
self.input_static_cars = ...
```

后面增加：

```python
self.input_representation = self.cfg_net["model"]["training"].get(
    "input_representation", "exact"
)

print("Input representation:", self.input_representation)
```

因为 `PlanT_agent.py` 会从 checkpoint 的 hyperparameters 中读取 cfg，所以：

```text
Exact checkpoint → 自动 exact
Relation checkpoint → 自动 relation
```

不需要手动维护两套 agent。

## 11.3 get_input_batch 中进行变换

找到：

```python
data_car += [...]

features = data_car
```

在 `features = data_car` 之前插入：

```python
if self.input_representation == "relation":
    if len(label_raw) == 0:
        raise RuntimeError("No CARLA bounding-box data available.")

    ego_obj = label_raw[0]
    if "extent" not in ego_obj:
        raise RuntimeError("Ego bounding box has no extent.")

    data_car = [
        relationize_exact_row(
            row,
            ego_speed_mps=input_data["speed"],
            ego_extent=ego_obj["extent"],
        )
        for row in data_car
    ]

features = data_car
```

> 当前 PlanT 2.0 / DataAgent 的 bounding-box 逻辑中，ego object 是列表第一项，Dataset 同样使用 `labels_data_all[1:]` 去掉第一项 ego，因此这套写法和当前固定 commit 的数据结构是一致的。

---

# 12. 为什么 PlanT/model.py 不需要修改

我核对了当前 `PlanT/model.py`：

```python
self.num_attributes = 6
```

每种 object type 都是：

```python
nn.Linear(6, hidden_dim)
```

我们的 Exact token：

```text
6 continuous values
```

我们的 Relation token：

```text
6 continuous values
```

所以：

```text
Transformer 不改
Hidden size 不改
Planning head 不改
Waypoints head 不改
Controller 不改
```

这是本实验最重要的控制变量设计之一。

---

# 13. 暂时关闭/统一几个会破坏公平性的默认配置

## 13.0 Exact 和 Relation 两组必须都输入 ego speed

这一点是实验公平性的硬要求。

Relation 代理特征中的 `closing_rate`、`predicted_min_clearance` 会使用自车速度。如果 Relation 使用了 ego speed，而 Exact baseline 仍保持 PlanT 2.0 默认：

```yaml
input_ego_speed: False
```

那么 Relation 实际上多得到了一条 baseline 没有的信息，无法把性能差异归因于“关系抽象”。

因此从**我们自己的 A/B 训练开始**，Exact 和 Relation 两组统一设置：

```text
model.training.input_ego_speed=true
```

### 13.0.1 必须先修复当前 commit 中 `input_ego_speed` 的数据键缺失

这里有一个上游代码中的 latent bug，必须在第 15 节训练 smoke test 之前修复。

当前 `PlanT/model.py` 在 `input_ego_speed=true` 时读取：

```python
batch["input_ego_speed"]
```

但是原始训练数据路径 `PlanT/dataset.py` 只生成：

```python
sample["ego_speed"]
```

原始在线推理路径 `PlanT/PlanT_agent.py` 也只生成：

```python
sample["ego_speed"]
```

而 `generate_batch()` 只会把 sample **已经存在的 key** 自动 stack 成 batch 字段。因此若不修复，开启 `model.training.input_ego_speed=true` 后会直接出现：

```text
KeyError: 'input_ego_speed'
```

这也是为什么官方默认 checkpoint 没有暴露这个问题：官方默认配置是 `input_ego_speed: False`。

#### 修复 A：训练数据路径

编辑：

```text
PlanT/dataset.py
```

找到：

```python
sample["target_speed"] = loaded_measurements[self.cfg_train.seq_len - 1]["target_speed"]
sample["ego_speed"] = loaded_measurements[self.cfg_train.seq_len - 1]["speed"]
```

紧接着增加：

```python
sample["input_ego_speed"] = sample["ego_speed"]
```

#### 修复 B：在线闭环推理路径

编辑 `PlanT/PlanT_agent.py`，在 `get_input_batch()` 中找到：

```python
sample["route_original"] = input_data["route"]
sample["speed_limit"] = input_data["speed_limit"]
sample["ego_speed"] = input_data["speed"]
```

紧接着增加：

```python
sample["input_ego_speed"] = input_data["speed"]
```

`generate_batch()` 不需要修改，因为它会遍历 sample 的全部非 `input/output` key，并自动 stack `input_ego_speed`。

#### 修复后的最小检查

可在 `model.py` forward 中临时加入：

```python
if self.input_ego_speed:
    assert "input_ego_speed" in batch
    assert batch["input_ego_speed"].ndim == 1
```

跑通 Gate 2A 后可删除该调试断言。

> 第 4 节使用官方预训练 checkpoint 做 Gate 0 时仍按官方 checkpoint 自己的配置运行，不强行改它；只有我们重新训练 Exact / Relation 对照模型时统一打开 ego speed。

PlanT 2.0 默认配置中：

```yaml
augment: True
augment_parked: True
forecastLoss_weight: 1
```

第一轮 Relation 实验不要直接用这三个默认项。

## 13.1 必须关闭 `augment`

原因：当前 `aug_sample()` 明确假设：

```text
input[:, 1:3] 是 x,y
input[:, 3] 是 yaw
```

它会对这些列做平移和旋转。

Relation token 已经不是 x/y/yaw，如果还开 augmentation，会把关系特征错误地当坐标旋转。

所以 Exact 和 Relation 两组都设：

```text
model.training.augment=false
```

否则两组预处理不一致，实验不公平。

## 13.2 必须关闭 `augment_parked`

当前官方 Dataset 代码里存在作者机器上的硬编码路径：

```text
/home/geiger/gwb301/code/PlanT_2_cleanup/PlanT/car_data.npy
```

外部机器直接使用容易报错。

第一轮两组统一：

```text
model.training.augment_parked=false
```

## 13.3 第一轮关闭 forecasting loss

我们的目标是先研究 planner representation，而不是同时研究 object forecasting。

因此两组统一：

```text
model.pre_training.forecastLoss_weight=0
```

注意：当前代码仍然可能计算 forecasting logits/loss 用于日志，但权重为 0，不参与总 loss。

---

# 14. 建本地 user config

复制官方 user config：

```bash
cd ~/research/plant2
cp PlanT/config/user/simon.yaml PlanT/config/user/local.yaml
```

编辑：

```bash
nano PlanT/config/user/local.yaml
```

只写：

```yaml
working_dir: /home/YOUR_USER/research/plant2
```

一定替换成你的**绝对路径**。

检查：

```bash
cat PlanT/config/user/local.yaml
pwd
```

二者应该对应。

---

# 15. Gate 2A：训练代码 smoke test，不追求学会驾驶

目的只有一个：确认我们的修改不会出现 shape / dataloader / forward / checkpoint 错误。

设置：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

export DS="$WORK_DIR/data/PlanT2_DS"   # 按你实际解压目录修改
export SEED=1
export WANDB_MODE=offline
```

再次确认：

```bash
test -d "$DS/data" && echo OK
```

## 15.1 Exact smoke

```bash
export CHECKPOINT_ADDON=exact_smoke

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
  model.training.input_representation=exact \
  model.pre_training.forecastLoss_weight=0 \
  expname=exact_smoke
```

通过标准：

- Dataloader 能加载；
- `x_objs` shape 正常；
- forward 正常；
- waypoint/path loss 能计算；
- checkpoint 能保存。

## 15.2 Relation smoke

```bash
export CHECKPOINT_ADDON=relation_smoke

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
  model.training.input_representation=relation \
  model.pre_training.forecastLoss_weight=0 \
  expname=relation_smoke
```

两边都不报错，才进入真正训练。

## 15.3 Gate 2A / Pilot 的 checkpoint 保存规则

当前 `PlanT/lit_train.py` 设置：

```python
ModelCheckpoint(
    save_top_k=-1,
    save_last=True,
    every_n_epochs=10,
    save_on_train_epoch_end=True,
)
checkpoint_callback.CHECKPOINT_NAME_LAST = f"last_{seed}"
```

因此：

```text
Gate 2A：max_epochs=1  → PlanT/checkpoints/last_1.ckpt
Pilot：max_epochs=5   → PlanT/checkpoints/last_1.ckpt
```

`every_n_epochs=10` 只控制周期性的 epoch checkpoint；`save_last=True` 不受这一间隔限制，会维护最新的 `last_{seed}.ckpt`。因此不足 10 epoch 时，不要期待 `000_*.ckpt` 或 `004_*.ckpt` 之类的周期文件。

### 重要：Exact 和 Relation 连续训练会更新同一个 `last_1.ckpt`

两组都使用 `SEED=1` 时，last checkpoint 名字相同。因此 Exact 结束后立即复制：

```bash
cp PlanT/checkpoints/last_1.ckpt PlanT/checkpoints/exact_smoke_last_1.ckpt
```

Relation 结束后复制：

```bash
cp PlanT/checkpoints/last_1.ckpt PlanT/checkpoints/relation_smoke_last_1.ckpt
```

Pilot 同理：

```bash
cp PlanT/checkpoints/last_1.ckpt PlanT/checkpoints/exact_holdout_last_1.ckpt
# Relation 训练完成后
cp PlanT/checkpoints/last_1.ckpt PlanT/checkpoints/relation_holdout_last_1.ckpt
```

否则第二次训练会让 `last_1.ckpt` 指向最新模型，第 19 节容易误用 checkpoint。

到第 10、20、30 个训练 epoch 时才会额外产生周期 checkpoint。由于 Lightning 的 epoch 从 0 开始计数，第一次周期保存对应第 10 个训练 epoch，文件名中的 epoch 通常显示为 `009`。

---

# 16. 第一阶段先做“数据分布审计”，再建立 Held-out split

如果 Exact 和 Relation 都用所有数据训练，再在同分布 benchmark 上跑，最多只能回答：

> Relation 能不能开车？

不能回答：

> Relation 是否更容易泛化？

上一版只统计 Town，然后直接选择一个 Town Holdout。这个做法工程上简单，但现在核对 PlanT 2.0 官方数据生成代码后，需要升级。

官方采集脚本在生成数据时明确使用：

```python
scenario_type = route.split("/")[-2]
save_path = f".../data/{scenario_type}"
```

随后每条 route 再保存为类似：

```text
data/
└── <ScenarioType>/
    └── TownXX_RepX_<route_id>/
        ├── boxes/
        ├── measurements/
        ├── bev_no_car_semantics/
        └── results.json.gz
```

因此每条训练 route 天然同时具有两个重要标签：

```text
Town          → 地图/道路域
ScenarioType  → 场景表面语义
```

这意味着第一轮不能只看 Town 数量。必须先统计：

```text
Scenario Type × Town × Route Count × Frame Count × Approx. Train Samples
```

再决定 holdout。

## 16.1 为什么只统计 Town 会产生混杂因素

例如：

```text
Town03: Accident 100, ParkingCutIn 80, VehicleTurning 70
Town05: Accident 100, ParkingCutIn 0,  VehicleTurning 0
```

如果直接把 Town05 全部排除：

```text
train = 其他 Town
test  = Town05
```

最后 Exact / Relation 的差异可能同时来自：

```text
地图变化 + Scenario 组成变化
```

这时不能把结果简单解释成“地图 OOD 泛化”。

因此 Town Holdout 的最低要求应该是：

> **测试 Town 中主要 Scenario Type 在训练 Town 中也有充分覆盖，避免把“地图变化”和“新场景变化”混在一起。**

## 16.2 Dataset 一次性加入 Town + Scenario 双层过滤

在 `PlanTDataset.__init__` 中找到：

```python
label_raw_path = label_raw_path_all # Could filter here if needed
```

改成：

```python
label_raw_path = label_raw_path_all

include_towns = set(self.cfg_train.get("include_towns", []))
exclude_towns = set(self.cfg_train.get("exclude_towns", []))
include_scenarios = set(self.cfg_train.get("include_scenarios", []))
exclude_scenarios = set(self.cfg_train.get("exclude_scenarios", []))


def _route_town(route_dir):
    # route_dir: .../<ScenarioType>/TownXX_RepX_routeid
    return Path(route_dir).name.split("_")[0]


def _route_scenario(route_dir):
    # 官方数据目录父目录即 scenario type
    return Path(route_dir).parent.name


if include_towns:
    label_raw_path = [
        p for p in label_raw_path
        if _route_town(p) in include_towns
    ]

if exclude_towns:
    label_raw_path = [
        p for p in label_raw_path
        if _route_town(p) not in exclude_towns
    ]

if include_scenarios:
    label_raw_path = [
        p for p in label_raw_path
        if _route_scenario(p) in include_scenarios
    ]

if exclude_scenarios:
    label_raw_path = [
        p for p in label_raw_path
        if _route_scenario(p) not in exclude_scenarios
    ]

print("Include towns:", include_towns)
print("Exclude towns:", exclude_towns)
print("Include scenarios:", include_scenarios)
print("Exclude scenarios:", exclude_scenarios)
print("Routes after split filter:", len(label_raw_path))
```

### 为什么现在就加 Scenario filter？

第一轮仍可以只用：

```text
exclude_towns=[TownXX]
exclude_scenarios=[]
```

但论文真正关键的 cross-scenario reuse 实验以后会需要：

```text
exclude_scenarios=[ParkingCutIn, ...]
```

现在一次做好，后面不用再改训练数据入口。

## 16.3 不要再使用旧的 `list_dataset_towns.py`

旧脚本只统计：

```text
磁盘上有多少个 boxes 目录
```

这存在两个问题：

1. 看不到 Scenario Type；
2. route 数不等于真正训练 sample 数。

PlanT 的 Dataset 会继续过滤失败 route，并把一条 route 展开成大量 frame-level training sample。因此新版先做完整分布审计。

创建：

```bash
nano tools/analyze_dataset_distribution.py
```

写入：

```python
import csv
import gzip
import json
import os
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(os.environ["DS"]) / "data"
CONFIG = Path("PlanT/config/model/PlanT.yaml")
OUTPUT = Path("outputs/dataset_distribution.csv")

if not ROOT.is_dir():
    raise RuntimeError(f"Dataset root not found: {ROOT}")

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

wps_len = int(cfg["waypoints"]["wps_len"])
seq_len = int(cfg["training"]["seq_len"])


def get_town(route_dir: Path) -> str:
    return route_dir.name.split("_")[0]


def get_scenario(route_dir: Path) -> str:
    return route_dir.parent.name


def usable_by_results(route_dir: Path) -> bool:
    """
    尽量镜像 PlanTDataset 中 results.json.gz 的主要过滤逻辑。
    注意：官方 Dataset 还会检查 SLURM log 中的 silent crash；
    本统计脚本不依赖作者集群日志，因此这里称 usable_by_results，
    最终实际 trainable route 数可能略少。
    """
    result_path = route_dir / "results.json.gz"
    if route_dir.name.startswith("FAILED_") or not result_path.is_file():
        return False

    try:
        with gzip.open(result_path, "rt", encoding="utf-8") as f:
            r = json.load(f)
    except Exception:
        return False

    bad_status = {
        "Failed - Agent couldn't be set up",
        "Failed",
        "Failed - Simulation crashed",
        "Failed - Agent crashed",
    }
    if r.get("status") in bad_status:
        return False

    scores = r.get("scores", {})
    score_composed = float(scores.get("score_composed", 0.0))

    infractions = r.get("infractions", {})
    min_speed = infractions.get("min_speed_infractions", [])
    num_infractions = int(r.get("num_infractions", 0))

    # 与 PlanTDataset 的主要逻辑一致：
    # 非满分 route 只有在全部 infraction 都是 min-speed 时才允许保留。
    if score_composed < 100.0 and not (num_infractions == len(min_speed)):
        return False

    return True


rows = []
boxes_dirs = sorted(ROOT.rglob("boxes"))

for boxes_dir in boxes_dirs:
    route_dir = boxes_dir.parent
    town = get_town(route_dir)
    scenario = get_scenario(route_dir)

    frame_count = len(list(boxes_dir.glob("*.json.gz")))
    usable = usable_by_results(route_dir)

    # PlanTDataset:
    # range(5, num_seq - wps_len - seq_len - 2)
    # 因此样本数约为 num_seq - wps_len - seq_len - 7。
    approx_samples = max(0, frame_count - wps_len - seq_len - 7) if usable else 0

    rows.append({
        "scenario": scenario,
        "town": town,
        "route": route_dir.name,
        "raw_route": 1,
        "usable_by_results": int(usable),
        "frames": frame_count,
        "approx_train_samples": approx_samples,
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [
        "scenario", "town", "route", "raw_route", "usable_by_results",
        "frames", "approx_train_samples"
    ])
    writer.writeheader()
    writer.writerows(rows)


def print_counter(title, counter):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    for key, value in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"{str(key):65s} {value:10d}")


raw_by_town = Counter()
usable_by_town = Counter()
raw_by_scenario = Counter()
usable_by_scenario = Counter()
samples_by_town_scenario = Counter()
routes_by_town_scenario = Counter()

for r in rows:
    raw_by_town[r["town"]] += 1
    raw_by_scenario[r["scenario"]] += 1

    if r["usable_by_results"]:
        usable_by_town[r["town"]] += 1
        usable_by_scenario[r["scenario"]] += 1
        routes_by_town_scenario[(r["town"], r["scenario"])] += 1
        samples_by_town_scenario[(r["town"], r["scenario"])] += r["approx_train_samples"]

print(f"Dataset root: {ROOT}")
print(f"Raw route folders: {len(rows)}")
print(f"CSV saved to: {OUTPUT}")
print(f"wps_len={wps_len}, seq_len={seq_len}")

print_counter("1. Raw routes by Town", raw_by_town)
print_counter("2. Usable-by-results routes by Town", usable_by_town)
print_counter("3. Raw routes by Scenario Type", raw_by_scenario)
print_counter("4. Usable-by-results routes by Scenario Type", usable_by_scenario)
print_counter("5. Usable Route Count: Town × Scenario", routes_by_town_scenario)
print_counter("6. Approx. Train Samples: Town × Scenario", samples_by_town_scenario)
```

运行：

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

python tools/analyze_dataset_distribution.py | tee outputs/dataset_distribution.txt
```

应该得到：

```text
outputs/dataset_distribution.csv
outputs/dataset_distribution.txt
```

### 这里的 `usable_by_results` 为什么不是“100% 精确 trainable”

官方 `PlanTDataset` 除 `results.json.gz` 外，还会根据作者 SLURM 日志检查某些 silent crash。公开数据在你的机器上不一定保留相同集群日志结构，因此统计脚本不能安全地复制这一条。

所以：

```text
usable_by_results = split 设计用的高质量近似统计
真正训练加载量 = 以 PlanTDataset 实际初始化日志为准
```

不要为了让统计脚本“绝对一致”去伪造作者集群日志。

## 16.4 你现在真正要看的不是一个数字，而是四张表

至少保存并检查：

```text
A. Usable routes by Town
B. Usable routes by Scenario Type
C. Town × Scenario usable route matrix
D. Town × Scenario approximate train-sample matrix
```

为什么 D 最重要？

因为模型训练面对的是 frame/sample，而不是 route 数量。

例如：

```text
Scenario A：100 routes × 100 frames ≈ 10,000 samples
Scenario B： 50 routes × 1000 frames ≈ 50,000 samples
```

Route 看起来 A 更多，但训练中 B 的权重反而大很多。

## 16.5 选择 HOLDOUT_TOWN 的新标准

不要只满足：

```text
训练数据里有 + benchmark 里有 + route 不少
```

至少同时满足：

```text
1. 该 Town 在训练数据中有足够 usable route/sample；
2. benchmark 中存在可闭环评测路线；
3. 该 Town 的主要 Scenario Type 在其他训练 Town 中也出现；
4. 不要让 holdout Town 独占大量 Scenario Type；
5. 去掉该 Town 后，剩余训练样本量仍足够；
6. Exact / Relation 必须使用完全相同 split。
```

最理想的 Town Holdout 是：

```text
地图不同
但主要交互场景类别仍然在训练数据中见过
```

这样它才更接近“地图/道路域变化”的 controlled OOD。

---

# 17. Benchmark 也要统计 Town + Scenario 组成

上一版 `list_benchmark_towns.py` 只告诉你 XML 属于哪个 Town。实际上 Longest6 XML 内部还直接包含：

```xml
<scenario type="DynamicObjectCrossing" ...>
<scenario type="SignalizedJunctionLeftTurn" ...>
...
```

因此测试路线也应该审计 Scenario composition。

创建：

```bash
nano tools/analyze_benchmark_routes.py
```

写入：

```python
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

roots = [
    Path("leaderboard/data/longest6_split"),
    Path("leaderboard/data/bench2drive_split"),
]

for root in roots:
    if not root.exists():
        continue

    print("\n" + "#" * 100)
    print("ROOT:", root)
    print("#" * 100)

    for xml_file in sorted(root.glob("*.xml")):
        try:
            tree = ET.parse(xml_file)
        except Exception as e:
            print("PARSE_FAILED", xml_file, e)
            continue

        routes = list(tree.getroot().iter("route"))
        for route in routes:
            town = route.attrib.get("town", "UNKNOWN")
            route_id = route.attrib.get("id", "UNKNOWN")

            scenario_counter = Counter()
            for scenario in route.iter("scenario"):
                stype = scenario.attrib.get("type", "UNKNOWN")
                scenario_counter[stype] += 1

            print(f"\nXML={xml_file} route_id={route_id} town={town}")
            print(f"scenario_total={sum(scenario_counter.values())}")
            for stype, n in sorted(scenario_counter.items()):
                print(f"  {stype:45s} {n}")
```

运行：

```bash
python tools/analyze_benchmark_routes.py | tee outputs/benchmark_distribution.txt
```

### 为什么这一步必要？

同一个 Town 的两条 benchmark route 也可能有不同 Scenario 组成。

因此后面 Exact / Relation 比较时，最好保存：

```text
Town
XML route
Scenario composition
```

而不是只记录 `TownXX`。

## 17.1 确定第一轮 Town Holdout

完成第16、17节统计后，再选择：

```bash
export HOLDOUT_TOWN=TownXX
```

并把选择依据写进实验日志，例如：

```text
HOLDOUT_TOWN=TownXX
reason:
- benchmark 可评测；
- 训练中样本量充足；
- 其主要 scenario 在其他 Town 有覆盖；
- 去掉后训练集规模仍足够；
- 不存在明显 scenario-exclusive confounder。
```

如果找不到满足这些条件的 Town，**不要硬做 Town Holdout**。此时可以把第一轮 OOD 改成参数扰动，Town Holdout 仅作为辅助结果。

## 17.2 现在先把 Scenario Holdout 设计预留出来，但不急着训练

官方数据已经天然带 `scenario_type`，因此后续真正针对论文核心假设的 split 可以直接写成：

```text
训练：include_scenarios = 某些场景类型
测试：holdout_scenarios = 另一些表面场景类型
```

但 Scenario Holdout 不能随便随机挑类别。

最终应该选择：

```text
物理/语义场景不同
但关系结构有可比性
```

例如后续重点寻找：

```text
纵向逼近类训练
        ↓
未见 cut-in / crossing 类测试
        ↓
检查是否存在相似：
M 较小 + M 正在恶化 + 临界时间短 + 合理动作结果相似
```

这是第二阶段，不要在第一轮 pilot 前把问题复杂化。

---

# 18. 真正的 A/B 训练

这里有两级。

## Level 1：Pilot screening

目的：先看有没有方向性信号。

Exact 和 Relation 必须：

- 同一训练数据；
- 同一数据分布审计结果；
- 同一 held-out town；
- 同一 seed；
- 同一 backbone；
- 同一 loss；
- 同一训练 epoch；
- 同一 augmentation 设置；
- 只有 representation 不同。

### Exact

```bash
cd ~/research/plant2
source env_plant2.sh
conda activate plant2

export SEED=1
export CHECKPOINT_ADDON=exact_holdout
export WANDB_MODE=offline

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
  model.training.input_representation=exact \
  "model.training.exclude_towns=[$HOLDOUT_TOWN]" \
  model.pre_training.forecastLoss_weight=0 \
  expname=exact_holdout
```

### Relation

```bash
export SEED=1
export CHECKPOINT_ADDON=relation_holdout

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
  model.training.input_representation=relation \
  "model.training.exclude_towns=[$HOLDOUT_TOWN]" \
  model.pre_training.forecastLoss_weight=0 \
  expname=relation_holdout
```

> 5 epoch 只用于筛查，不应作为论文最终结论。若 Relation 连基础驾驶都没学会，优先检查关系信息是否丢失，而不是立刻判断假设失败。

## Level 2：正式验证

如果 pilot 有信号，再恢复官方训练长度：

```text
max_epochs = 30
```

并至少使用多个随机种子，例如：

```text
SEED=1
SEED=2
SEED=3
```

最终报告 mean ± std，而不是挑一个 seed。

---

# 19. Gate 3：先测“关系表示是否还能正常驾驶”

训练后 checkpoint 位于：

```text
PlanT/checkpoints/
```

对于文档中的 1 epoch smoke 和 5 epoch pilot，应使用 `save_last=True` 产生的 last checkpoint。若已按第 15.3 节复制，推荐直接设置：

```bash
export EXACT_CKPT="$WORK_DIR/PlanT/checkpoints/exact_holdout_last_1.ckpt"
export REL_CKPT="$WORK_DIR/PlanT/checkpoints/relation_holdout_last_1.ckpt"
```

如果没有提前复制，先检查：

```bash
find PlanT/checkpoints -name '*.ckpt' -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort
```

特别注意：`PlanT/checkpoints/last_1.ckpt` 只代表 **seed=1 最近一次训练的模型**。先训 Exact 再训 Relation 且中间不复制时，它最终就是 Relation 模型，不能再拿来评 Exact。

闭环前建议核验 checkpoint 内配置：

```bash
python - "$EXACT_CKPT" "$REL_CKPT" <<'PY'
import sys, torch
for p in sys.argv[1:]:
    ckpt = torch.load(p, map_location="cpu", weights_only=False)
    cfg = ckpt["hyper_parameters"]["cfg"]
    tr = cfg["model"]["training"]
    print(p)
    print("  input_representation =", tr.get("input_representation", "exact"))
    print("  input_ego_speed      =", tr.get("input_ego_speed", False))
PY
```

预期 Exact 为 `input_representation=exact`、Relation 为 `input_representation=relation`，且两者 `input_ego_speed=True`。

## 19.1 Exact 闭环

CARLA 终端已经启动后：

```bash
export PLANT_CHECKPOINT="$EXACT_CKPT"

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes=leaderboard/data/longest6_split/longest6_00.xml \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/exact_basic.json \
  --timeout=300
```

启动日志应该输出：

```text
Input representation: exact
```

## 19.2 Relation 闭环

```bash
export PLANT_CHECKPOINT="$REL_CKPT"

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes=leaderboard/data/longest6_split/longest6_00.xml \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/relation_basic.json \
  --timeout=300
```

应该输出：

```text
Input representation: relation
```

### Gate 3 这里先回答一个很朴素的问题

```text
Relation model 是否至少能完成：
跟路、跟车、停车、基础交互，而不是完全不会开？
```

如果完全不会开，先不要谈 OOD。

---

# 20. Gate 4：第一阶段 OOD——经过分布审计的 held-out Town 闭环比较

只有完成第16、17节的 **Town × Scenario × Sample** 分布审计后，才进入 Town Holdout。

不要再使用旧的 `tools/list_benchmark_towns.py` 作为唯一依据。使用：

```text
tools/analyze_dataset_distribution.py
tools/analyze_benchmark_routes.py
```

选择属于 `$HOLDOUT_TOWN`、且 Scenario composition 已记录的 route XML。

假设某条为：

```text
/path/to/heldout_route.xml
```

Exact：

```bash
export PLANT_CHECKPOINT="$EXACT_CKPT"

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes=/path/to/heldout_route.xml \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/ood_exact_route01.json \
  --timeout=300
```

Relation：

```bash
export PLANT_CHECKPOINT="$REL_CKPT"

python leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py \
  --routes=/path/to/heldout_route.xml \
  --track=MAP \
  --agent=PlanT/PlanT_agent.py \
  --checkpoint=outputs/ood_relation_route01.json \
  --timeout=300
```

同一条 route、同一 seed 配置都跑。

---

# 21. 第一轮需要记录哪些指标

不要只看 Driving Score。

至少记录：

| 指标 | 为什么需要 |
|---|---|
| Route Completion | 是否真的到达目的地 |
| Driving Score | CARLA 综合指标 |
| Collision vehicle | 最直接安全结果 |
| Collision pedestrian | 对非车参与者安全 |
| Collision static | 是否能理解静态安全关系 |
| Red-light infraction | 规则相关能力 |
| Stop-sign infraction | 规则相关能力 |
| Off-road / route deviation | 关系压缩是否损害道路驾驶 |
| Minimum-speed / blocked | 是否因过度保守而停住 |

特别关注两种失败：

```text
A. Relation 更安全，但完全不走
→ 只是变保守，不是“更会开车”

B. Relation completion 高，但 collision 高
→ 关系状态不足以支撑安全决策
```

因此最终应该同时看：

```text
Safety + Progress
```

而不是单项指标。

---

# 22. 第一轮结果怎么解释，避免错误结论

## 情况 A：ID 接近，OOD Relation 明显更好

这是最理想信号：

```text
ID:
Exact ≈ Relation

OOD:
Relation > Exact
```

它支持继续研究：

> 在不明显损失常规驾驶能力的情况下，驾驶关系抽象可能提供了更稳定的迁移表示。

这时下一步值得投入：

1. 改善 relation 定义；
2. 加真正动态安全包络；
3. 加 uncertainty；
4. 做 cross-scenario holdout；
5. 研究 Action Effect。

## 情况 B：Relation ID 和 OOD 都明显差

不能马上宣布假设失败。

优先检查：

1. 是否丢了 planner 真正需要的横向空间信息；
2. bounding-circle proxy 是否太粗；
3. constant-velocity 是否把路口/cut-in 关系描述错；
4. object type 是否应该保留；
5. relation 是否需要额外加入 lane/occupancy relation；
6. 训练过程是否收敛。

如果换几种合理 relation 后仍然没有信号，才需要怀疑研究假设。

## 情况 C：Exact 和 Relation 全部差

这主要是训练/工程问题，不是研究结论。

先恢复官方 PlanT 2.0 配置检查训练 pipeline。

## 情况 D：Relation ID 更好，但 OOD 没优势

说明关系可能只是一个更好的 feature engineering，而没有证明“可复用性”。

此时论文主张不能写“提高泛化”，必须继续做更严格 cross-scenario / relation-preserving OOD。

---

# 23. 为什么 Town Holdout 仍只是一阶段：Scenario Holdout 才更接近论文核心

你的核心假设不是：

> 换一个地图也能开。

而是：

> **物理场景高度不同，但背后的驾驶关系相似时，关系层能否复用驾驶经验。**

因此 Town Holdout 主要回答：

```text
地图/道路域发生变化时，Relation 是否比 Exact 更稳定？
```

它有价值，但不是最终证据。

现在已经确认 PlanT2 数据本身按 `ScenarioType/TownRoute` 保存，所以第二阶段可以直接利用现有 Scenario Type 做更严格的 **cross-scenario relation reuse**，不一定从零重采全部数据。

例如：

```text
训练：纵向跟车/逼近类 Scenario
测试：ParkingCutIn / DynamicObjectCrossing / 其他未见 Scenario
```

关键不是 Scenario 名字本身，而是后续要证明：

```text
X_train != X_test
但
R_train ≈ R_test
```

并检查模型能否复用类似行为规律。

例如若不同 Scenario 都出现：

```text
安全余量较小
余量正在恶化
临界时间较短
减速能改善关系
```

则测试 Relation policy 是否比 Exact policy 更容易产生相似、合理的处理。

第二阶段需要：

- 先根据第16节统计找到样本量足够的 Scenario；
- 明确 train/holdout scenario split；
- 检查 holdout scenario 是否在 Town、速度、参与者类型等变量上产生额外严重混杂；
- 必要时再用 ScenarioRunner / carla_garage expert 补充受控数据，而不是一开始就重采整个数据集。

所以第一轮仍然先完成：

```text
Town controlled OOD + 参数 OOD
```

如果出现方向性信号，再进入 Scenario Holdout。

---

# 24. 第二个非常便宜的 OOD：参数扰动，不需要重新定义新场景

Town Holdout 之后，建议再做一个参数 OOD：

```text
训练：普通速度、普通轿车尺寸
测试：更高速度 / 更大车辆 / 更小间距
```

这里最符合你从“人类驾驶大概感知”得到的启发：

虽然精确数值变化很大，但是：

```text
“距离偏紧 + 正在接近 + 很快到临界状态”
```

这类关系可以保持相似。

实现方式可以先通过修改 ScenarioRunner route/scenario 参数完成，后面再专门编写参数化场景生成器。

第一版不要同时改 weather、friction、agent type、route、speed 五个维度，否则无法判断改进来自哪里。

---

# 25. 这个实验当前到底验证什么，不能验证什么

## 可以初步验证

### H1：关系表征是否具有决策充分性的迹象

```text
关系输入是否至少还能开车？
```

### H2：关系表示是否更稳定

```text
同一关系结构在精确参数变化后，模型行为是否更稳定？
```

### H3：OOD 泛化是否出现方向性优势

```text
Held-out Town / 参数变化下，Relation 是否比 Exact 更稳？
```

## 现在还不能证明

### 1. “人类真的就是这么表示驾驶关系”

不是本实验目标。

人类驾驶只是启发来源。

### 2. “这几个 relation 就是最终最小充分关系”

第一版只是代理表示。

### 3. “端到端模型 OOD 失败是因为使用精确状态”

不要这么写。

我们当前没有这个因果结论。

### 4. “关系表示一定提高 OOD”

这是待验证 hypothesis，不是前提。

---

# 26. 为什么这一套实验和你的论文中心思想是对应的

你的中心问题可以分为三层：

```text
第一层：存在性
复杂物理场景中是否真的存在可复用驾驶关系？

第二层：充分性
只依赖这些关系，能否仍然做出合理驾驶决策？

第三层：迁移性
当精确物理状态变化，但关键关系相似时，行为经验能否复用？
```

本方案中的实验对应：

```text
PlanT Exact Token
        vs
PlanT Relation Token
```

其真正价值不在于“改了 6 个 feature”，而在于建立一个受控实验：

```text
同一 planner
同一训练数据
同一 route 信息
同一道路 BEV
同一控制器
同一 loss
同一训练 schedule

唯一主要差异：
模型是在 exact object state 上学习，还是在 driving relation 上学习。
```

如果 Relation 在未见条件下持续出现优势，才值得把研究继续扩展为：

```text
Precise Physical State
        ↓
Dynamic Safety Envelope / Reliable Physical Bridge
        ↓
Low-dimensional Driving Relations
        ↓
Action-conditioned Relation Dynamics
        ↓
Planning
```

---

# 27. 后续真正论文版应该怎样升级

只有快速验证出现正向信号后，再按下面顺序继续：

## Phase 2.1：把 bounding circle 代理换成正式时空安全包络

复用成熟方法：

- 几何占用；
- motion prediction；
- uncertainty；
- probabilistic occupancy；
- signed distance / reachable set。

包络是“桥梁”，不是论文主要创新。

## Phase 2.2：从连续 relation 进一步验证“低维性”

做 relation ablation：

```text
6 relations
5 relations
4 relations
3 relations
```

寻找：

> 在不明显损失驾驶能力的情况下，到底最少需要哪些关系？

这才真正支撑“low-dimensional”而不是只支撑“different feature representation”。

## Phase 2.3：真正的 cross-scenario holdout

例如：

```text
train: following / longitudinal conflict
OOD: cut-in / intersection / cyclist crossing
```

并刻意构造：

```text
X_train != X_test
但 R_train ≈ R_test
```

这是最关键的论文证据。

## Phase 2.4：Action Effect

最终从：

```text
R → trajectory
```

升级为：

```text
(R_t, candidate action a)
        ↓
R_future(a)
        ↓
关系改善 / 恶化
```

验证：

> 动作—后果规律是否比完整场景—动作映射更容易跨场景复用？

---

# 28. 建议的实验表格提前固定

以后每次实验都填，不要只保存一堆 JSON。

```text
experiment_id
upstream_commit
carla_version
representation
relation_version
train_towns
holdout_town
train_scenarios
holdout_scenarios
scenario_split
dataset_distribution_csv
benchmark_distribution_file
seed
max_epochs
checkpoint
route
route_completion
driving_score
collision_vehicle
collision_pedestrian
collision_static
red_light
stop_sign
route_deviation
blocked
notes
```

可以先用 CSV：

```text
results/experiment_log.csv
```

每次训练的完整 Hydra config 和 git commit 一起保存。

训练前：

```bash
git rev-parse HEAD > outputs/current_git_commit.txt
conda env export > outputs/conda_environment_full.yml
```

---

# 29. 推荐目录结构

最终保持：

```text
~/research/plant2/
├── carla/                         # 官方 PlanT2 对应 CARLA 0.9.15
├── checkpoints/
│   └── PlanT2/
├── data/
│   ├── PlanT2_Dataset/
│   └── PlanT2_DS/
├── PlanT/
│   ├── relation_features.py       # 我们新增
│   ├── dataset.py                 # 最小修改
│   ├── PlanT_agent.py             # 最小修改
│   └── ...
├── tests/
│   └── test_relation_features.py
├── tools/
│   ├── list_dataset_towns.py
│   └── list_benchmark_towns.py
├── outputs/
│   ├── smoke/
│   ├── exact/
│   └── relation/
├── results/
│   └── experiment_log.csv
└── env_plant2.sh
```

你现有的 CARLA 0.9.16 保留在原位置，与这里完全隔离。

---

# 30. 最推荐的实际执行顺序

如果你明天开始做，不要看完整文档后一口气全敲。

严格按下面 checklist：

## Step A：环境复现

- [ ] Linux / NVIDIA GPU 检查
- [ ] clone PlanT2
- [ ] checkout 固定 commit
- [ ] 安装独立 CARLA 0.9.15
- [ ] `conda env create -f environment.yml`
- [ ] CARLA Python client 能连接
- [ ] 下载原始 checkpoint
- [ ] 原始 PlanT2 跑通一条 `longest6_00.xml`

**A 不通过，不进入 B。**

## Step B：关系模块只做离线检查

- [ ] 创建 `relation_features.py`
- [ ] 3 个 unit tests 通过
- [ ] 配置加入 `input_representation`
- [ ] Dataset 最后一步 relationize
- [ ] Agent 同样 relationize

## Step C：训练 smoke

- [ ] Exact 1 epoch / 5 batch 无报错
- [ ] Relation 1 epoch / 5 batch 无报错
- [ ] 检查 checkpoint 中 representation 配置正确

可以检查：

```bash
python - /path/to/checkpoint.ckpt <<'PY'
import torch
import sys
ckpt = torch.load(sys.argv[1], map_location='cpu', weights_only=False)
print(ckpt['hyper_parameters']['cfg']['model']['training'].get('input_representation'))
PY
```

若你的 shell 不支持上面的参数方式，可写成一个单独脚本。

## Step D：数据审计 + Pilot

- [ ] 运行 `tools/analyze_dataset_distribution.py`
- [ ] 保存 Scenario × Town × usable route × sample 统计
- [ ] 运行 `tools/analyze_benchmark_routes.py`
- [ ] 检查候选 held-out Town 是否存在 Scenario composition 混杂
- [ ] 只有通过分布审计后才确定 `HOLDOUT_TOWN`
- [ ] Exact 训练
- [ ] Relation 训练
- [ ] 基础路线闭环
- [ ] held-out 路线闭环
- [ ] 每条测试 route 同时记录 Town + Scenario composition
- [ ] 记录 collision + completion，而不是只看一个 score

## Step E：判断是否继续

只有出现以下至少一种信号才继续投入复杂包络：

```text
1. Relation ID 性能接近 Exact，但 OOD 更好；
2. Relation 在较少数据下达到接近 Exact 的驾驶能力；
3. Relation 对速度/尺寸/距离扰动明显更稳定；
4. 不同场景能够在 relation space 映射到相似状态，并产生相似合理行为。
```

---

# 31. 常见报错与排查优先级

## 31.1 CARLA client version mismatch

表现：

```text
RPC / serializer / API mismatch
```

检查：

```bash
which python
python -c "import carla; print(carla.__file__)"
echo $CARLA_ROOT
```

必须保证：

```text
Simulator: CARLA 0.9.15
Python environment: carla==0.9.15
```

不要让系统里原来 0.9.16 的 Python API 抢到 `PYTHONPATH` 前面。

## 31.2 `No module named srunner`

检查：

```bash
echo $SCENARIO_RUNNER_ROOT
echo $PYTHONPATH
ls scenario_runner_autopilot
```

重新：

```bash
source env_plant2.sh
```

## 31.3 `No module named leaderboard`

同理检查：

```bash
echo $LEADERBOARD_ROOT
ls leaderboard_autopilot
```

## 31.4 `car_data.npy` 硬编码路径错误

确认训练命令包含：

```text
model.training.augment_parked=false
```

## 31.5 Relation 训练时出现 augmentation shape / 数值异常

确认：

```text
model.training.augment=false
```

## 31.6 `DS_LOCAL` / diskcache 报错

第一轮统一：

```text
use_caching=false
```

不用 `DS_LOCAL`。

## 31.7 Relation checkpoint 在线仍显示 exact

检查 checkpoint：

```python
ckpt['hyper_parameters']['cfg']['model']['training']['input_representation']
```

以及 `PlanT_agent.py` 是否真的从 checkpoint cfg 读取。

## 31.8 Relation 模型一动不动

先不要立刻判断假设失败。

检查：

1. relation features 是否全部接近常数；
2. `current_clearance / DIST_SCALE` 是否过度压缩；
3. `closing` 符号是否正确；
4. bearing 是否符合 CARLA ego frame；
5. 是否所有 object 都被过滤掉；
6. target waypoint loss 是否下降；
7. exact 同配置训练是否也不动。

建议随机打印 10 个 sample：

```python
print(sample["input"][:10])
```

确认它们不是全 0 / NaN / inf。

---

# 32. 当前 proxy relation 的已知局限——论文里以后必须替换或解释

第一版有意简单，因此有明确局限：

## 1. bounding circle 过于保守

它没有考虑车辆矩形朝向。

## 2. constant velocity 不是行为预测

它只能表达短时运动趋势，不能正确描述：

- 主动 cut-in；
- 路口转弯；
- 行人突然改变方向。

## 3. 没有 prediction uncertainty

第一轮不使用 SURE-Plan 类方法。

## 4. 没有道路—对象统一安全包络

道路 BEV 仍然独立保留。

## 5. 这一版还不是“全场景固定低维向量”

当前仍然是“一对象一个 relation token”，对象数量增加时 token 数量仍会增加。因此它验证的是：

```text
object-specific exact attributes
        ↓
object-centric reusable relations
```

而不是已经证明：

```text
任意复杂场景 → 一个固定 3~5 维向量
```

如果第一轮结果正向，后续再研究 relevant-object selection / top-k relation / spatial-sector aggregation 等方式进一步形成真正紧凑的全局关系瓶颈。

## 6. 还没有真正 Action-Conditioned

当前：

```text
Scene → Relation → Planning
```

最终目标：

```text
(Scene → Relation, candidate action)
              ↓
       Future Relation
```

所以第一轮的任务不是“完成论文”，而是：

> **判断 Relational Bottleneck / Relational Abstraction 这个中心假设是否值得做成完整论文。**

---

# 33. 为什么这一方案不会偏离你的研究起点

你的研究起点来自人类驾驶启发，而不是预先断言现有端到端模型“因为精确模式而失败”。

正确逻辑应一直保持：

```text
观察：
人类无法获得机器式的全部精确物理信息，
但能够把有限驾驶经验迁移到大量不同场景。

        ↓

启发性假设：
支撑驾驶行为的关键关系结构，
可能远低于完整物理状态的复杂度，且能够复用。

        ↓

实验问题：
如果用统一 planner，
只改变 Exact State 与 Driving Relation representation，
Relation 是否仍具有决策充分性，且在未见条件下更稳定？

        ↓

若成立：
再研究如何从真实复杂场景可靠产生这些关系，
以及 Action Effect 如何在关系空间传播。
```

不要倒过来写成：

```text
端到端 OOD 失败
= 因为模型依赖精确状态
```

这一点目前没有证据，也不是你的原始出发点。

---

# 34. 论文角度：第一轮实验成功以后最有价值的证据链

最终论文应争取形成：

## Evidence 1：关系存在

```text
不同精确物理场景
        ↓
可以映射到相似 Driving Relation
```

## Evidence 2：关系近似充分

```text
删除大量 exact scene attributes 后
模型仍然能够完成正常驾驶
```

## Evidence 3：关系可复用

```text
train scene A
         ↓
relation pattern R
         ↓
test unseen scene B 也出现 R
         ↓
模型能够迁移行为规律
```

## Evidence 4：关系维度可以继续压缩

通过 feature ablation 找到：

```text
真正必要的关系项
```

## Evidence 5：精确物理层仍负责 hard safety verification

后续把成熟动态安全包络/概率占用/SDF 等作为桥梁和安全验证层，而不是和低维关系创新抢主线。

---

# 35. 核实来源

本方案工程部分是根据以下当前公开代码/资料逐项核对后形成的：

1. **PlanT 2.0 官方仓库**  
   https://github.com/autonomousvision/plant2

2. **本方案固定的 PlanT 2.0 commit**  
   `6269e5a43c6f6b984d2bd97e3ec4a025ebefbeef`

3. **PlanT 2.0 官方模型**  
   https://huggingface.co/SimonGer/PlanT2

4. **PlanT 2.0 官方数据集**  
   https://huggingface.co/datasets/SimonGer/PlanT2_Dataset

5. **CARLA 官方 releases**  
   https://github.com/carla-simulator/carla/releases

6. 当前代码中已核对的重要事实：

```text
PlanT/setup_carla.sh        → 下载 CARLA 0.9.15
PlanT/environment.yml       → carla==0.9.15, Python 3.10, torch 2.6.0
PlanT/dataset.py            → object = type + x/y/yaw/speed/width/length
PlanT/model.py              → num_attributes = 6
PlanT/PlanT_agent.py        → 在线同样从 CARLA GT boxes 生成 6 属性 object token
collect_dataset_slurm.py       → 数据按 data/<scenario_type>/<Town...route>/ 组织
leaderboard route XML          → route 内含显式 <scenario type=...> 场景组成
carla_garage/.../chauffeurnet.py
                            → 当前 BEV 只保留 road/sidewalk/lane 类道路语义，动态 actor 绘制逻辑被注释
```

---

# 36. 最终建议

你现在最不应该做的是：

```text
先花很长时间完善动态安全包络
→ 再设计不确定性
→ 再设计 world model
→ 再改 VAD
→ 最后才发现 relation hypothesis 没有明显作用
```

最应该做的是：

```text
原 PlanT2 跑通
        ↓
Exact / Relation 只换 representation
        ↓
Town / 参数 OOD 做第一次证伪
        ↓
看有没有稳定信号
```

如果有：

```text
再把 proxy relation 换成正式动态安全包络输出
再做 cross-scenario relation reuse
再做 Action-Conditioned Relation Dynamics
```

这样每一步都有明确科学问题，也最大限度避免把时间花在并非核心创新的工程模块上。

