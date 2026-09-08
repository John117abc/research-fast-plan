# Gate F3-A Result (one-time, frozen config, 2026-09-08)

Dataset: 108 confirmatory samples (9 cells x 12), empirical labels, health
clean. Frozen config in protocol section 9. Three mechanism leave-one-out
folds (cross/lead/block) trained+sealed once; no per-fold tuning, no early
stopping, no hyperparameter change after any fold was seen.

## Fold results (blind k1)
| test mechanism | blind n | k1 |
|----------------|---------|-----|
| cross  | 36 | 0.806 |
| lead   | 36 | 0.528 |
| block  | 24 | 1.000 |

## Gate verdict (frozen section 5)
- G2 retrieval geometry: d(cross-mech same)=0.510 < d(cross-mech diff)=1.415  PASS
- G1 floors:
  k1 overall       0.750  (need >= 0.80)   FAIL
  LateralNecessary 0.639  (need >= 0.70)   FAIL
  LateralOptional  0.750  (need >= 0.89)   FAIL
  Contingency      0.861  (need >= 0.95)   FAIL
  => G1 FAIL

## Status (per protocol stopping rule)
F3-A does NOT pass: a small nonlinear 4-channel temporal encoder with
supervised contrastive positives restricted to cross-mechanism does not reach
the frozen floors on fully unseen mechanisms, though retrieval geometry (G2)
and the block/cont generalisation are strong and per-mechanism generalisation
varies widely (lead fold weak). Per the frozen rule: F3-A FAIL => do NOT start
F3-B; revisit the definition/representation of structural equivalence first
(e.g. temporal alignment robustness, label noise from engine G-based structure
near boundaries, contrastive-sample efficiency at n~100, or per-structure floor
calibration on this confirmatory set). No result-driven tuning was applied.

Artifacts: gate_f3/results/F3A_result.json, this document.
