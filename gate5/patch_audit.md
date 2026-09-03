# Gate 5 · Step 2 记录：本地代码 vs 官方代码 Patch 清单

> 日期：2026-09-03 · 对应文档 §2（§2.1 diff / §2.2 分类 / §2.3 A/B/C / §2.4 通过标准）
> 结论：**Step 2 = 通过**。所有本地修改均有出处；须关闭项默认全部关闭；影响官方 baseline 数值行为的 patch = 无（仅 2 处 always-on debug 覆盖层，见 §4 注意事项）。

## §2.1 生成物

| 文件 | 内容 | 范围 |
|---|---|---|
| `gate5/local_vs_official.diff` | `git diff 6269e5a -- PlanT tests tools` | official→当前工作区（pilot commit + 未提交），923+/16- |
| `gate5/uncommitted.diff` | `git diff -- PlanT tests tools` | HEAD→工作区（Gate 4.5/4.6 诊断，248+/6-） |
| `gate5/git_status.txt` | `git status` | 全量状态 |

> 注：本地与官方所有代码差异集中在 **15 个代码文件**（PlanT 核心 + tools/tests）。`model.py`、`lit_module.py`、`carla_garage/*`（controller/route planner/BEV）、`leaderboard*`、routes 全部**未修改**。`outputs/` 日志类噪声未纳入 diff。

## §2.2 修改分类表

### 来源分层
- **L1（已提交）**：`relation-pilot` @ 8b6f23c vs official 6269e5a —— relation-representation pilot infra。
- **L2（未提交）**：HEAD vs 工作区 —— Gate 4.5A/B/C + 4.6 诊断。

### 分类表（对照文档 §2.2 行）

| 类别 | 是否修改 | 文件 | 修改内容 | 来源 | 影响官方 baseline？ |
|---|---|---|---|---|---|
| Relation-v0 | ✅ | `PlanT/relation_features.py`（新增） | `relationize_exact_row()`：几何→关系特征（m_now/m_min/closing/tcpa/bearing）；`filter_planner_tokens()` | L1+L2 | 否（见下） |
| Relation-v0 | ✅ | `PlanT/dataset.py` | 训练端：当 `input_representation=relation` 时对 planner input 做 relationize（在 forecasting target 匹配之后） | L1 | 否（cfg-gated） |
| Relation-v0 | ✅ | `PlanT/PlanT_agent.py` | 在线端：当 `input_representation=relation` 时 relationize（需 CARLA label_raw 含 extent） | L1 | 否（cfg-gated） |
| input_ego_speed | ✅ | `PlanT/dataset.py` | `sample["input_ego_speed"]=sample["ego_speed"]`（别名） | L1 | 否（cfg=False 时 model 不消费） |
| input_ego_speed | ✅ | `PlanT/PlanT_agent.py` | `sample["input_ego_speed"]=input_data["speed"]` | L1 | 否（同上） |
| stop-sign | ✅ | `PlanT/PlanT_agent.py` | 仅新增 **deadlock detector**（type4 卡死检测，只置 `_debug_force_clear` 标志，**不改驾驶**）；type4 生成/清除逻辑（`cleared_stop_sign`、3.0/10m）**未改** | L2 | 否（状态只读） |
| NoStop | ✅ | `PlanT/dataset.py` + `PlanT/PlanT_agent.py` + `relation_features.py` + `PlanT.yaml` | `remove_stop_sign_token` 键：训练/在线用同一 `filter_planner_tokens(...,True)` 移除 type=4 | L2 | 否（cfg-gated，官方 ckpt 无此键→False） |
| debug log | ✅ | `PlanT/PlanT_agent.py` | Gate4.5A JSONL（always-on 写 `outputs/gate45a/`）；`desired_speed_raw/mean_speed_raw` 拆变量（纯重构，控制值不变）；dangerous-relations/lead/token 计数（debug）；`data_car_exact_raw` 副本（debug） | L2 | 否（debug only） |
| Dataset | ✅ | `PlanT/dataset.py` | include/exclude towns+scenarios 过滤 + 打印；silent-crash SLURM 日志检查加 `try/except FileNotFoundError`（公共数据无 cluster 日志）；`input_ego_speed` 别名 | L1 | 否（仅训练数据层） |
| PlanT_agent | ✅ | `PlanT/PlanT_agent.py` | 见上各分类；另加 **调试文字覆盖层 `draw_string("EXACT"/"RELATION")`（always-on）** | L2 | 否（可视化，无驾驶影响） |
| PlanT_agent | ✅ | `PlanT/PlanT_agent.py` | Gate4.5B Path mask（env-gated）；Gate4.5C force-drop type4（env-gated） | L2 | 否（默认 OFF） |
| controller | ❌ 未修改 | `carla_garage/*`（LateralPID/LongitudinalLinearRegressionController 及 `lon_pid/lat_pid` 调用） | — | — | — |
| checkpoint | ✅ | `PlanT/lit_train.py` | `CHECKPOINT_ADDON` env → checkpoint 命名 `last_{addon}_{seed}`（默认回退原名） | L1 | 否（仅训练保存名） |
| route planner | ❌ 未修改 | leaderboard/carla_garage waypoint planner | — | — | — |
| 其他 | ✅ | `tests/test_relation_features.py`、`tools/*.py`、`tools/scratch/*` | 离线测试/分析/脚本（relationize 单测、route/dataset 分布分析、解压、训练 run 脚本） | L1 | 否（不在运行时路径） |

