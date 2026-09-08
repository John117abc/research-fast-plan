# F3-A2 Prototype results on Dev-108 (frozen hyperparams; exploratory, not a Gate)

Variants on the frozen 4-channel absolute-time CNN pipeline:
  0 baseline; 1 phase-normalized (cumulative-variation phi re-sample);
  2 temporal augmentation (stretch+shift); 3 phase + augmentation.
Dev targets (user): lead fold per-struct k1 Necessary>=.75, Optional>=.90,
Contingency>=.90; geometry d(leadNec,blockNec) < d(leadNec,leadOpt).

| proto | cross k1 | lead k1 | lead Opt | lead Nec | lead Cont | block k1 | d(leadNec,blockNec) | d(leadNec,leadOpt) | inverted |
|-------|----------|---------|----------|----------|-----------|----------|---------------------|--------------------|----------|
| 0 abs (base) | .833 | .611 | 1.00 | 0.00 | .833 | 1.00 | 3.46 | 0.05 | no |
| 1 phase only | .861 | .556 | 1.00 | 0.00 | .667 | .958 | 3.22 | 0.16 | no |
| 2 aug only | .778 | .694 | 1.00 | .083 | 1.00 | 1.00 | 1.39 | 0.33 | no |
| 3 phase+aug | .861 | .639 | .583 | .333 | 1.00 | 1.00 | 0.40 | 0.08 | no |

## Readout
- Phase-normalization alone does not fix the collapse (lead Necessary still 0.00;
  it does not remove mechanism identity for the lead family).
- Temporal augmentation is the direction that works: d(leadNec,blockNec) shrinks
  3.46 -> 1.39 -> 0.40 (proto2 -> proto3) and lead Necessary rises 0.00 -> .083 -> .333.
- Combination proto3 pulls Necessary toward the other Necessary sources by
  ~9x, but the geometry is NOT inverted yet (0.40 vs 0.08) and it degrades
  lead Optional (.583), i.e. the remaining failure is Optional<->Necessary
  within lead, not Contingency (Cont stays 1.0 in 2/3).
- No prototype meets the dev targets. Stopped-lead Necessary still clusters with
  lead Optional; the two differ mainly by the late terminal collapse.
- A recurring side observation: cross-fold Optional is weak (~0.58) in all
  variants - Optional cross-mechanism (cross-clear vs lead/temp) is also not
  robust under this elementwise pipeline.

## Interpretation for the next decision
Temporal/scale invariance is promising but insufficient at this capacity/
alignment level; the Optional<->Necessary lead boundary remains unresolved.
This keeps open (and now more salient) the hypothesis that "terminal branch
viability (G-window) alone may not fully define structural equivalence" - i.e.
immediate dead-end vs gradually-lost-progress may be two driving-relevant
states. Deciding between (i) stronger scale/onset-invariant representation or
(ii) refining the structure definition is the fork; no new untouched data yet.
