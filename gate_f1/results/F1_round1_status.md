# Gate F1 Round-1 Pilot Result (40 deterministic runs, fresh 2026-09-07)

CARLA 0.9.15 / Town12 / frozen 208 m segment / Lane-PID-free deterministic
kinematic ego / 20 Hz recorder / FROZEN F0 offline engine (H=10, G=(P10-P8)/2).

## Acceptance (>=4/5 per scene): PASS
| scene | physics | n | observed quadrants | pass |
|-------|---------|---|--------------------|------|
| A1 | pedestrian crossing | 5 | LateralOptional ×4, Contingency ×1 | 4/5 True |
| A2 | crossing vehicle | 5 | LateralOptional ×4, Contingency ×1 | 4/5 True |
| B1 | single static blocker | 5 | LateralNecessary ×5 | 5/5 True |
| B2 | stopped queue (c0) | 5 | LateralNecessary ×5 | 5/5 True |
| C1 | slow lead car | 5 | LateralOptional ×5 | 5/5 True |
| C2 | slow two-wheeler/vehicle | 5 | LateralOptional ×5 | 5/5 True |
| D1 | static + left slow platoon | 5 | Contingency/Wait ×5 | 5/5 True |
| D2 | double-lane stopped queue | 5 | Contingency/Wait ×5 | 5/5 True |

Total 38/40 with the expected archetype. Precise reading (do NOT reduce to
"2 wrong samples"):

- The only 2 non-expected samples (A1 g4 and A2 g4) come from the SAME
  parameter group (v_target=9, remaining distance to the conflict point
  ~7-9 m at decision). At that initial state the ego is already inside the
  non-braking region (kinematically verified: distance < v^2/(2*a_max) to the
  closure), so there is NO recoverable branch on the current corridor and no
  alternative either -> (G0,GL) ~ (0,0) -> Contingency, in BOTH pedestrian and
  vehicle physics.
- These are therefore treated as a STATE-INDUCED STRUCTURAL TRANSITION, not as
  misclassification: same crossing physics, different initial state -> different
  feasible topology. This is exactly the claim that structure is a function of
  the interaction state, not of the scenario label. They are kept and reported.

Evidence-strength ordering for the write-up (Round-1):
  (a) STRONGEST  B1/B2 vs D1/D2: current corridor blocked in both; only the
      ALTERNATIVE future branch differs -> LateralNecessary vs Contingency.
      Similar current physical appearance => different structure (fig4).
  (b) SECOND     A1 vs A2: different physical entities, same normalized P^0(t)
      restricted-then-reopen evolution and same quadrants (fig3); g4 transition
      reproduces identically across both physics.
  (c) TOOL NOT   the (G0,GL) quadrant is the representation, not itself the
      EVIDENCE   evidence; the evidence is whether pre-built future-structure
      conditions separate, and whether different physics with the same future
      structure meet.

## Answers to the three F1 questions
1. Different physics -> same structure: A1 vs A2 both produce temporary-closure
   then reopen on the current corridor (see f1_same_structure_cross_scene.png,
   normalized P^0 curves); quadrants identical except state-boundary g4.
2. Same scene start -> different structure by feasible alternative:
   B1 (static blocker, left free) = LateralNecessary vs D1/D2 (static blocker,
   left blocked) = Contingency (f1_same_scene_diff_structure.png). Static
   blocker + "change" rule would mislabel both; (G0,GL) separates them.
3. Structure from future-feasible space, not scenario name: all eight classes
   map cleanly onto the (G0,GL) quadrant topology (f1_quadrants.png):
     A/C: G0>0            (current alive)
     B:   G0~0, GL>0      LateralNecessary
     D:   G0~0, GL~0      Contingency
   P(t) shapes differ correctly: temp closure plateau-reopen (A), saturation
   with alternative (B), slow-but-sustained (C), both saturated (D) - see
   f1_P_t_classes.png.

## Artifacts
gate_f1/results/<scene>/run<g>.ndjson        (raw 20 Hz)
gate_f1/results/<scene>/run<g>.summary.json  (per-run metrics + fine series)
gate_f1/results/f1_all_summary.csv
gate_f1/figures/{f1_quadrants,f1_P_t_classes,f1_same_structure_cross_scene,
                f1_same_scene_diff_structure}.png
