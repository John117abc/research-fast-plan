# Gate F2 Protocol - Cross-Scenario Structure Reuse (draft frozen 2026-09-07)

Goal (one sentence): break the 1:1 mapping scenario -> structure category.

F1 showed structure categories co-vary strongly with scenes. F2 deliberately
asks whether the REPRESENTATION, not the label, captures structure:
  (scene, state) -> Z_F -> structural relation

## Representation (NOT reduced to (G0,GL))
Full normalized feasible frontier per state i:
  Z_F^i = [ P^0_i(t1..tN), P^L_i(t1..tN) ],  P^x = P_x(t)/P_free(t),
  t = 0.5, 1.0, ..., 10 s (N=20 each; corridor-dead PL entries -> 0).
(G0,GL) is kept only as an explanatory label for the write-up.

## Retrieval task (leave-family-out)
For every state i with physical family f(i):
  - candidate pool excludes all states of family f(i);
  - rank candidates by distance in Z_F space (Euclidean on z-scored dims);
  - decide if nearest neighbors share i's structure class.
Physical families = scenario class (A1 pedestrian, A2 vehicle crossing,
B1 single blocker, B2 stopped queue, C1 slow lead car, C2 slow two-wheeler,
D1 blocker + left platoon, D2 double queue). A mechanism-family view
(cross=A1+A2, blocked=B1+B2+D1+D2, lead=C1+C2) is also reported.

## Success criteria (the F2 claim)
Stable inequality over the dataset:
  mean d(different scene, SAME structure) < mean d(same scene, DIFFERENT structure)
  (i.e. structure, not scene, is the dominant geometry of Z_F), plus a clear
  leave-family-out k-NN structure hit-rate above pool baseline.

## Input
Reuses F1 frozen data: gate_f1/results/<scene>/run<g>.summary.json (80 samples)
and f1_all_summary.csv for labels. No new CARLA for this first evidence pass.
State-variation extension (more within-scene structural variety, e.g.
near-stationary slow lead -> Necessary) is a follow-up dataset expansion, NOT a
method change.
