# F3 Dataset & Experiment Protocol (frozen 2026-09-07)

Status note: the F2-104 set is downgraded to **Dev-104** (development set only).
It is NOT the independent test set for F3. F3 uses a NEW dataset generated to
this protocol, with mechanism-isolated splits.

Evidence chain this protocol serves:
  F1 structure affects maneuver necessity
  -> F2 structure recurs across physical mechanisms (Dev-104)
  -> F3-A cross-mechanism structural equivalence is LEARNABLE (this protocol)
  -> F3-B raw physical state predicts that relation (next protocol)

## 1. Dataset: target composition
Coarse mechanisms (physics families):
  M_cross = {A1 pedestrian crossing, A2 vehicle crossing}  (+ crossing-stall variants)
  M_lead  = {C slow lead, G1 stopped lead, G2 stopped lead + left occ}
  M_block = {B1/B2 static blocker/queue, D1/D2 + left occupied}
  M_temp  = {G3 temporary occupant leaving}
Structure labels are EMPIRICAL (computed from the frozen engine, G0/GL plus
full-frontier shape), never hand-assigned by intended scenario.

Coverage matrix (cells with target count; X = physically not realized):
| structure / mech      | M_cross        | M_lead   | M_block | M_temp |
|-----------------------|----------------|----------|---------|--------|
| LateralOptional       | 12 (clears)    | 12       | X       | 12     |
| LateralNecessary      | 12 (stall+free)| 12       | 12      | X      |
| Contingency           | 12 (stall+occ) | 12       | 12      | X      |

Target new-sample size N >= 108; every cell sampled across >=2 scenes and a
deterministic sweep of >=2 state variables (parameter rows, NOT CARLA random
seeds). Generation uses the F1/F2 builder kinematics extended by:
  crossing-stall (occupant enters lane and stays until horizon end),
  crossing + left-occupied,
  broader timing/distance sweeps so each cell covers boundary states too
  (boundary samples keep their empirical label).
Dev-104 is NOT merged into training; used only for sanity figures.

## 2. Parameter sampling rule (deterministic, per cell)
Each cell = 12 rows built from a 2-3 variable grid (per mechanism):
  - shared: v_target in {6, 8, 9}; start/conflict geometry in the spawn-safe
    window; dt/H/engine constants as frozen (do not touch).
  - M_cross: distance d_conflict, occupancy window (clear -> Optional;
    stall-to-horizon -> Necessary; stall + left stream -> Contingency).
  - M_lead: cruise v0, brake onset tc, decel a, stop distance; left free/occ.
  - M_block: L_block, queue spacing; left free/occupied.
  - M_temp: occ_s, t_leave, away_v (clearing within horizon -> Optional).
Rows are written to gate_f3/data/params_*.yaml before generation; recorded as
gate_f3/data/raw/<mech>/run<row>.ndjson; metrics to
gate_f3/data/summary/*.json exactly as F1 02-pipeline.

## 3. Train / Val / Blind-Test split (mechanism-isolated)
Mechanisms {M_cross, M_lead, M_block} each get a leave-one-mechanism-out fold.
M_temp is always in the training pool (Optional diversity).
Per fold f with test mechanism T in {cross, lead, block}:
  - Train   = all samples of the other two test-eligible mechanisms + M_temp
  - Val     = 15% of Train samples for early stopping
  - Blind   = all samples of T  (mechanism unseen in Train AND Val)
Evaluation aggregates over the 3 folds. Reported per structure only on folds
where that structure exists in T (Optional absent in M_block is expected).

FROZEN SPLIT RULES (2026-09-07):
- Group-disjoint Val: Val is NOT random sample-wise. Train/Val are split by
  scene x parameter-template GROUP (same initial distance / speed / timing
  family must not straddle Train and Val). A group = one row family; val rows
  are whole groups held out.
- Blind one-time open: all three Blind folds (cross, lead, block) are generated
  and SEALED before any model training. After model structure, embedding dim,
  loss, learning rate, epochs and early-stop are frozen, the three folds are
  run ONCE in a single sweep. No seeing a cross-fold result and then adjusting
  the model before running lead/block - doing so would turn later folds into
  development set.

## 4. F3-A task & minimal model
Input  : full frontier channels over t=0.5..10 s. Normalization ONLY when
         Pfree(t) > eps; NO sentinel (-1/999/NaN) may enter the network.
         Infeasible timesteps are handled explicitly. 4-channel input:
           ch0 = P0(t)/Pfree(t),  ch1 = PL(t)/Pfree(t),
           ch2 = M0(t) feasibility mask of the current corridor,
           ch3 = ML(t) feasibility mask of the alternative corridor.
         (mask = 1 where the branch has a feasible value at t, else 0). This is
         numeric hygiene, not an extra Relation rule.
Task   : learn embedding r = f_theta(x) such that
           same structure  -> r_i ~ r_j
           different structure -> r_i !~ r_j
         no quadrant/threshold input at inference.
Model  : deliberately small temporal encoder: two 1-D conv blocks over the time
         series (4 channels) -> max/mean pool -> MLP -> r (d=8).
         Supervised contrastive (InfoNCE-style); positive pairs = cross-
         mechanism same-structure ONLY (never same mechanism); negatives are
         different-structure. Optimizer Adam; hyperparameters fixed before the
         one-time Blind sweep (see split rules). No hyperparameter search on
         Blind.
Baselines reported identically: euclid on raw Z (Dev numbers) and linear M.
No tuning of epsilon/H/labels on Blind.

## 5. F3-A PASS/FAIL Gates (decide on Blind, 3 folds pooled)
  G1 Learnable structural equivalence, leave-one-mechanism-out structure
     hit-rate k=1 of f_theta, ALL of:
        k1 overall        >= 0.80
        k1 LateralNecessary >= 0.70
        k1 LateralOptional  >= 0.89   (not worse than euclid by > ~0.05)
        k1 Contingency      >= 0.95
     The per-structure floors are mandatory: learned space must not trade
     Optional/Contingency performance to lift Necessary.
  G2 Retrieval geometry: within Blind folds, mean d(cross-mech same-struct) <
     mean d(same-mech diff-struct) under learned representation.
  G3 No-label-shortcut sanity: per-fold confusion ~diagonal; purity of top-5
     cross-mechanism neighbours well above fold base rate; report even on FAIL.
PASS requires G1 and G2. On FAIL: freeze here; revisit the definition of
structural equivalence BEFORE any F3-B (raw-state prediction).

## 5a. Anti-degeneracy requirement for M_cross stall cells
cross-stall -> Necessary (and cross-stall + left-occupied -> Contingency) MUST
show clear crossing-origin dynamics and NOT degenerate into "a sideways static
blocker":
  - the actor performs a real crossing motion first (starts off-corridor,
    crosses into the current corridor with lateral heading),
  - then persists in the current corridor for the horizon (long occupancy),
  - left corridor is traversable/free (Necessary) or occupied (Contingency),
  - it is NEVER initialized as a static obstacle standing in the lane.
i.e. the sample demonstrates: dynamic crossing interaction -> persistent
current-corridor closure, not a re-made B/D. Offline check: the recorded
occupant lat profile must show entry-from-outside across several frames before
settling in-lane.

## 6. Artifacts
gate_f3/data/{params,raw,summary}, gate_f3/figures,
gate_f3/results/F3A_result.md. All generator/model scripts pinned in gate_f3/.

## 7. Execution order (then do-not-revise)
1. implement crossing-stall / crossing+leftocc builders + row tables (frozen);
2. generate dataset to quota; 3. run offline metrics;
4. implement F3-A model + split + gates; 5. execute & report PASS/FAIL.
