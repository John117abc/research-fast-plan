# Gate 6 · Engineering Qualification 冻结

> 日期：2026-09-04 · 状态：**PASS**（本阶段不再改动以下基础设施）

| 项目 | 判定 | 证据 |
|---|---|---|
| Scenario runtime mapping（XML↔runtime instance） | PASS | S 事件日志：`config_name(=XML name)`+`type`+owned `actor_ids`+`route_config_name`+`game_time`；route10 全程 7×HB/5×PCI/2×VT/5×PED 精确对应 |
| Actor → token mapping | PASS | snapshot meta 中场景 actor 以 token 出现（token_idx/几何/速度），S 事件 actor_ids 可命中 |
| Forward snapshot | PASS | `.npz` 存 `x_objs/idxs/route_original/speed_limit/BEV` + online pred；dtype/shape 保真 |
| Offline replay（硬 Gate） | PASS | 微 pilot 33/33 max 1.2e-3 m；route10 26/26 max 1.6e-2 m（浮点级） |
| 四类语义 smoke | PASS | route10 100% 完成：HB（lead 急刹+ego 停，HB_3 干净）/ PCI（cut-in 车侧向入道+ego 停）/ VT（对向横切+ego 停）/ PED（walker 横穿 ego path+ego 停） |

## 冻结说明
- HardBreak 不做人工清洗；统一由后续 actor-removal / dominant-actor 的 D_i 筛选决定可用帧，仅删明显映射错误。
- 工具与日志（GATE6_SMOKE / GATE6_SNAP / GATE6_SCNLOG）保持现状，后续采集直接复用。
