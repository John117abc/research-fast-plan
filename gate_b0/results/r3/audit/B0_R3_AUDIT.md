# B0-R3 audit (diagnostic only; no Gate, no changes)

Question: is the R3 rho=0.958 partly an artifact of overlapping future windows
between R1(X_t) and R1(X_{t+1})? Four checks below.

## A. Per-action closure
| action | Spearman(d0,d1(u)) | median d1 Q1 | median d1 Q5 |
|---|---|---|---|
| U0 | 0.9346 | 0.02019 | 0.38972 |
| U1 | 0.9474 | 0.0256 | 0.38007 |
| U2 | 0.8997 | 0.03279 | 0.38151 |
| U3 | 0.7512 | 0.04113 | 0.38634 |
| U4 | 0.8781 | 0.0 | 0.2125 |
| U5 | 0.9074 | 0.0 | 0.2125 |
| U6 | 0.8912 | 0.0 | 0.2125 |
| U7 | 0.8807 | 0.0 | 0.2125 |

All 8 actions show a positive monotone trend: min rho=0.751, max rho=0.947.

## B. Do different actions change the successor relation?
Within-state mean distance between successors of different actions:
mean=0.1894 median=0.2043 min=0.0681 max=0.3167 (R1 distances are in [0,1]).

## C. Time-overlap sensitivity
| diagnostic | Spearman | median d0 | median d1 |
|---|---|---|---|
| early (0.5-3.0) | 0.9823 | 0.01647 | 0.03785 |
| mid (3.5-6.5) | 0.9593 | 0.21461 | 0.17347 |
| late (7.0-10.0) | 0.9485 | 0.21814 | 0.16983 |
| successor_tail_abs10.0-11.0 (10.0-11.0) | 0.9242 | 0.15535 | 0.16211 |
| nonoverlap_d0_early_vs_d1_late (0.5-3 vs 8-11) | 0.846 | 0.01647 | 0.16983 |

The clean non-overlap test (d0 on t=0.5-3 vs d1 on t=8-11) gives rho=0.846;
the successor-tail-only test (absolute 10-11 s, no overlap with R1(X) horizon)
gives rho=0.924.

## D. Matching quality
|d0_cross - d0_same_matched|: n=3888 mean=0.0002 median=0.0001 p90=0.0004 max=0.0026; 100.0% within 0.01.

## Answers
1. **Per-action continuous relation?** Yes for all 8 actions (see A; positive,
   monotone Q1->Q5).
2. **Do actions move the state to different successor relations?** See B; the
   within-state cross-action successor distance is reported above (0 would mean
   the action signal is absent).
3. **Is rho driven by future-window overlap?** See C; the non-overlap and
   tail-only correlations quantify how much survives without shared windows.
4. **Is cross/same matching fair?** See D; the initial-distance gap distribution
   is tight, so the 0.988 D1 ratio is a like-for-like comparison.

No PASS/FAIL set; no existing result/R1/distance/action/threshold modified.
Preserved: results/r3/B0_R3_result.md, quantile_statistics.csv,
mechanism_pair_statistics.csv; added per-action aggregate + audit figures.
