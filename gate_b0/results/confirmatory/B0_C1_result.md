# B0-C1 confirmatory result (independent CARLA states)

Frozen R1 / distance / action set / stats; 72 NEW states (9 cells x 8);
all cross-mechanism pairs; state-level cluster bootstrap (10000, seed 100).
C5 dropped from the main Gate before unblinding (Dev-108 had 864/864 feasible).

## Gate verdict
| condition | met |
|---|---|
| C1 rho>=0.60 and CI low>0.40 | True |
| C2 median D1(Q1) <= 0.5*median D1(Q5) | True |
| C3 >=2/3 mechanism combos rho>0.50 | True |
| C4 cross/same matched ratio <= 1.25 | True |
| **overall confirmatory** | **True** |

## Headline numbers
- overall Spearman(d0,D1_mean) = **0.948**, 95% CI [0.928, 0.964]
- median D1: Q1=0.0152 vs Q5=0.2970 (ratio=0.051); diff CI [-0.288, -0.276]
- cross vs same matched median D1: 0.1296 vs 0.1450 (ratio=0.894); diff CI [-0.101, 0.062]
- feasibility agreement mean = 1.000 (C5 not a Gate)

## Quantile trend
| Q | d0 range | n | D1 median | IQR |
|---|---|---|---|---|
| Q1 | 0.0015-0.0318 | 173 | 0.01515 | 0.01075-0.02072 |
| Q2 | 0.0318-0.0652 | 259 | 0.03371 | 0.02551-0.05119 |
| Q3 | 0.0652-0.1424 | 432 | 0.05672 | 0.0422-0.08029 |
| Q4 | 0.1424-0.3531 | 432 | 0.25782 | 0.21966-0.27528 |
| Q5 | 0.3531-0.4580 | 432 | 0.29701 | 0.28518-0.30921 |

Monotone: **yes**.

## Per coarse-mechanism pair
| combo | n | Spearman |
|---|---|---|
| cross|lead | 576 | 0.9675 |
| block_or_occupancy|cross | 576 | 0.9337 |
| block_or_occupancy|lead | 576 | 0.9444 |

## Pre-registered audits
- Audit A (non-overlap d0 0.5-3s vs d1 8-11s): Spearman = 0.830
- Audit B (action effect): within-state successor distance across different
  actions mean=0.1874 min=0.0409 (0 would mean no action signal).

## Conclusion
**B0-C1 CONFIRMATORY PASS**: on 72 independent CARLA states the frozen R1
continuous distance reproduces the one-step behavioral-consistency relation
across physical mechanisms.

Limits: this supports *one-step behavioral consistency of the R1 distance*
only. It does NOT prove a final Driving Relation, nor end-to-end generalization.
No second-order closure, no Waymo/PlanT, no model training. Figures: figures/.
