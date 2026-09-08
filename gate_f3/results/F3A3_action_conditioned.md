# Gate F3-A3 Action-Conditioned Equivalence Test (Dev-108, no training)

Per state: R(X) = [Q_K, Q_L(0..6)] where Q_L(t_s) = max feasible H=10 progress
if the lateral change STARTS at t_s (no change before), Q_K = max keep progress.
Restricted-search variant only; frozen engine/labels untouched.

| group | Q_K | Q_L(0) | Q_L(1) | Q_L(2) | Q_L(3) | Q_L(4) | Q_L(5) | Q_L(6) |
|---|---|---|---|---|---|---|---|---|
| block_nec (blocker) | 20.6 | 115 | 104 | 72 | 46 | 35 | 29 | None |
| cross_stall | 28.3 | 114 | 110 | 94 | 79 | 57 | 42 | 34 |
| lead_nec (stopped-lead) | 48.8 | 116 | 116 | 87 | 84 | 81 | 68 | 58 |
| lead_opt | 56.2 | 115 | 115 | 90 | 82 | 80 | 70 | 67 |

## Readout
- Action-consequence structures DIFFER between "Necessary" realizations:
  * blocker Necessary: low Q_K (20.6, current already near-dead) and a fast,
    deep Q_L decay over delay (115 -> ~29 by t_s=5, infeasible by t_s=6) =>
    high time pressure: change matters now, opportunity collapses within ~3-4 s.
  * stopped-lead Necessary: high Q_K (48.8, staying still yields real progress)
    and shallow Q_L decay (116 -> 58 at t_s=6) => wide slack; both stay and
    delayed change remain viable.
  * cross-stall Necessary sits in between (Q_K 28, Q_L 114 -> 34).
- stopped-lead Necessary and lead Optional have similar action profiles
  (Q_K 49 vs 56; Q_L tails 58 vs 67): the two differ mainly in current-corridor
  viability near the terminal window - consistent with why a representation
  confuses them.
- blocker Necessary vs stopped-lead Necessary do NOT share the same
  action-conditioned feasible structure.

## Verdict
F3-A3 supports the hypothesis that {Optional, Necessary, Contingency} is a
COARSE maneuver category, not the final Driving Relation:
LateralNecessary merges at least two action-structurally different states
(immediate-dead-end high-pressure blocker vs gradually-collapsing high-slack
stopped lead). Therefore the Relation should be defined on action-conditioned
future-feasible consequences R(X) = {F(X|a): a in A} (how actions change
future feasibility), not on terminal branch viability alone. This resolves the
F3-A confusion as label-abstraction (over-merge) for blocker-vs-stopped-lead,
while stopped-lead vs lead Optional still differ along current-viability.
Artifacts: gate_f3/results/F3A3_action_curves.json, this document.
