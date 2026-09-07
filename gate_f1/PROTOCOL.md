# Gate F1 Protocol (frozen 2026-09-06)

Status: supersedes F0 Pilot semantics **only** where marked OVERRIDE. Everything
else reuses the frozen F0 chain unchanged (`gate_f0/feasible/engine.py`,
`gate_f0/recorder/world_recorder.py`, `gate_f0/ego/lane_pid_ego.py`,
`gate_f0/road_segment.json`, corridor/segment geometry). No PlanT.

## Questions F1 answers
1. Do different physical scenes produce the same feasible structure?
   X_A != X_B but F(X_A) ~ F(X_B)  (A1 pedestrian vs A2 crossing vehicle).
2. Does the same scene class produce different structures when the feasible
   alternatives differ? (B1 vs D1: static blocker, left free vs left blocked).
Conclusion must come from future-feasible space, not scenario names.

## Frozen quantities (do not change)
- H = {2,4,6,8,10} s ; fine step 0.5 s ; G0=(P0(10)-P0(8))/2, GL likewise.
- Engine: accel {-4,-2,0,1.5}, v_max 12, T_LC 3.0, margin 0.5,
  ego half-extent (2.2,1.0); P monotonic best-ever; corridor-local occupancy.

## DECISION FRAME (OVERRIDE of F0 interaction-onset)
- t0 = scenario-active start = first recorded frame after preparation.
- Preparation: ego spawned, accelerates to v_target, then holds
  |v - v_target| < 0.5 m/s for >= 1.0 s.
- Pre-warmup motion is NOT part of the sample (discarded from analysis).
- Ego s0 = 0 at t0. Occupancy anchored to t0 with scripted trigger offsets.
- t0 is uniform for all 8 classes so A-class samples show pre-closure growth
  and B/D show suppressed-from-start.

## Class structure & expected (G0, GL) quadrant
| class | physics | expected |
|-------|---------|----------|
| A1 pedestrian crossing | temp closure then reopen | G0>0 (any GL) |
| A2 vehicle crossing | temp closure then reopen | G0>0 |
| B1 single static blocker | left free | G0~0, GL>0  LateralNecessary |
| B2 stopped queue (c0) | left free | G0~0, GL>0 |
| C1 slow lead car | left free, c0 movable | G0>0, GL>0 LateralOptional |
| C2 slow two-wheeler (fallback slow vehicle ok) | | G0>0, GL>0 |
| D1 static + left stream no gap | both dead | G0~0, GL~0 Contingency |
| D2 double-lane stopped queue | both dead | G0~0, GL~0 Contingency |

## Per-sample procedure
CARLA boot (Town12) -> spawn ego (hero, Lane-PID) -> accelerate ->
speed band hold 1 s -> t0 (record start) -> trigger actors by deterministic
offsets -> record >= 10 s at 20 Hz -> destroy.

Trigger rules:
- A1/A2: conflict at s = d_conflict ahead of ego at t0. Trigger window OVERRIDE
  (smoke 00 found the literal Te-1 start lands after the ego's earliest reachable
  pass for every group -> would read FREE; use bracketing instead):
      Te   = d_conflict / v_target            (cruise-hold arrival)
      tmin = earliest reachable arrival under accel 1.5
      occupancy window = [tmin - 1.0 s, max(Te + 1.0, tmin + 2.5) s]
  Window starts before the fastest reachable pass and ends after the cruise pass;
  crossing actor in-lane over this window then leaves. (A2 physical realization:
  00_smoke found NO drivable junction crosses the frozen segment -> kinematic
  crossing vehicle per approved decision; no junction path needed.)
- All others: static/queue/lead exist from t0.

## Offline analysis (3 engine runs per sample, core engine untouched)
1. current corridor  -> P0(H)
2. left change       -> PL(H)
3. baseline no actors-> Pfree(H)
Normalized: P^0(h)=P0(h)/Pfree(h), P^L(h)=PL(h)/Pfree(h).
Pfree shares same road geometry, ego initial state and dynamics.

## Implementation notes (frozen 2026-09-06, smoke-tuned)
- EGO DRIVE (OVERRIDE): CARLA PID physics was non-repeatable (reaches only
  ~4.6-5.7 m/s despite targets 6-9; probe full-throttle gave ~0). Ego is now a
  deterministic kinematic vehicle (ramp a=1.5 -> cruise at v_target ->
  gap brake sqrt(2*2.5*(gap-3)) before obstacles; set_transform each tick).
  Engine reads only (v0,s0) + recorded occupancy, so results are unaffected.
- PREP gate: t0 requires |v-v_target|<0.2 (kinematic exact) for >=1.0 s with
  clear road (nearest prop ahead > 18 m); obstacle distances chosen so this
  fits before the brake zone.
- LAT MIRROR: on this frozen segment the recorded 'cl' lane is physically at
  lat=-W; engine models the alternative at +W, so recorded occupancy lat is
  negated into the engine frame (mirrors the right-hand lane to the engine's
  left). Current-lane blocking is sign-symmetric and unaffected.
- SPAWN SAFE WINDOW: CARLA try_spawn on this segment is only reliable for
  station <= ~80 (beyond ~85 off-drivable geometry). Static/lead/queue objects
  live in stations 16..78; spawn falls back across a station grid then anchors
  every tick to the intended pose.
- CROSSING WINDOW (A1/A2): arming happens at t0 against the ego's *remaining*
  distance (d_conflict - ego_s0) using engine accel reach; window brackets
  [tmin_r - (0-lat0)/1.6 ... ] so the crossing actor is in-lane across the
  earliest reachable pass. Crossing prop spawns off-shoulder candidates then is
  teleported to the conflict law every tick.
- D1 "no-safe-gap": realized as slow CL platoon (1.5 m/s, stations 30..78,
  5 cars) that keeps the merge window occupied through the 10 s horizon;
  D2 = stopped queues on both lanes.
- Data: results/<scene>/run<g>.ndjson (20 Hz), run<g>.summary.json
  (metrics + fine series), f1_all_summary.csv. Offline per run = 3 FROZEN
  engine passes (P0/PL with recorded occupancy, Pfree with actors removed).

## Acceptance
Round 1: 8 scenarios x 5 deterministic groups = 40 runs.
A scenario passes round 1 if >=4/5 fall into expected quadrant/structure.
If a scenario has only 2-3/5, STOP gathering data and inspect: boundary-state
physics vs unstable computation (not "tune to 100%").
Non-passing instances are KEPT and explained by state (e.g., ego could pass
before closure) - they are evidence, not noise.

## Artifact layout
results/<scenario>/run<group>.ndjson (raw 20 Hz)
results/<scenario>/run<group>.summary.json (one-line metrics + fine series)
figures/{f1_quadrants.png, P_t_classes.png, same_structure_cross_scene.png,
        same_scene_diff_structure.png}
