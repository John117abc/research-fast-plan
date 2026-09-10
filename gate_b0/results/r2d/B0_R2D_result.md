# Gate B0-R2D: cross-mechanism near-neighbour difference attribution

Diagnostic only. R1, distance, action set, thresholds unchanged; no new data,
no training, no closure. Groups: A=11 candidates, B=next 39 cross pairs,
C=39 cross pairs in the 50-75th percentile band.

## Group medians (d_raw = R1 distance)
| group | n | d_raw | R_time | R_scale | rho_action | exist_agree | dVL_trend_corr |
|---|---|---|---|---|---|---|---|
| A | 11 | 0.006 | 0.2402 | -0.0456 | 0.999 | 1.0 | 1.0 |
| B | 39 | 0.0092 | 0.3509 | -0.0877 | 0.996 | 1.0 | 1.0 |
| C | 39 | 0.3241 | 0.1576 | 0.1991 | 0.8185 | 0.7812 | 0.4744 |

Descriptive criteria (not a Gate): R_time high>=0.30, R_scale high>=0.15, rho high>=0.80, rho low<=0.50.

## Conclusion: **A_time_or_scale_dominated**
**Result A (mainly irrelevant time/scale detail)**, specifically *temporal*
misalignment, not amplitude scaling: R_scale is negative for both A and B.

### Q1: why are the 11 A pairs so close?
- d_raw median 0.0060 (tiny); rho_action=0.999, exist_agree=1.000, dVL_trend=1.000:
  the action-consequence structure genuinely agrees.
- Even for A, R_time median 0.240: part of the residual is a <=2 s time offset;
  R_scale median -0.046 (negative) means it is NOT an amplitude difference.
### Q2: why did the 12-50 pairs (B) miss the candidate set?
- They are only marginally farther: d_raw median 0.0092 (A=0.0060, C=0.3241).
- Their structure is essentially identical: rho_action=0.996 (100% of B pairs >=0.95),
  exist_agree=1.000, dVL_trend=1.000.
- The residual is largely TEMPORAL: R_time median 0.351; 26% of B pairs have R_time>=0.5 and 62% >=0.30.
- NOT scale: R_scale median -0.088 (negative); only 13% of B pairs have R_scale>=0.15.
- So B missed candidacy on the strict mutual-NN + bottom-10% rule, not because
  of a true action-consequence difference.
### Q3: A/B vs clearly different C
- C is far: d_raw median 0.3241 (~35x B), rho_action=0.819, exist_agree=0.781, dVL_trend=0.474.
- Time shift does not rescue C (R_time median 0.158, and larger shifts are needed); C differences are real action-consequence differences.

## Caveat
R_time is a ratio on already-tiny A/B distances, so it is noisy in absolute
terms; the robust signals are the near-identical action ranking, branch
existence and opportunity trend for A/B versus the clearly different C.
The R2 G1 shortfall (11 vs 15) is therefore a narrow margin in the pair
selection rule, not a structural collapse of R1.

## Auto-selected typical pairs (fig6)
figures/r2d_fig6_typical_pairs.png: max R_time; high rho with large d_raw;
max d_raw. No manual selection.

## Not run
No PASS/FAIL Gate; no closure; no new R2 representation; no data/training.
Figures: figures/r2d_fig1..6.
