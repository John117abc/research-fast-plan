# Gate B0-R3 result: continuous R1 distance one-step closure (Dev-108)

Development only. R1, distance, action set, thresholds, scenarios unchanged;
no training, no new data, no second-order closure, no confirmatory set.

## Question
Does smaller d0 (R1 distance) imply smaller D1 (R1 distance after the same
forced action)? Tested on ALL cross-mechanism pairs (no mutual-NN / bottom-10%
/ |Peq|>=15 selection). B0-R2's historical G1 FAIL is unchanged.

## Overall
- cross-mechanism pairs: 3888; matched same-mechanism controls: 3888
- Spearman(d0, D1_mean) = **0.958**, 95% cluster-bootstrap CI [0.943, 0.970]
- median D1: Q1=0.0158 vs Q5=0.2947 (Q1/Q5=0.053); diff CI [-0.284, -0.274]
- cross vs same matched: median D1=0.1292 vs 0.1308; ratio=0.988; diff CI [-0.065, 0.028]
- feasibility agreement: Q1=1.000, Q5=1.000

## Quantile trend (median D1_mean)
| Q | d0 range | n | D1 median | IQR | feas |
|---|---|---|---|---|---|
| Q1 | 0.0000-0.0320 | 389 | 0.01576 | 0.01175-0.02159 | 1.0 |
| Q2 | 0.0320-0.0599 | 583 | 0.03139 | 0.02565-0.0446 | 1.0 |
| Q3 | 0.0599-0.1553 | 972 | 0.06233 | 0.04532-0.09371 | 1.0 |
| Q4 | 0.1553-0.3530 | 972 | 0.2568 | 0.19887-0.27707 | 1.0 |
| Q5 | 0.3530-0.4471 | 972 | 0.2947 | 0.28308-0.30811 | 1.0 |

Monotone Q1<Q2<Q3<Q4<Q5: **yes**.

## Per coarse-mechanism pair
| combo | n | Spearman | median D1 Q1 | median D1 Q5 |
|---|---|---|---|---|
| cross|lead | 1296 | 0.9805 | 0.01502 | 0.29149 |
| block_or_occupancy|cross | 1296 | 0.952 | 0.02084 | 0.2946 |
| block_or_occupancy|lead | 1296 | 0.9468 | 0.01484 | 0.29776 |

## Pre-registered development conditions
| condition | met |
|---|---|
| C1 rho>=0.60 and CI low>0.40 | True |
| C2 median D1(Q1) <= 0.5*median D1(Q5) | True |
| C3 >=2/3 mechanism combos rho>0.50 | True |
| C4 cross/same matched ratio <= 1.25 | True |
| C5 feasibility agreement Q1 > Q5 | False |

All conditions met: False

### C5 caveat (important)
C5 is **not testable on Dev-108**: all 864 forced-1 s successors are feasible
(no collisions / dead-ends), so feasibility agreement is identically 1.0 in
every quantile. This is absence of signal, not evidence against the hypothesis.
The distance-based conditions C1-C4 are all satisfied.

## Conclusion
**B0-R3 DEVELOPMENT SUPPORT**: on Dev-108, smaller initial R1 distance
continuously predicts smaller post-action R1 distance (rho=0.958), with a clear
monotone quantile trend and no cross-mechanism penalty relative to
initial-distance-matched same-mechanism pairs.
This is development support only, NOT a confirmatory PASS. No second-order
closure, no confirmatory data, no model training were performed.

Figures: figures/r3_fig1..6.
