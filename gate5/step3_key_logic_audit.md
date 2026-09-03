# Gate 5 · Step 3 记录：关键逻辑逐项资格审查

> 日期：2026-09-03 · 对应文档 §3.1-§3.5
> 说明：§3.1/§3.2(代码)/§3.3 为纯代码审计，本文件给出结论；§3.2 的运行日志 + §3.4/§3.5 需官方 reference 实际运行（见 `gate5/step4_smoke_results.md`，由 Step 4 smoke 产出）。

---

## §3.1 input_ego_speed

### 事实表
| 端 | 官方（epoch=029 全量 30ep） | 研究 holdout（exact/relation，5ep, Town05 excl） | 研究 nostop（同上 + NoStop） |
|---|---|---|---|
| Dataset 是否产生 `input_ego_speed` | **否**（官方 base dataset.py 仅 `sample["ego_speed"]`） | **是**（L1 patch：`sample["input_ego_speed"]=sample["ego_speed"]`） | 是（同） |
| 训练 cfg `input_ego_speed`（ckpt cfg 实测） | **False** | **True** | **True** |
| model.py 是否消费（仅当 cfg True） | 否 | 是 | 是 |
| 在线 agent 是否提供该 key | 提供（`sample["input_ego_speed"]=input_data["speed"]`，L1）但**模型不消费** | 提供且消费 | 提供且消费 |
| 数值语义 | —（未用） | 自车速度 m/s（数据集 measurement `speed` 实测 max≈20.4≈73km/h → m/s；在线 `sensor.speedometer` 亦 m/s） | 同 |

> 实测：研究 4 个 ckpt cfg = `{'input_ego_speed': True}`；官方 ckpt cfg = `False`；数据集/在线两端均为 m/s，量纲一致。

### PASS/FAIL
- 训练/在线语义一致：✅（两端 key 含义均为"自车当前速度 m/s"）
- 官方线：训练 False + 在线提供 key 但不消费 → 一致 ✅
- 研究线：训练 True + 在线消费（cfg 驱动）→ 一致 ✅
- ckpt cfg 与运行一致：✅（4 个研究 ckpt 均存 True；官方存 False）
- **FAIL 条件均未触发**（无 train True/online False 之类错配；`input_ego_speed` 是 dataset 正式 alias，不是"临时硬补"）→ **§3.1 = PASS**

---

## §3.2 Stop-sign lifecycle（代码部分）

状态机见 `gate5/stop_sign_state_machine.md`。要点：
- type=4 生成条件、cleared 置位/复位、token 消失逻辑为**官方原代码**，我方 patch 未改动（仅新增只读 deadlock detector）。
- 清除常量 clearing=3.0m / unclearing=10m（carla_garage/config.py）。
- 运行日志（官方 reference route25/28 JSONL）见状态机文档"运行日志"节：8/8 与 4/4 次停车牌交互 token 全部消失；观测到多次"原地 cleared"与"长停后驶过"；最长静止 ~30s 后均自行恢复；两条 route 均 100% 完成 → **状态机无永久 deadlock**。

### §3.2 判定 = **PASS**
- type4 不会永久存在 ✅
- 完成停车后能进入 clear 状态 ✅
- 车辆能够正常恢复前进 ✅
- 状态机不会形成永久 deadlock ✅

---

## §3.3 Planner input token 一致性（训练端 vs 在线端）

type 编号（plant_variables.class_nums，两端共用同一实例）：`car=1, walker=2, static=3, stop_sign=4, traffic_light=5, emergency=6`；`static_car→1`（并入 type 1，第二段 0 速行）。

### 逐字段对比（exact 表示）
| 字段 | 训练端（dataset.py 386-414） | 在线端（PlanT_agent.py 553-578） | 一致 |
|---|---|---|---|
| 行结构 | `[type,x,y,yaw_deg,speed_kmh,width,length,id]`→后删 id | `[type,x,y,yaw_deg,speed_kmh,width,length]` | ✅ |
| type 索引 | `type_nums[class]` | 同 | ✅ |
| 位置 | 局部坐标 x/y（前/左） | 同（relative transform） | ✅ |
| yaw | rad2deg（deg） | 同 | ✅ |
| speed | m/s→km/h（×3.6），car/walker/emergency 用实际，其余 0 | 同 | ✅ |
| width/length | `extent[1]*2(+door)`/`extent[0]*2` | 同式 | ✅ |
| class 归一化 | 警车/消防/救护→`emergency`（dataset 359-363） | 同（agent 527-531） | ✅ |
| walker 未动过滤 | —（训练集标签自含） | 在线按 speed/id 过滤静止 walker | ✅（在线特有逻辑，base 原有） |
| static / static_car | static 保留（type3）；`input_static_cars=False` 时 pop static_car | longest6 pop static（type3）；`input_static_cars=False` pop static_car | ✅（cfg 一致） |
| traffic_light | Red/Yellow **且 affects_ego** | Red/Yellow（依赖 run_step 选中的 next light，≤30m） | ≈（base 固有近似：affects_ego≈next-<30） |
| stop_sign | **且 affects_ego** | next_stop<30 且 **not cleared**（生命周期标志） | ✅（正是 §3.2 生命周期） |
| relation 变换 | `relationize_exact_row`（cfg=relation 时） | 同函数 | ✅ |
| NoStop 过滤 | `filter_planner_tokens(...,True)`（cfg 时） | 同函数 | ✅ |

> relation row 输出 7 列（type + 6 关系特征），两端同源同函数；NoStop 过滤两端共用同一函数且只作用于 planner input rows。**我方新增/修改的两条路径训练==在线**。

### PASS/FAIL
- [x] type 分布、feature 维度两端一致
- [x] 无训练有/在线无的字段；无在线额外加特征
- 说明：training==online 的 base 级近似差异（traffic_light affects_ego vs next-<30、walker 在线过滤、static 出现与否）为官方原代码固有，**非本 Gate 引入**，不构成 FAIL → **§3.3 = PASS**

---

## §3.4 / §3.5 Path-Waypoint 输出 & Controller（官方 reference JSONL 核验）

基于 `outputs/gate5/gate5_ref_route{29,25,28}_tm100.jsonl`：

| 检查项 | route29 | route25 | route28 |
|---|---|---|---|
| pred_wps / pred_path 可用率 | 100% / 100% | 100% / 100% | 100% / 100% |
| mean_speed_raw (P50) m/s | 14.3 | 2.8 | 1.2 |
| 输出尺度 / shape | 正常（0~20 范围，与 bins 一致） | 正常 | 正常 |
| ego 移动占比 (>0.5m/s) | 91.2% | 53.4% | 46.2% |
| throttle>0 / brake / steer median | 82.1% / 17.9% / 0.006 | 66.5% / 33.5% / 0.005 | 53.6% / 46.4% / 0.003 |
| 完成 | 100%（143s） | 100%（464s） | 100%（349s） |

- §3.4：path+wps 输出 100% 帧可用、无 shape/scale 异常、waypoint 步距合理（首段 ~0.6-2.2m）。
- §3.5：controller 高比例执行 planner（r29 91% 时间在动、制动仅 18% 且集中在减速）；brake 与"planner 高速+刹停"共现约 10-14%，属减速/跟停语义，非"planner 正常但 controller 系统踩死"。route25/28 低速占比高是停车牌/车流 stop-and-go 的正常表现。

### §3.4 / §3.5 判定 = **PASS**（无 shape 异常；controller 正确执行 planner 输出）
