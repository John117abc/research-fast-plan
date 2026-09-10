# Gate B0 execution notes

Run from the repo root with the `plant2` env:

```bash
bash gate_b0/scripts/00_freeze_env.sh
conda run -n plant2 python -u gate_b0/scripts/01_data_health.py
conda run -n plant2 python -u gate_b0/scripts/02_smoke_action_probe.py
conda run -n plant2 python -u gate_b0/scripts/03_build_signatures.py   # ~20 min
conda run -n plant2 python -u gate_b0/scripts/04_build_pairs.py
conda run -n plant2 python -u gate_b0/scripts/05_run_one_step_closure.py
conda run -n plant2 python -u gate_b0/scripts/06_make_figures.py
```

Discovery result: **G0 PASS, G1 FAIL** -> Gate B0 discovery FAIL; per protocol
section 24 Case A, stop and do not train a network.

## B0-R1 representation validation (development only)

```bash
conda run -n plant2 python -u gate_b0/scripts/09_build_r1.py       # ~4 min
conda run -n plant2 python -u gate_b0/scripts/10_r1_diagnostics.py
```

R1 replaces R0's scalar max-progress with per-action, per-branch progress
curves `{V0^u(t), VL^u(t)}` (320 values/state). Result: R0 collapse resolved
(unique 107/108, largest cluster 2, all-ones 0; lead_opt vs lead_nec ratio
1.12 vs undefined for R0; block_nec current-corridor half-decay at 4.5 s vs
9.0 s for lead_nec). No closure Gate, no training, no confirmatory data.


## Deviations from the plan text (recorded, per constraint 6)

1. The plan lists `gate_f0/feasible/{corridor_builder,lane_change_primitive,
   occupancy_gt,collision_check,progress_frontier}.py`. These do not exist;
   the frozen engine is `gate_f0/feasible/engine.py` (StraightCorridor,
   OccupancyGT, compute_frontiers) plus `beam_search.py`,
   `longitudinal_primitives.py`, `corridor_map.py`. B0 calls `engine.py`
   semantics through a wrapper (`action_probe/constrained_rollout.py`) and does
   NOT modify it.
2. CARLA is **0.9.15** in this environment, not 0.9.16.
3. `target_actor_ids` is not a stored field. It is derived as all non-ego
   recorded actor ids per row (`common.list_states`), and the free baseline
   removes exactly those ids. No background TM actors exist.
4. `param_group_id` is not stored. Defined as `cell | v{ego_v} | family_key`,
   where family_key bins the cell's primary continuous variable
   (`L`, `d_conflict`, `occ_s`, `s0`) with width 8 (see `common.py`).
5. Confirmatory G1 threshold pre-registered as `|Peq| >= 10` (scaled 15*72/108);
   fine/coarse coverage conditions are NOT scaled.
6. `d0` bottom-10% threshold is degenerate here (10th percentile of cross-pair
   d0 is exactly 0.0 because R0 collapses), so the candidate rule requires
   d0_mean == 0; see the verdict.
