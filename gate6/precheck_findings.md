# Gate 6 · 执行前四项核查记录（Pre-check Findings）

> 日期：2026-09-03 · 只读核查，未改动任何代码/配置
> 对应问题：① Town12/13 真实场景资源 ② PlanT forward 完整输入 ③ BEV 内容 ④ Object token 坐标/速度定义
> 结论速览：
> - 真实可用动态场景 46 种（~6000 实例，Town12/13 为主）；文档假设的 FollowLeadingVehicle/NoSignalJunctionCrossing/纯 CutIn 在 benchmark 路线中 **0 实例**，需按真实类型重映射。
> - Replay 需保存 forward 全部输入：`x_objs`(含顺序) + `route_original` + `speed_limit` + `BEV`；模型 **stateless**（无跨帧 hidden/cache）。
> - BEV **仅静态地图 5 类**（无 vehicle/pedestrian/dynamic）→ 离线只改 actor token 做干预合法。
> - Token 坐标=ego 局部(m，x 前向 y 左)，yaw=相对 ego 航向(存 token 为度)，speed=km/h(前向, 可为负)，width/length=m。

---

## 1. Town12 / Town13 真实场景资源

统计范围（`leaderboard/data` 单一镜像，避免与 scenario_runner_* 镜像重复计数）：
`routes_training.xml` + `routes_validation_split/*.xml` + `bench2drive_split/*.xml`

46 种 scenario type、合计约 6000 实例，绝大多数在 Town12/Town13（本机 CARLA build 含 Town11/12/13/15，可运行）。

### 动态交互场景统计表（实例 ≥ 5，含 Town12/Town13 与其他 town）

| scenario_type | 实例 | 涉及route数 | Town12 | Town13 | 其他town |
|---|---:|---:|---:|---:|---:|
| HardBreakRoute（前车急刹，≈跟车类） | 766 | 115 | 573 | 189 | 4 |
| ControlLoss | 688 | 112 | 429 | 255 | 4 |
| DynamicObjectCrossing（动态横穿） | 470 | 89 | 352 | 114 | 4 |
| PriorityAtJunction | 263 | 56 | 237 | 26 | 0 |
| NonSignalizedJunctionRightTurn | 251 | 91 | 128 | 123 | 0 |
| ParkedObstacleTwoWays | 247 | 85 | 206 | 39 | 2 |
| BlockedIntersection | 246 | 100 | 156 | 88 | 2 |
| HazardAtSideLaneTwoWays | 222 | 83 | 177 | 41 | 4 |
| AccidentTwoWays | 217 | 72 | 158 | 57 | 2 |
| InvadingTurn | 212 | 55 | 119 | 93 | 0 |
| ParkingCrossingPedestrian | 207 | 46 | 127 | 78 | 2 |
| VehicleTurningRoute（对向/横穿车） | 187 | 76 | 116 | 71 | 0 |
| ParkingCutIn | 181 | 45 | 118 | 62 | 1 |
| StaticCutIn | 166 | 47 | 119 | 44 | 3 |
| PedestrianCrossing | 158 | 51 | 94 | 60 | 4 |
| NonSignalizedJunctionLeftTurn | 151 | 41 | 76 | 74 | 1 |
| VehicleTurningRoutePedestrian | 142 | 57 | 84 | 58 | 0 |
| OppositeVehicleTakingPriority | 110 | 45 | 79 | 31 | 0 |
| CrossingBicycleFlow | 47 | 26 | **47** | **0** | 0 |
| HighwayCutIn | 41 | 23 | 34 | 7 | 0 |
| 其余（ParkingExit/HazardAtSideLane/EnterActorFlow/V2/Interurban*/Merger*/SequentialLaneChange/各 Vanilla 等） | 5~55 | ≤55 | — | — | — |

> 完整 46 类明细已列出主要项；`SequentialLaneChange`(5)、`Vanilla*`(各5) 等小类仅 bench2drive 有。

### 与 Gate6 方案假设的差异（需按规则替换）
| Gate6 方案组 | 文档点名 class | benchmark 实例 | 建议替代（真实存在且充足） |
|---|---|---|---|
| A. Following | FollowLeadingVehicle | **0**（仅 srunner/examples） | **HardBreakRoute**（766，前车急刹） |
| B. Cut-in | CutIn / HighwayCutIn | 0 / 41 | **StaticCutIn**(166) 或 **ParkingCutIn**(181) 或 HighwayCutIn(41，仅 T12 为主) |
| C. Crossing Vehicle | NoSignalJunctionCrossing | **0** | **VehicleTurningRoute**(187) / VehicleTurningRoutePedestrian(142) / **DynamicObjectCrossing**(470) |
| D. Pedestrian/Cyclist | PedestrianCrossing / CrossBicycleFlow | 158 / 47 | PedestrianCrossing(158，T12/T13均衡) 或 CrossingBicycleFlow(47，**仅 Town12**) 或 ParkingCrossingPedestrian(207) |

