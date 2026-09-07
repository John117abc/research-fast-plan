# Gate F1 Round-2 Confirmatory Result (80 samples, frozen config)

FROZEN confirmatory set: parameter groups 6-10 x 8 scenes = 40 new recordings
added to the 40 calibration recordings (Round-1) = 80 total. No mechanism or
parameter changed between Round-1 and Round-2 (see F1_round2_freeze.md).

## Per-scene structure (10 samples each)
| scene | expected | observed quadrants | notes |
|-------|----------|--------------------|-------|
| A1 | G0>0 | LateralOptional ×9, Contingency ×1 (g4) | state transition reproduces |
| A2 | G0>0 | LateralOptional ×9, Contingency ×1 (g4) | same state transition |
| B1 | GL>0 | LateralNecessary ×10 | |
| B2 | GL>0 | LateralNecessary ×10 | |
| C1 | both>0 | LateralOptional ×10 | |
| C2 | both>0 | LateralOptional ×10 | |
| D1 | both~0 | Contingency/Wait ×10 | |
| D2 | both~0 | Contingency/Wait ×10 | |

78/80 with the pre-built expected archetype. The only two non-expected samples
(A1 g4, A2 g4) are the SAME state-induced structural transition already seen in
Round-1: v_target=9, remaining distance to conflict ~7-9 m at decision, inside
the non-braking region -> no recoverable branch on current or alternative ->
(G0,GL)=(0,0) -> Contingency, identically in pedestrian and vehicle physics.
They are KEPT and reported as structure evidence (f1_state_induced_transition.png).

## Confirmatory evidence (frozen, no post-hoc tuning)
1. Same current obstruction, different alternative -> different structure:
   B (current blocked, left free) = LateralNecessary vs D (current blocked,
   left blocked) = Contingency, 10/10 each.
   Similar current physical appearance does NOT imply the same driving
   structure (f1_same_scene_diff_structure.png).
2. Different physics, same future structure: A1 vs A2 (pedestrian vs crossing
   vehicle) -> same normalized restricted-then-reopen P^0 evolution and same
   quadrants incl. the joint g4 transition
   (f1_same_structure_cross_scene.png).
3. Structure varies with state, not scenario label: within the SAME physics
   (A1), g1 (normal) = temporary-closure-reopen while g4 (too close + fast)
   = Contingency (f1_state_induced_transition.png). Relation = f(state),
   not f(scenario class).

## State-of-evidence
These 80 samples provide controlled evidence of REUSABLE feasible-future
structure (scripted CARLA, oracle future, predefined corridor, handcrafted
feasible search). They answer "is this structure worth learning?" affirmatively
and set up the next decision: whether to proceed to a
Cross-Scenario Reuse / Relation-Learning stage.
