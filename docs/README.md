# 实验文档索引

本目录存放关系表示验证实验（Gate 4.x）的配套文档。主方案见根目录 `CARLA_PlanT2_低维驾驶关系快速验证方案_v1.2.md`。

## docs/experiment_plans —— 实验方案（design）

| 文件 | 内容 | 状态 |
|---|---|---|
| `Gate4_5A_路口第一车Blocked零训练诊断方案_修正版.md` | 零训练日志诊断 blocked 机制 | 已执行 |
| `Gate4.5B_Path_Interaction_Relevance_机制闭环执行说明_修正版.md` | Path-Relevance 最小因果干预（证伪 H2） | 已执行 |
| `Gate4.5C_Stop_Sign_Token_Deadlock_因果闭环执行方案_修正版.md` | 停车牌 token 死锁因果干预（确认 H3） | 已执行 |
| `Gate4.6_Exact_NoStop_vs_Relation_NoStop_表示有效性对比实验.md` | 训练+在线同删 type=4，检验 Relation 表示有效性 | 已执行 |
| `Relation_v0_5_规则对象最小诊断补丁.md` | 早期 Rule-Exact 补丁设想 | 已搁置（被 4.5A/B/C 替代） |

## docs/results —— 实验结论（results）

| 文件 | 内容 |
|---|---|
| `Gate45x_Gate46_诊断实验结论汇总.md` | Gate 4.5A/B/C + 4.6 全部结论、对比表与后续建议 |
