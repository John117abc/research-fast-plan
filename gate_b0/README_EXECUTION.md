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

## B0-R2 R1 one-step closure (stopped at G1)

```bash
conda run -n plant2 python -u gate_b0/scripts/11_build_r1_successors.py   # ~20 min
conda run -n plant2 python -u gate_b0/scripts/12_r2_pairs.py
conda run -n plant2 python -u gate_b0/scripts/15_r2_stop_report.py
```

`|Peq| = 11 < 15` (only 11 mutual cross-mechanism NN pairs exist), so per
protocol sections 2/8 the round stops before closure: no `r2_closure_*.csv`,
no two-step. Coverage was fine (6 fine pairs, 3 coarse combos). See
`results/r2/B0_R2_result.md`.

## B0-R2D difference-attribution diagnostic (no Gate)

```bash
conda run -n plant2 python -u gate_b0/scripts/16_r2d_diagnostics.py   # ~6 s
```

Pure analysis of the existing R1 signatures/pairs (no engine runs). Compares
A=11 candidates, B=next 39 cross pairs, C=39 mid-distance cross pairs.
Conclusion: **Result A (temporal detail)**. A and B share near-identical
action ranking (rho 0.999/0.996), branch existence (1.0) and opportunity trend
(1.0); B's residual is largely a <=2 s time offset (R_time median 0.35) and NOT
amplitude (R_scale negative). C is clearly different (d_raw ~35x, rho 0.82,
exist 0.78, dVL 0.47). See `results/r2d/B0_R2D_result.md`.

## B0-R3 continuous one-step closure (development support)

```bash
conda run -n plant2 python -u gate_b0/scripts/17_r3_build_cache.py
conda run -n plant2 python -u gate_b0/scripts/18_r3_pairs_closure.py
conda run -n plant2 python -u gate_b0/scripts/19_r3_stats.py      # ~37 s
conda run -n plant2 python -u gate_b0/scripts/20_r3_report.py
```

All cross-mechanism pairs (3888) + same-mechanism matched controls; successor
R1 read from cache (864 entries, all valid). Result: Spearman(d0,D1_mean)=0.958
(95% cluster-bootstrap CI [0.943,0.970]); monotone Q1<...<Q5 (median D1
0.016->0.295); cross/same matched ratio 0.988 (CI spans 0). Conditions C1-C4
met; C5 not testable (all successors feasible -> feasibility agreement =1.0).
Recorded as **B0-R3 DEVELOPMENT SUPPORT**, not a confirmatory PASS. See
`results/r3/B0_R3_result.md`.





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
