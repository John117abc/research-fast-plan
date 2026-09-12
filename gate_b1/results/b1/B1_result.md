# Gate B1 result: structural existence in real Waymo data

R1^8s (256 dims), all cross-mechanism pairs, k=5, 10000 label permutations (seed 100).
Fixed engine; mechanism labels only for stratification.

## Coverage / health
- states: 480; mechanisms: 6 {'M6_temp_occupancy': 80, 'M2_vehicle_crossing': 80, 'M1_lead_slow_stop': 80, 'M3_vru_crossing': 80, 'M4_cut_in': 80, 'M5_merge': 80}
- unique signatures (round 3): 365 / 480; all-ones states: 0
- median cross-mech distance = 0.2164; median same-mech = 0.1947

## kNN cross-mechanism ratio
- observed = 0.7025; permutation mean = 0.8351 (std 0.0088); z=-15.02; p(obs>=null)=1.0000
- mechanism-pair edge shares: {'M5_merge|M6_temp_occupancy': 111, 'M2_vehicle_crossing|M6_temp_occupancy': 135, 'M2_vehicle_crossing|M3_vru_crossing': 109, 'M2_vehicle_crossing|M5_merge': 149, 'M4_cut_in|M6_temp_occupancy': 131, 'M3_vru_crossing|M6_temp_occupancy': 123, 'M1_lead_slow_stop|M5_merge': 72, 'M1_lead_slow_stop|M4_cut_in': 89, 'M1_lead_slow_stop|M6_temp_occupancy': 66, 'M3_vru_crossing|M4_cut_in': 91, 'M3_vru_crossing|M5_merge': 51, 'M1_lead_slow_stop|M3_vru_crossing': 92, 'M4_cut_in|M5_merge': 231, 'M1_lead_slow_stop|M2_vehicle_crossing': 62, 'M2_vehicle_crossing|M4_cut_in': 174}; top-pair share = 0.137

## Within-mechanism diversity
| mechanism | n | median | p90 |
|---|---|---|---|
| M1_lead_slow_stop | 80 | 0.22123 | 0.38054 |
| M2_vehicle_crossing | 80 | 0.2109 | 0.34563 |
| M3_vru_crossing | 80 | 0.17599 | 0.36701 |
| M4_cut_in | 80 | 0.189 | 0.34828 |
| M5_merge | 80 | 0.16877 | 0.34033 |
| M6_temp_occupancy | 80 | 0.20077 | 0.34122 |

## Pre-registered support rules
| rule | met |
|---|---|
| at_least_4_mechanisms | True |
| not_separated_by_mechanism | False |
| not_single_pair | True |
| within_diversity_nontrivial | True |

## Verdict: **B1-WEAK**

Interpretation: R1^8s carries statistically significant mechanism-related
structure (same-mechanism neighbours are enriched vs the label-permutation
null, z=-15.02), so the pre-registered SUPPORT condition 'cross-mechanism
nearest neighbours significantly exceed random' is NOT met. At the same time,
cross-mechanism repetition clearly exists: 70.2% of k=5 neighbours are
different-mechanism, all 15 mechanism pairs contribute (top share 0.14), and
some cross pairs are exactly identical (e.g. M1 lead ~ M2 vehicle crossing, d=0).
So the result is partial (WEAK), not a clean SUPPORT nor a clean mechanism split.

Representative pairs: results/b1/cross_mechanism_neighbor_stats.json (cross nearest 10; same farthest 10). Figures: figures/.

