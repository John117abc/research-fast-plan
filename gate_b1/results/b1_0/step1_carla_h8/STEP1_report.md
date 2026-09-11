# B1-0 Step 1: CARLA H=8s compatibility audit

Frozen 72 confirmatory states; horizon truncated 10s -> 8s; no threshold change.

## Pre-registered criterion
Spearman(d_R8s, d_R10s) >= 0.90 AND C1-C4 all PASS.

## Result
- cross-mechanism pairs: 1728; same-mechanism pairs: 828
- Spearman(d_R8s, d_R10s) = **0.996**
- Spearman(d0,D1) at 8s = 0.953, 95% CI [0.93407, 0.96786]
- median D1: Q1=0.0109 Q5=0.2691; matched ratio=0.9717
- mechanism rho: {'cross|lead': 0.9706, 'block_or_occupancy|cross': 0.9344, 'block_or_occupancy|lead': 0.9519}

| condition | met |
|---|---|
| dist_rank_corr>=0.90 | True |
| C1_rho>=0.60_CIlow>0.40 | True |
| C2_Q1<=0.5*Q5 | True |
| C3_two_of_three_mech_rho>0.50 | True |
| C4_matched_ratio<=1.25 | True |

## Verdict: **STEP1 PASS -> continue B1-0 Steps 2-6**