- 每组 ≥5 独立 instance：全部满足（最少候选 41~47）。
- Gate5 所用的 `longest6_split`（Town05）**不含任何交互场景** → Gate6 需改跑 `routes_training`/`routes_validation_split`/`bench2drive_split`。

---

## 2. PlanT forward 的完整输入（官方模型）

`PlanT/model.py` `HFLM.forward(batch)`（model.py:202）实际读取的 batch 字段：

| key | 内容 | 用途/锚点 |
|---|---|---|
| `x_objs` | 全样本拼接的 object token 矩阵，index 0 = padding 行 `[0,0,0,0,0,0,0]`；每行 `[type,x,y,yaw_deg,speed_kmh,width,length]`（7 列） | 按 type 用 `tok_emb[type]`(Linear(6→n_embd)) 嵌入，model.py:211 |
| `idxs` | 把展平 token 挑回各样本的索引（padding 技巧）；batch=1 时等价于 `arange(n_objs+1)[1:]` | model.py:213, `generate_batch`(dataset.py:667-703) |
| `route_original` | top-20 局部路点 (20×2) → flatten 40 → `route_emb` | model.py:216 |
| `speed_limit` | 类别索引 int (0~3) → `speed_emb` | model.py:220 |
| `BEV` | RGB 张量；**仅当 input_bev=True（官方=是）** → resnet18 → 1 token | model.py:233-236 |
| `input_ego_speed` | **仅当 cfg True（官方=False，不消费）** | model.py:227-231 |
| `y_objs` | 推理 None（无 forecasting loss） | model.py:252 |

前置查询 token 顺序（BERT positional embedding → **顺序敏感，必须原样保存**）：
`wp_token×28 (wps8+path20)` → `[BEV token]` → `route` → `speed_limit` → `objects`
（model.py:216-241；`use_dropout=True` 但 `eval()` 下关闭）

**Mask / 长度信息：无**（无 attention mask、无显式 seq 长度参数；padding 用 idxs 处理）。
**跨帧 hidden / cache / memory：无**。`run_step` @torch.no_grad（PlanT_agent.py:196），每帧重建 batch；transformer 无 KV cache；`SingleGRUWaypoints` 每帧从 `x=0` 自回归解码（model.py:304-319）；agent 侧持久状态只有 controller/`cleared_stop_sign`/walker 集等（不进网络）。

### 对 Step 6.3 Replay 的结论
离线 replay 需逐位复现（每快照保存）：
1. `x_objs` 行（**含 token 顺序**，7 列浮点原样）
2. `route_original`（top-20 局部点）
3. `speed_limit`（int 类别）
4. `BEV`（送 resnet 前的 RGB 张量）
漏任一 → 误差无法到 0。Gate6 方案 §11 NPZ 清单需补 BEV 与 speed_limit。

---

## 3. BEV 具体内容 → 仅静态地图层

渲染器：`carla_garage/birds_eye_view/chauffeurnet.py` `ObsManager.get_observation()`（chauffeurnet.py:158）。
- **车辆/行人/红绿灯/停车牌绘制全部被注释**（L174-227、L215-280 均注释），`_history_queue`/mask 相关函数未启用。
- 实际输出的 `bev_semantic_classes` 类号（L270-280）：
  ```
  0 = 背景/unlabeled
  1 = road
  2 = sidewalk
  3 = lane_marking_all
  4 = lane_marking_white_broken
  ```
- 无 dynamic occupancy、无 ego 本身。

在线管道（PlanT_agent.py:188-192）：`bev_colors[类别图]` 染 RGB → `rot90` → crop `[64:-64,64:-64]` → `permute(2,0,1)` 得 `(3,H,W)`。数据集侧使用同名 `bev_no_car_semantics`（不含车）。

### 结论
BEV 只含道路/标线地图信息，与所有 actor 无关（只随 ego 位姿 warp）。**离线仅改 actor token、BEV 保持不变即可复现干预** → 干预机制合法、无需处理 BEV。

---

## 4. Object token 坐标与速度定义