## §2.3 A/B/C 分类

### A. 允许保留（debug/统计/结果保存，不改模型行为）
- Gate4.5A JSONL 日志（always-on；文件 IO）
- `desired_speed_raw / mean_speed_raw` 拆变量（控制值与原版逐帧一致）
- token 计数 / dangerous-relations / lead-vehicle 检测（仅写 `_dbg_relation`）
- 调试文字覆盖层 `draw_string`（CARLA debug 可视化）
- 新工具/测试（离线）

### B. 必须关闭（正式 reference 运行时不生效）
| 项 | 开关机制 | 默认状态 |
|---|---|---|
| Relation-v0（online relationize） | checkpoint cfg `input_representation` | **官方 ckpt 无此键 → `exact`（OFF）** ✅ |
| NoStop（type4 filter） | checkpoint cfg `remove_stop_sign_token` | **官方 ckpt 无此键 → `False`（OFF）** ✅ |
| Gate4.5B Path mask | env `GATE45B_MASK` | **未设置 → OFF** ✅ |
| Gate4.5C force-drop type4 | env `GATE45C_FORCE_DROP` | **未设置 → OFF** ✅ |

### C. 必须单独确认（Step 3 处理）
- **input_ego_speed patch**（L1）：训练 `input_ego_speed=True`（研究模型）vs 官方 ckpt `False`；在线端 key 恒产生、但 `model.py` 仅当 cfg=True 时消费 → 需 Step 3.1 逐端确认一致。
- **debug 覆盖层 draw_string（always-on）**：不改变驾驶，但"纯 reference 严格性"上建议 env-gate；本次记录不更改。
- **Gate4.5A JSONL always-on**：同上，属结果保存；不改变驾驶。

## §2.4 通过标准核对
- [x] 所有本地修改都有出处（两层：L1 pilot commit / L2 未提交诊断，逐 hunk 归属）
- [x] Relation / NoStop / intervention 已关闭（4 项开关全部默认 OFF，见 §2.3 B 表）
- [x] debug-only patch 不影响 forward/control（重构逐帧等价；其余 debug 均为只读记录）
- [x] 影响行为的 patch 已单独标记（input_ego_speed 入 C 类 → Step 3.1；type4 生成/清除逻辑确认未动）

## §2.4 FAIL 条件核对
- 不知道某段代码为什么被改 → 未出现（每 hunk 有 Gate/实验出处注释）
- 无法确认是否影响 planner input → 已确认：planner input 的改动仅 relationize / nostop-filter / 45B-mask / 45C-drop，**全部 cfg 或 env 门控且默认关闭**
- 无法确认 Dataset 与 online agent 是否一致 → 部分确认：relationize 与 remove_stop filter 两端共用同一 `relation_features.py` 函数；Step 3.3 将逐 token/维度再核对

## 注意事项（供 Step 4 smoke 决策）
1. 官方 reference smoke 时，planner/control 数值行为 = 官方逻辑（重构等价 + 干预全关）。
2. 仍生效的 always-on 附加项：① 每帧写 JSONL；② `draw_string` 文字覆盖。均为 debug-only，无驾驶影响；若追求"极净 reference"，可为二者加 env 门控后再跑（需用户确认是否改动）。
3. 工作区含未提交诊断代码 —— 建议 Gate 5 通过后单独 commit，保持 official/pilot/诊断三层历史可追溯。
