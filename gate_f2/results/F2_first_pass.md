# Gate F2 First-Pass Result (offline retrieval on the frozen F1 80-set)

Representation: Z_F = [P0/Pfree, PL/Pfree] over t=0.5..10 s (40 dims, z-scored).
Labels (G0,GL / quadrant) used only for explanation.

## 1. Distance inequality (the F2 claim)
| family definition | mean d(diff-scene SAME struct) | mean d(same-scene DIFF struct) | control (same both) | holds |
|---|---|---|---|---|
| literal scene (8) | 4.16 | 19.02 | 2.15 | TRUE |
| mechanism (cross/blocked/lead) | 6.04 | 9.64 | 2.17 | TRUE |

In Z_F space the dominant geometry is structure, not scene: cross-scene pairs
that share a structure are ~4-5x closer than within-scene pairs that differ in
structure (literal); the gap narrows but persists under the harder
mechanism-level exclusion.

## 2. Leave-family-out retrieval
- literal-scene kNN (pedestrian/vehicle crossing treated as different physical
  families, per F2 protocol): k=1 hit 1.00, k=5 hit 0.975
  (pool prior ~0.48). Structure is retrievable across scenes.
- mechanism-level leave-out: Optional 0.76 (cross <-> lead reuse),
  Contingency 0.09, LateralNecessary 0.00.

## 3. What the first pass reveals (coverage gap, not representation failure)
LateralNecessary is currently only realized inside the "blocked" mechanism
(B1/B2). Under mechanism-leave-out no Necess source exists in the pool, hence
0.00. Contingency is realized in A(g4, cross) and D (blocked); cross-mechanism
reuse exists but nearest neighbors are dominated by blocked-family samples.
This pinpoints exactly which states F2 must ADD (physics change only, no method
change) to prove full cross-mechanism reuse:
  - near-stationary / very-slow lead (v~0.5-1.0) + free left  -> LateralNecessary
  - blocked current + left free at far state (A/B variants)     -> Optional variety
  - vehicle-crossing family normal + g4 (already gives Optional/Contingency)
  - a "slow lead then accelerating away" state                  -> Contingency (optionality removed)

## Figures
gate_f2/figures/f2_PCA_struct_vs_scene.png (structure-colored vs scene-colored
Z_F projection; structure clusters visible, scenes intermix within structure).
