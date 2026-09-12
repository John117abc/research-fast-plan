# B1-0 adaptation check — result (Steps 1-6 complete; Step 7 NOT run)

Environments: `plant2` (engine/R1/CARLA audit), `waymo_rc` (TFRecord parsing only),
connected via canonical_state JSON. No R1/collision/feasible logic in waymo_rc.

## Step 1 — CARLA H=8s compatibility audit: PASS
Frozen 72 confirmatory states; horizon 10s -> 8s (`R_1^{8s}`, 256 dims).
- Spearman(d_R8s, d_R10s) = **0.996** (criterion >=0.90)
- C1-C4 all PASS at 8s: rho=0.953 CI [0.934,0.968]; median D1 Q1=0.0109/Q5=0.2691;
  matched ratio 0.972; mechanism rho 0.971/0.934/0.952.
- Artifact: `step1_carla_h8/`.

## Step 2 — JSON <-> official TFRecord consistency: PASS
- 60/60 seeded samples consistent (scenario_id, sdc_id, ego pose/vel, bbox,
  tracks/frames/lanes counts all exact; mapping
  `tfrecord-XXXXX-of-01000_<idx>.json` -> record `<idx>`).
- Canonical (raw parse + lane topology) exported to `gate_b1/canonical/`.
- Artifact: `step2_json_tfrecord/`.

## Step 3 — official WOMD lane-neighbor recovery: PASS
Resolution of the earlier blocker: use official `lane.left_neighbors` +
`self_start/end_index` and the real neighbor polyline over
`neighbor_start/end_index` (NO shifted/fabricated lane). Also fixed the Waymo
lateral handedness (left = `(sin h, -cos h)`) and excluded the ego from occupancy.
- 72 canonical states: **14 with a valid official left neighbor (19.4%)**;
  58 excluded with `no_valid_left_neighbor` (no in-range, left-side,
  same-direction, future-covering neighbor).
- **0 left/direction errors**: all selected neighbors have lateral +2.7..+4.1 m
  and heading diff < 3 deg; no right-side or reverse lane selected.
- Artifacts: `step3_lane_detector/{left_neighbor_smoke.csv,
  left_neighbor_candidates.json, connectivity_evidence.json}`.

## Step 4 — M1-M7 mechanism detectors smoke: PASS (engineering)
1500 random JSON states; primary mechanism distribution (non-empty 81.9%):
M1_lead 328, M2_veh_cross 308, M4_cut_in 254, M5_merge 225, M3_vru_cross 61,
M6_temp_occ 52, M0_none 272. `primary_mechanism`, `auxiliary_mechanism_tags`,
`detector_evidence` saved; 20 samples/mechanism dumped for human QC.
- Artifact: `step4_mechanism/` (M7 left-opportunity needs the left lane; to be
  applied on the neighbor-valid subset in formal B1).

## Step 5 — interaction_actor_ids / free baseline smoke: PASS
14 neighbor-valid states: interaction actors via swept-bbox x current/left
corridor band (same margin 0.5 / ego half-width 1.0); mean 6.2, max 14;
free baseline removes ONLY these actors (never all traffic).
- Artifact: `step5_free_baseline/`.

## Step 6 — full R1^8s on 10 real Waymo states: PASS (engineering)
Fixed engine semantics (Waymo-left lat, ego excluded from occupancy).
- 10/10 states computed `R_1^{8s}` (256 dims); all V in [0,1]; mean V ~0.51;
  no NaN; curves saved.
- Artifact: `step6_r1/` (`r1_8s_waymo_smoke.csv`, `r1_8s_curves.json`, figure).

## Step 7 — formal B1 (300-500 states): NOT RUN (per instruction).

No change was made to the frozen R1 math, distance, actions, or CARLA results.
Adapter-only fixes: Waymo lateral handedness; ego excluded from occupancy.
