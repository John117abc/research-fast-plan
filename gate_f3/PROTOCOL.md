# Gate F3 Protocol - Metric/Representation Learning for mechanism-invariant
# future-structure (draft 2026-09-07)

Goal: on the frozen 104-sample Z_F set (gate_f2), learn a representation/
distance such that mechanism variants of the SAME structure merge, measured by
the F2 gates. Success = LateralNecessary (and all structures) aggregate under
leave-mechanism-out, not because we changed epsilon/H/labels or the frozen Z_F.

## Supervision (structure only, no quadrant re-tuning)
Pair geometry built from labels (structure, literal scene, mechanism):
  positives P : mechanism_i != mechanism_j, structure_i == structure_j
  negatives N : mechanism_i == mechanism_j, structure_i != structure_j
Learning pulls P close and pushes N apart in the learned space.

## Model (chosen for N=104: tiny, interpretable)
Low-rank linear metric: d^2_M(Zi,Zj) = (Zi-Zj)^T A^T A (Zi-Zj), A in R^{40 x r}
r=6. Triplet-hinge + L2, Adam, numpy-only. Z frozen & z-scored from F2.

## Evaluation (frozen gates, unchanged from F2)
- CV protocol: leave-one-literal-scene-out. Metric A_fit trained on triplets
  with NO pair touching the held-out scene; test scene queries use pool of the
  other scenes; aggregate over the 11 folds.
- Metrics: (g1) d(cross-mech same-struct) < d(same-mech diff-struct);
  (g2) per-structure leave-mechanism-out kNN hit-rate (Optional/Contingency/
  Necessary); (g3) overall leave-mechanism-out hit vs pool prior.
Baseline: Euclidean (F2 numbers). No structure thresholds changed.
Caveats recorded: N small; CV folds share scenes of same mechanism.
