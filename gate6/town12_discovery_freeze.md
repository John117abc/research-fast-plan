# Gate 6 · Town12 Discovery Dataset 冻结

> 日期：2026-09-04 · 条件：PlanT-Reference / TM seed=100 / 快照 5 Hz
> 状态：**每类 ≥8 个独立有效 instance 达成**，冻结进入 actor-removal / dominant-actor 阶段。

## 采集路线（routes_training.xml Town12）
| route | 结果 | game | 快照帧 | replay(max err) | 说明 |
|---|---|---|---|---|---|
| route10 | Completed 100% | 1718s | ~8579 | 26/26, 1.6e-2 m | 首条，含 HB7/PCI5/VT2/PED5 |
| route14 | Completed 100% | 1788s | ~8931 | 14/14, 4.4e-4 m | HB7/PED4/VT5（PCI 0） |
| route3（disc） | 手动终止（目标已足） | ~814s* | ~4068 | 12/12, 1.3e-3 m | 补 PCI/VT；未要求跑完 |

> *route3 因目标已达成提前终止；已完成段快照保留。

## Discovery 有效 instance 池（语义 interaction==Y，无人工清洗）
| Group | type | 总数 | route10 | route14 | route3 |
|---|---|---|---|---|---|
| A | HardBreakRoute | **14** | 5 | 3 | 6 |
| B | ParkingCutIn | **9** | 5 | 0 | 4 |
| C | VehicleTurningRoute | **8** | 2 | 5 | 1 |
| D | PedestrianCrossing | **10** | 5 | 4 | 1 |

> 注：HardBreak 部分实例（如 route10 HB1/2、HB4/5 与 HB6/7）存在窗口重叠/无前车 token 现象，**保留原窗不删除**，由后续 dominant-actor 的 D_i 统一筛选；仅明显映射错误才剔除。

## 产物清单
- `gate6/town12_manifest.csv` / `town13_manifest.csv`
- `gate6/town12_discovery_routes_reachable.csv`
- `gate6/town12_discovery_instances.csv`（60 条逐 instance 语义记录）
- `gate6/scnlog_route10|route14|route3disc.jsonl`（S 事件）
- `gate6/semantic_route10|route14|route3.csv`
- `outputs/gate6/snapshots/exact_town12_route10_*|route14_*|route3_discovery_*/`（.npz + meta.jsonl）
- `gate6/replay_check_*.csv`（微 pilot/route10/route14/route3 全 PASS）
- `gate6/engineering_qualification_freeze.md`

## 下一阶段
1. actor-removal：对每个 snapshot 逐个删动态 actor → D_i = RMS(pred_wps_remove − pred_wps_base)
2. single-dominant 筛选：D1 ≥ 0.20 m 且 D1/max(D2,0.05) ≥ 1.5
3. 每 instance 选 4 个 decision states（early/early-mid/late-mid/late，间隔 ≥1 s）
4. 统一 5 类 intervention（I1-I5）→ Planning Response Signature
（先暂停，等反馈）
