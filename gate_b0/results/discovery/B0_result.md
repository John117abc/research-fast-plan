# Gate B0 (discovery) result

Data: Dev-108 (F3), no new data, no training. Action set U0-U7
(keep/left x ax in {-4,-2,0,+1.5}), forced 1 s then free 9 s, H=10 s.

## Gate verdict
- **G0 engineering health: PASS** (108/108 signatures, no NaN, Q_free>0 for all
  actions, 0 V_raw>1.02, START_LEFT successor stays CHANGING_LEFT tau=1.0,
  occupancy rebased at t0+1s from the 20 Hz GT).
- **G1 candidate equivalence: FAIL** — `|Peq|=3` (<15), fine-mechanism pairs=3
  (>=3 ok), coarse-mechanism combos=1 (<2).
- G2/G3/G4 computed for completeness but not meaningful at `|Peq|=3`.
- **Overall discovery: FAIL. Per protocol §24 Case A: STOP; do not train a network.**

## Root cause: R0 is degenerate
`Q_X(u) = max` progress after forcing u for 1 s, then free search. Because the
free search may still initiate a lane change, whenever the left lane is free the
ego can always take the lateral escape, so `V ~ 1` for both Optional and
Necessary. Consequences:

- 108 states -> only **57 unique R0 signatures**; **47/108 are the all-ones
  signature** `V=[1,1,1,1,1,1,1,1]`.
- All-ones by fine mechanism: `lead_nec 12/12`, `lead_opt 12/12`,
  `temp_opt 10/12`, `cross_stall 9/12`, `block_nec 4/12`.
- So R0 merges the exact distinction the research cares about
  (Optional vs Necessary) and does not need any learned representation to do so;
  the 10th percentile of cross-pair `d0` is exactly `0.0`, so the frozen
  mutual-NN + bottom-10% rule can only admit `d0=0` pairs -> 3.

The 3 Peq pairs (all `d0=0`, i.e. identical R0) are:
`block_cont_r7__cross_stall_occ_r11`, `block_nec_r10__cross_stall_r1`,
`cross_stall_r11__temp_opt_r12`.

## Interpretation
The failure is **not** a representation-capacity problem; it is the definition of
the action consequence. A scalar max-progress under a free continuation cannot
express:
1. which corridor the future uses (current vs alternative), and
2. the *timing / recourse structure* of the lateral option (now-or-never vs
   wide slack), which F3-A3 already showed separates blocker-Necessary from
   stopped-lead-Necessary.

This matches protocol §24 Case B's "missing consequence" list (recourse timing,
which branch), but occurs before closure, i.e. as a Case-A-style failure of R0.

## Not run
- B0-7 two-step closure (only after one-step PASS).
- Confirmatory generation (only after discovery PASS).
