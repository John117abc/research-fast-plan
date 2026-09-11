# B1-0 adaptation check — result (STOPPED at Step 3)

Environments: `plant2` (engine/R1/CARLA audit), `waymo_rc` (TFRecord parsing only),
connected via canonical_state JSON. No R1/collision/feasible logic in waymo_rc.

## Step 1 — CARLA H=8s compatibility audit: PASS
Frozen 72 confirmatory states; horizon truncated 10s -> 8s (`R_1^{8s}`, 256 dims).
Pre-registered criterion: `Spearman(d_R8s,d_R10s) >= 0.90` AND C1-C4 all PASS.

- Spearman(d_R8s, d_R10s) = **0.996**
- Spearman(d0,D1) at 8s = 0.953, 95% CI [0.934, 0.968]
- median D1: Q1=0.0109 vs Q5=0.2691; matched ratio 0.972
- mechanism rho: cross|lead 0.971, block|cross 0.934, block|lead 0.952
- C1-C4 all PASS -> **STEP1 PASS** (artifact: `step1_carla_h8/`).

## Step 2 — JSON <-> official TFRecord consistency: PASS
Seeded 12 samples; `data_json/training/tfrecord-XXXXX-of-01000_<idx>.json`
maps to record `<idx>` of `data/training/training.tfrecord-XXXXX-of-01000`.

- 12/12 scenario_id + sdc_id match; ego dx/dy/dheading/dvx/dvy = 0.0;
  bbox length/width = 0.0; n_tracks / n_frames / n_lanes exactly equal.
- Canonical states exported to `gate_b1/canonical/` (raw parse only).
- Artifact: `step2_json_tfrecord/{check.csv,summary.json}`.

## Step 3 — left-adjacent same-direction lane detection: **DEFINITIONAL BLOCKER**
The frozen B1 requirement is "current lane + left adjacent same-direction lane".
Waymo raw map cannot stably provide this:

1. `lane` features are **fragmented short centerline segments** (typical
   longitudinal span 5-10 m); a single segment is not a corridor.
2. Connectivity (`entry_lanes/exit_lanes`) does not encode lateral adjacency:
   its connected components span intersections and multiple lanes
   (observed component sizes 126-415 segments; lateral std 30-42 m), so
   union-find over connectivity is not "one lane".
3. Naive geometric left-lane detection is unstable:
   - loose rule: 6/12 canonical states "found" a left lane, but offsets
     1.58-1.96 m indicate narrow/bike lanes, not the driving neighbour;
   - strict rule (same driving type, offset 2.5-4.5 m, heading<20 deg,
     lat std<0.8 m, >=40 m overlap): **0/12**.
   - JSON 500-sample coverage: 21.4% "ok" under the loose rule (107 ok,
     386 no_left_lane, 7 no_ego_lane) — but those are the unreliable ones.
4. The reference project `gpudrive/baselines/waymo_reality_check` also avoids
   lateral adjacency: it builds only a single reference path by chaining
   `exit_lanes` from the entry lane (`02_build_reference_path.py`).

Per the agreed stop rule ("左邻车道关系无法稳定恢复 -> 立即停止，不进入正式 B1"),
**B1-0 is STOPPED at Step 3. Steps 4-6 and formal B1 were not run.**

## Options to resolve (need a decision before proceeding)
- **A. Geometric left corridor (recommended, minimal):** keep R1 math frozen,
  define the left corridor as a parallel band offset to the left of the ego
  lane centerline by an estimated lane width (from adjacent road_line/road_edge
  spacing), instead of requiring a topological left lane. Pre-register this as
  the B1 corridor definition; validate lane-width estimate against TFRecord.
- **B. Adopt a lane-graph pipeline:** use a map processor that yields lane
  adjacency (Waymax roadgraph / GPUDrive road graph / custom lane-following with
  lateral neighbour extraction). Larger engineering dependency.
- **C. Curated subset:** restrict to states with unambiguous left lane under a
  stricter detector plus manual verification (not scalable; still needs a
  reliable detector).

No change was made to the frozen R1, distance, actions, or CARLA results.