### 行格式（恒定 7 列）
`[type, x, y, yaw_deg, speed_kmh, width_m, length_m]`
- type 编号（`PlanT/plant_variables.py`）：`car=1, walker=2, static=3, stop_sign=4, traffic_light=5, emergency=6`；`static_car→1`；model 注释 0=padding（共 7 类）
- 在线构造：`PlanT_agent.get_input_batch`（PlanT_agent.py:553-578）；训练构造：`dataset.py:386-414`（行序 car/walker/emergency 前、static/stop/light 后）

### 各字段定义
| 字段 | 定义 | 锚点 |
|---|---|---|
| x/y | **Ego 局部坐标（m）**；`x`=前向（前方为正），`y`=左向（CARLA 左前上系）。`rel = R_ego^T·(p_actor−p_ego)` | `carla_garage/transfuser_utils.py:163` `get_relative_transform`；调用 `carla_garage/data_agent.py:489` |
| yaw | **相对 ego 航向**；源为 radians（`normalize_angle(actor_yaw−ego_yaw)`，data_agent.py:488），token 中经 `rad2deg` 存**度** | 在线 `PlanT_agent.py:558`；训练 `dataset.py:391` |
| speed | **前向速度 km/h**；源 `_get_forward_speed()`（m/s 前向 = v·heading，可负，如倒车），token 中 `×3.6` | `carla_garage/data_agent.py:806`；`PlanT_agent.py:559`、`dataset.py:392` |
| width/length | CARLA bbox extent（半尺寸）×2，单位 m（width=`extent[1]*2(+door)`，length=`extent[0]*2`） | `PlanT_agent.py:560-561`、`dataset.py:393-394` |

### world actor → token 链
```
DataAgent.get_bounding_boxes()          carla_garage/data_agent.py:429
  ├─ 每 actor: position=局部m, yaw=相对rad, speed=前向m/s, extent, type_id, id
  └─ 含 ego（index 0，position≈0）
PlanTAgent.run_step                      PlanT_agent.py:196
  ├─ label_raw=self.get_bounding_boxes()
  ├─ 过滤 too-far（range 椭圆），append 最近红绿灯/停车牌
  └─ self._get_control → get_input_batch
PlanTAgent.get_input_batch               PlanT_agent.py:505
  ├─ 归一化 class（警车→emergency、静止walker→irrelevant 等）
  ├─ 行构造: type_nums[class], pos, rad2deg(yaw), speed*3.6, extent*2
  └─ (relation/NoStop/干预 均作用于成型后的行)
```

### 对 Gate6 干预（I1~I5）的含义
- 快照只有**标量 speed**，无 velocity vector → I1/I2 的"沿运动方向"实际只能用 **yaw** 推算：`u=[cos(yaw_rad), sin(yaw_rad)]`（yaw 的符号/轴约定建议在实现时用真实帧做一次 sanity，例如正前方前车 yaw≈0、应沿 +x 前移）。
- I3/I4 改 speed_kmh 列；注意 0 速对象（静止/起步）×1.2/0.8 无效，需在筛选阶段留意。
- I1/I2 改 x/y 列（在 ego 局部系内移动该 actor）；不改其它任何字段 → 合法。

---

## 5. 开放/待定项（供 Step 6.0 决策）
1. 四组场景**按真实类型重映射**（§1 表），需用户确认最终 4 个 class。
2. 路线来源确认用 `leaderboard/data/routes_training.xml` + `routes_validation_split/*.xml` + `bench2drive_split/*.xml`（Town12/13 为主），先做 1~2 条 smoke 验证 scenario 触发率与耗时。
3. 快照格式建议在实现时同时保存：snapshot `.npz`（x_objs、route_original、speed_limit、BEV、online 输出 pred_path/pred_wps）+ `.json` 元数据（frame/scenario/ego/actor 映射/顺序），保证 replay 一致。

## 附：主要代码锚点
- scenario 定义：`scenario_runner_autopilot/srunner/scenarios/*.py`（类名与 XML type 一致才可被加载）
- scenario 运行：`leaderboard_autopilot/leaderboard/leaderboard_evaluator_local.py`（RouteScenario + scenario_manager_local）
- route/scenario 数据：`leaderboard/data/{routes_training.xml, routes_validation_split/*, bench2drive_split/*, longest6_split/*}`
- 模型：`PlanT/model.py`（forward 202、输入 203-241）
- 数据/在线：`PlanT/dataset.py`（generate_batch 667、行构造 386-414）、`PlanT/PlanT_agent.py`（tick 173、get_input_batch 505）
- actor 采集：`carla_garage/data_agent.py:429 get_bounding_boxes`、`806 _get_forward_speed`
- 坐标工具：`carla_garage/transfuser_utils.py:163 get_relative_transform`
- BEV：`carla_garage/birds_eye_view/chauffeurnet.py:158 get_observation`
