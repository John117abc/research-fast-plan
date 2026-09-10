# Gate B0-R1 diagnostic (development only, Dev-108)

R1(X) = {V0^u(t), VL^u(t)} for u in U0..U7, t=0.5..10s (320 values),
normalized by matched free baseline. Frozen stopping rule: {'max_cluster': 5, 'min_distinct': 90, 'min_sep_ratio': 1.0}.

## Diversity
- values per state: 320
- unique (round 3): 107 / 108; largest cluster: 2
- unique (round 2): 107 / 108; largest cluster: 2
- all-ones-like states (every V>=0.999): 0

R0 reference: unique (round 3)=57/108, largest cluster=47, all-ones-like=47.

## Group separability (between/within mean distance)
| pair | R1 ratio | R0 ratio |
|---|---|---|
| lead_nec|lead_opt | 1.122 | nan |
| block_nec|lead_opt | 2.643 | 1.283 |
| block_nec|lead_nec | 3.129 | 1.283 |
| block_nec|cross_stall | 1.545 | 1.195 |
| cross_stall|lead_opt | 2.180 | 1.051 |
| cross_stall|lead_nec | 2.900 | 1.051 |

lead_opt vs lead_nec: R1=1.122 (R0=nan)

## block_nec current-corridor decay (mean V0, U2 keep ax=0)
- t where mean V0 first < 0.5: block_nec=9, lead_nec=18, lead_opt=None

## Verdict (frozen rule)
- diversity recovered: True
- lead_opt/lead_nec separated: True
- **R1_DEGENERACY_RESOLVED**

Scope note: this round only tests whether R1 resolves R0's information
collapse. No new features, no scene-parameter changes, no training, no
closure Gate. Labels used only as post-hoc visualization groups.
