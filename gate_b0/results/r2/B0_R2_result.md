# Gate B0-R2 result: R1 one-step closure (Dev-108)

**STOPPED at pair construction: G1 FAIL.** Per protocol sections 2 and 8,
closure was NOT run and B0-R3 two-step was NOT entered.

## G1 candidate equivalence: FAIL
- |Peq| = **11** (frozen floor 15).
- Coverage was satisfied: 6 fine-mechanism pairs (floor 3), 3 coarse-mechanism combos (floor 2).
- Bottleneck: only **11 mutual cross-mechanism nearest-neighbour pairs exist at all** before any filter, so the count floor cannot be met.
- Peq R1 d0: min=0.0000 median=0.0060 max=0.0240; cross-pair bottom-10% threshold=0.0320.

## Candidate pairs (auto, no manual selection)

- `block_cont_r10` ~ `cross_stall_occ_r3` (block_cont | cross_stall_occ) d0=0.0240
- `block_cont_r7` ~ `cross_stall_occ_r11` (block_cont | cross_stall_occ) d0=0.0000
- `block_nec_r10` ~ `cross_stall_r9` (block_nec | cross_stall) d0=0.0060
- `block_nec_r12` ~ `cross_stall_r12` (block_nec | cross_stall) d0=0.0050
- `block_nec_r4` ~ `cross_stall_r11` (block_nec | cross_stall) d0=0.0032
- `cross_stall_r2` ~ `lead_nec_r1` (cross_stall | lead_nec) d0=0.0079
- `cross_stall_r6` ~ `temp_opt_r9` (cross_stall | temp_opt) d0=0.0038
- `cross_stall_occ_r10` ~ `lead_cont_r11` (cross_stall_occ | lead_cont) d0=0.0168
- `cross_stall_occ_r2` ~ `lead_cont_r1` (cross_stall_occ | lead_cont) d0=0.0011
- `lead_opt_r11` ~ `temp_opt_r2` (lead_opt | temp_opt) d0=0.0069
- `lead_opt_r12` ~ `temp_opt_r3` (lead_opt | temp_opt) d0=0.0070

## Gates
| Gate | Result |
|---|---|
| G1 candidate equivalence | FAIL |
| G2 closure vs random cross | not run |
| G3 vs same-mech matched | not run |
| G4 keeps separation | not run |
| overall | FAIL (stopped) |

## Interpretation
R1 is non-degenerate (107/108 unique; lead_opt/lead_nec separated), but on
Dev-108 the frozen cross-mechanism candidate rule (mutual NN + bottom-10%
d0 + distinct param group) yields only 11 pairs. So R1 does not yet form
enough stable cross-mechanism repeated structure to justify a closure test.
This is the protocol's G1-FAIL case: stop; do not modify R1, distance,
thresholds or action set in response to this result.

## Not run
- one-step closure (r2_closure_*.csv)
- matched/random closure controls
- B0-R3 two-step closure

Figures: results/r2/figures/r2_fig1_d0_distribution.png,
r2_fig2_peq_d0.png.
