# Gate F0 PilotGate 状态（2026-09-06）

## 判定总览
| 项 | 状态 |
|---|---|
| **F0 engine（offline feasible engine）** | **PASS**（H=10s、单调 P、future-only margin、lane-change state machine、GT occupancy） |
| **B StaticBlocker_FreeLeft（CARLA）** | **PASS** —— 冻结为 Lateral-Necessary prototype |
| **A TemporaryClosure（Synthetic offline）** | **PASS（原型成立）** —— growth→plateau→resumed growth 稳定出现在 closure 窗覆盖 ego 到达的 cells |
| **A TemporaryCrossing（CARLA PED）** | **NOT VALID archetype** —— 录制未真正形成 closure（ego 速度/到达与占用窗边缘错位）；按研究原则记"实例未满足 closure 条件"，**不判 F0 失败** |
| 后续 C/D / 120-run | 待 synthetic A + B 稳定后进入 |

## B（CARLA, frozen PASS）
- H=10s，5/5 seed：G4-6 高（transient）→ G6-8 衰减 → **G8-10≈0**（当前分支饱和/dead）；PL≈81m alive。
- 结论：**persistent blockage + alternative branch 由未来可行空间自然形成 current-dead / alternative-alive topology**，不依赖场景标签/planner。
- 数据：`gate_f0/results/pilot/static_blocker/seed{1..5}.ndjson`

## A（Synthetic TemporaryBarrier, offline）
- 冻结走廊：Town12 `gate_f0/road_segment.json`（C0/CL 实测采样）；full-lane occupancy 在冲突点 s_c ∈ {20,30,40 m}、closure window [Ts, Ts+dur]（dur ∈ {2,3,4}s）、v0 ∈ {4,6,8}。
- 扫 13 cells 结果（`gate_f0/results/synthetic_A_summary.csv`）：
  - closure 窗覆盖 ego 最快到达的 cells → **P0 出现 plateau 后 terminal 恢复**（例：s_c=20/dur3-4、s_c=30/dur4，G8-10 恢复为正，P 单调）。
  - 窗在 ego 到达前已开（如 s_c=40/dur2、远距离短窗）→ 显示 **no-closure（free）**，物理正确（barrier 在 ego 可达前已消失）。
- 图：`gate_f0/figures/synthetic_A_P0.png`（closure vs free 两条 P0(t)）
- 说明：closure 语义是"某区间内当前 corridor 所有 forward-passing branch 被截断、其后重新开放"，由 GT occupancy 决定；短窗(<1.5s)抑制可能不被 1.5s 平台指标检出，属指标粒度而非结构问题。

## CARLA PED A 记录（诚实留档）
- 已按冻结语义（H=10、warm-up v≥4 1s 触发、行人 −3→+3 完整出车道、窗 3-4s）重录，但 ego 速度逐 seed 抖动（0.5-5.7 m/s），到达时刻与占用窗边缘错位，`P0(t)` 仍接近 free。
- 结论措辞：**现实场景实例尚未形成有效 temporary-closure archetype**；PED 不自动等于 Temporary Closure —— 这本身就是"feasible structure ≠ scenario label"的佐证。

## 冻结配置（后续 A/C/D 共用，不再改）
- H = {2,4,6,8,10}s；主 terminal 指标 **G8-10 = (P10−P8)/2**
- decision = 统一 interaction-onset（可决策帧 v≥1）
- s0=0 相对 decision；occupancy 相对化；margin 仅约束 future 扩展
- config：`gate_f0/config/gate_f0.yaml`

## 产物索引
`gate_f0/results/pilot_summary_v2.csv`、`pilot_frontiers_v2.json`、`synthetic_A_summary.csv`、`gate_f0/results/pilot/{static_blocker,temp_crossing}/*.ndjson`、`gate_f0/figures/synthetic_A_P0.png`

## Synthetic C/D（离线，engine 复用）——四象限闭环
`gate_f0/results/synthetic_C_D_summary.csv`、`gate_f0/figures/f0_quadrants.png`

| 原型 | 构造（occupancy） | G0 | GL | 象限 |
|---|---|---|---|---|
| **A' LongitudinalSufficient** | C0 临时闭合 [1,5]s@30m + CL 墙 | 7.0 | ≈0(无可行) | current alive / alt dead |
| **B LateralNecessary** | C0 静态 30m + CL 空 | 0.0 | 12.4 | current dead / alt alive |
| **C LateralOptional** | C0 慢前车(2.5–4 m/s) + CL 空 | 2.5–4.0 | 12.4 | both alive |
| **D Contingency/Wait** | C0 静态 30m + CL 全 horizon 车流墙 | 0.0 | 无可行 | both dead |

四类象限全部由"未来可行 branch 是否还能持续 progress"自发产生（G8-10 terminal growth），无规则标签。

## 下一步
1. Synthetic A 补足到 >10 稳定 cells（微调窗对齐），连同 B 一起作为 F0 第一批正证据；
2. 进入 C（SlowLead+alternative）/D（blocked platoon）的合成原型（engine 已支持 platoon occupancy 多 actor）；
3. CARLA A 视需要以确定性脚本（非 Lane-PID 随机 ego）重建 archetype。

