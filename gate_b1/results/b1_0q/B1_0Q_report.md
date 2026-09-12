# B1-0Q mechanism-detector blind QC

Sampling: 20 per mechanism (M1-M6), fixed seed 100 (`sample_list.csv`).
Blind to R1/kNN; only trajectories/relative position/speed/heading/lane geometry/
future/evidence were used. Contact sheets: `images/sheet_<mech>.png`.

## Method note
The protocol asks for human/visual QC. A pure vision-model pass on the contact
sheets was unreliable for this fine-grained task (it confused auxiliary tags
with the primary label). We therefore ran an independent, reproducible second
evidence rule (`41_b1_0q_adjudicate.py`, stricter thresholds, no R1) as the
machine adjudication, and kept the visual sheets for human confirmation.

## Machine adjudication (clear_precision = correct/(correct+wrong))
| mechanism | correct | wrong | ambiguous | clear_precision |
|---|---|---|---|---|
| M1_lead_slow_stop | 10 | 2 | 8 | 0.833 |
| M2_vehicle_crossing | 16 | 0 | 4 | 1.000 |
| M3_vru_crossing | 16 | 0 | 4 | 1.000 |
| M4_cut_in | 15 | 0 | 5 | 1.000 |
| M5_merge | 15 | 2 | 3 | 0.882 |
| M6_temp_occupancy | 15 | 0 | 5 | 1.000 |

All mechanisms >= 0.80 (frozen rule) -> detectors frozen.
Lowest are M1 (0.833) and M5 (0.882); main ambiguity is static/parked leads
(M1) and weak merges (M5). No per-sample hand-editing was done.

Per-sample labels: `review_machine.csv`. Human confirmation of the visual
sheets is still recommended before treating the labels as final.
