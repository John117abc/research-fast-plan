# Gate F2 Stage-2 Result - Cross-Scenario Structure Reuse (104 samples)

Frozen confirmatory expansion: G1/G2/G3 x 8 deterministic rows = 24 new
recordings (virtual-clock self-consistent ego+prop laws) added to the 80 F1
samples -> 104 total. Metric/representation/epsilon/H frozen; no post-hoc
structure thresholding (F2_round2 protocol).

## New physical sources per structure (24 new)
| group | physics (state variation) | n | observed |
|-------|---------------------------|----|----------|
| G1 | lead decelerates to full stop, stays stopped, left free (8 rows over ego_v, s0, v0, tc, a) | 8 | LateralNecessary x8 |
| G2 | same stopped lead, left lane continuously occupied | 8 | Contingency x8 |
| G3 | temporary occupant on C0 leaves within horizon (occ_s, t_leave, away_v varied) | 8 | LateralOptional x8 |

Structure -> mechanism sources (F2 gate 2):
  LateralOptional: cross (A), lead (C), temp-occupant (G3)
  LateralNecessary: blocked (B), stopped-lead (G1)
  Contingency: cross-A g4, blocked (D), stopped-lead+blocked-left (G2)
Each of the three structures now has >=2 independent physical mechanisms.

## The three F2 gates on 104 samples
1. Distance inequality:
   literal-scene  d(diff-scene SAME struct)=4.98  <  d(same-scene DIFF struct)=19.57  (ctrl 2.43)  HOLD
   mechanism     d(cross-mech SAME struct)=6.06  <  d(same-mech DIFF struct)=7.89   (ctrl 2.26)  HOLD
2. Every structure has >=2 mechanism sources:        MET (above)
3. Coarse leave-mechanism-out clusters by structure:
   kNN k=1 hit 0.76, k=5 hit 0.69 (pool prior ~0.44);
   per-structure: LateralOptional 0.94, Contingency 1.00 -> strong
   cross-mechanism reuse; LateralNecessary 0.21 (near its ~0.21 pool share)
   -> the only remaining mechanism-sensitivity.
   literal leave-scene: k1 0.89 (Optional .94, Cont .97, Necess .71).

## Honest open item
LateralNecessary now HAS two physical sources (blocked B1/B2, stopped-lead G1)
and is cleanly separate leave-scene (0.71), but in leave-MECHANISM nearest
neighbours it still does not aggregate above baseline. The stopped-lead
frontier (gradual P0 saturation) and the static-blocker frontier (immediate
saturation) are recognisably the same structure yet not nearest under the
frozen 40-dim metric. Per the freeze, we do NOT re-tune the metric; this is
the specific representation question to carry into the learning stage
(whether Z_F with a fixed-horizon/elementwise metric is the right space, or a
learned/handcrafted kernel is needed to merge mechanism variants of the same
structure).

## Figures / data
gate_f2/figures/f2_PCA_struct_vs_scene.png (now 104 pts)
gate_f1/results/{G1,G2,G3}/run<g>.summary.json, f1_all_summary.csv (104 rows)
gate_f2/results/retrieval_metrics.json
