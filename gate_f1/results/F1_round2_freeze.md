# Gate F1 Round-2 Freeze (confirmatory run)

Decision (2026-09-07): proceed to Round-2 (parameter groups 6-10 x 8 scenes = 40
recordings) with the F1 mechanism and Round-2 parameters FROZEN.

## Calibration / Confirmatory split
- **Round-1 = calibration / development set.** It absorbed: dt-integration fix,
  kinematic ego motion, lateral mirror, spawn-distance window, parameter
  bounds probing. Round-1 results are development evidence only.
- **Round-2 = frozen confirmatory set.** From this point on the pipeline and
  all parameters are frozen. NO further changes will be made in order to push a
  sample into its expected quadrant.

## Frozen quantities (Round-2 and beyond)
simulation H={2,4,6,8,10}s, G=(P10-P8)/2, dt=0.5;
engine accel {-4,-2,0,1.5}, v_max=12, lane-change 3.0s, margin 0.5,
ego half-extent (2.2,1.0); decision t0 = stable-kinematic-cruise start;
parameter groups 6-10 exactly as in config/parameter_table.yaml (v8/v9
distances pre-set during calibration are part of the frozen parameter set).

## Interpretation commitments (how Round-2 evidence is read)
1. g4-type instances are NOT errors. When a sample falls outside its expected
   quadrant, first check whether it is a legitimate state-induced structural
   transition (e.g. A crossing from too-close-and-fast -> no recoverable branch
   -> Contingency in BOTH pedestrian and vehicle physics). Such samples are
   KEPT and reported as structure evidence, never tuned away.
2. Only infrastructure anomalies justify a re-run: CARLA spawn failure, actor
   overlap at spawn, ego initialization anomaly, or obvious scenario-definition
   violation. These are re-run; structural deviations are recorded.
3. Evidence strength ordering for the write-up:
   (a) B vs D  : same current obstruction, different alternative -> different
                 structure  (similar physical appearance != same structure);
   (b) A1 vs A2 : different physics -> similar feasible-future evolution;
   (c) (G0,GL) quadrant is a REPRESENTATION tool, not evidence by itself;
       the evidence is whether pre-built future-structure conditions form
       distinct regions and whether different physics with the same future
       structure land in the same region.

## Planned analyses after Round-2 (80 samples)
fig1 cross-scene / same-structure (A1<->A2, normalized P0)
fig2 same-obstacle / different-structure (B<->D; P0 both saturated, PL one
     alive one dead)
fig3 state-induced structural transition (A normal vs A g4: same physics,
     different initial state -> different feasible topology)
