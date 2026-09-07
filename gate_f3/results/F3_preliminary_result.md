# Gate F3 Preliminary Result - Metric learning on the frozen Z_F set

STATUS: Dev-104 (the former F2-104 set). Down-graded to development set;
superseded by the F3 dataset protocol (gate_f3/F3_dataset_and_experiment_protocol.md)
with mechanism-isolated Train/Val/Blind splits. Numbers below are development
evidence only.

Setting: 104 samples, Z_F = [P0/Pfree, PL/Pfree]@0.5..10s z-scored (frozen,
unchanged from F2). Supervision only from labels (structure/scene/mechanism);
epsilon/H/thresholds untouched. Evaluation = F2 gates.

## Euclidean baseline (reported in F2)
leave-mechanism-out kNN k=1: 0.76 overall
  LateralOptional 0.935, Contingency 1.0, LateralNecessary 0.214
d(cross-mech same-struct)=49.4 < d(same-mech diff-struct)=76.1 (gate-1 holds)

## What we tried (tiny-N, interpretable, numpy/scipy)
1. Low-rank linear metric M=A A^T (40x6), triplet hinge d(a,p) vs d(a,n)
   (p = cross-mech same-struct, n = same-mech diff-struct), Adam + per-step
   norm, stratified by structure.
2. Diagonal feature metric w=exp(b), L-BFGS on log-ratio objective, L2 to
   Euclidean.

## Observed behaviour
- A metric tuned to repair the gap CAN lift LateralNecessary cross-mechanism
  retrieval to ~0.64-0.71 (vs 0.214 euclid) in several fits, keeping
  Contingency at 1.0 and gate-1 holding.
- It does so at the expense of LateralOptional (~0.6-0.67 vs 0.935 euclid) and
  the gains are NOT stable across the 11 literal-scene leave-one-out folds
  (per-fold Necess 0.0-1.0, Optional 0.1-1.0).
- Diagonal variants either stay ~Euclidean (strong L2) or collapse to crowding
  (weak L2, Optional 0.91 but Necess 0.11).
- No single small global linear metric robustly merges mechanism variants of
  ALL three structures on this set.

## Interpretation (the honest finding of stage A)
The mechanism-invariant merge of all three structures is not achievable by a
small global linear/isotropic transform of the FROZEN fixed-horizon elementwise
frontier at n=104. This is evidence about the REPRESENTATION, not about the
physics: the elementwise P-curve geometry is under-specified for
cross-mechanism equivalence (stopped-lead vs static-blocker NearestNecessary
differ in shape yet share structure; euclid keeps them apart). A data-driven
stage should therefore learn a NONLINEAR, time-aware representation from raw
state, with the F2 gates used as the evaluation objective and an INDEPENDENT
expanded dataset as the training/validation split (not this 104-set, which
becomes the frozen eval target).

## Required before the learning stage (concrete)
- Independent, larger dataset (scripts/oracle exist; ~O(100s) more samples) so
  structure is not memorised; explicit scene/mechanism holdout splits.
- Learnable representation over raw state (not precomputed Z_F), supervised
  toward same-structure-same-embedding; F2 gates = eval metric.
- Keep F2 metric/epsilon/H frozen as the acceptance test.

## Artifacts
gate_f3/PROTOCOL.md, learn_metric.py, diag_metric.py,
gate_f3/results/metric_results.json, diag_results.json (both attempts logged).
