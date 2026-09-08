# F3-A lead-fold diagnostics (no model/gate change; 108 now diagnostic/dev)

Fold test=lead (36 blind: lead_opt 12 / lead_nec 12 / lead_cont 12),
train = cross + block + temp (72). Frozen config; single re-run.

## 1) Confusion (rows=true -> cols=pred = nearest train sample)
| true \ pred | Optional | Necessary | Contingency |
|---|---|---|---|
| Optional | 12 | 0 | 0 |
| Necessary | 12 | 0 | 0 |
| Contingency | 0 | 0 | 12 |

The lead-fold failure is a clean, single error mode: ALL stopped-lead Necessary
are mapped to Optional. Contingency and Optional generalise (each 12/12).

## 2) Distance to structure boundary (eps=0.1) for the 12 errors
Every error: G0=0.00, GL=12.38 -> |G0-eps|=0.10, |GL-eps|=12.28.
Errors are FAR from the GL boundary and sit exactly AT the G0 eps boundary.
=> NOT label noise. The discrete (G0,GL) label of these samples is clean and
far from ambiguity; they are still embedded as Optional.

## 3) Necessary formation transients (mean P0/Pfree by t, sampled every 1 s)
- block_nec : 1.0 1.0 0.9 0.6 0.4 0.3 0.3 0.2 0.2 0.2   (immediate saturation)
- lead_nec  : 1.0 1.0 1.0 1.0 0.9 0.8 0.7 0.6 0.5 0.4   (grow -> decel -> late sat)
- cross_stall:1.0 1.0 1.0 0.8 0.6 0.5 0.4 0.3 0.3 0.3   (middle)
LateralNecessary is realised by >=2 distinct temporal formation modes
(immediate vs gradually collapsing); the stopped-lead case is a
terminal-window boundary (G0~0 appears only near t=8-10).

## 4) Embedding geometry of stopped-lead Necessary (query n=12)
mean embed-distance to ...
  lead_opt (blind)   0.129
  lead_cont (blind)  1.835
  block_nec (train)  3.226
  cross_stall (train) 3.041
Stopped-lead Necessary sits 25x closer to lead Optional than to the OTHER
Necessary sources. The learned embedding has retained mechanism identity for
the lead family; it aligned by absolute t=0.5..10, so lead's gradual saturation
signature dominates over the (terminal) decision distinction.

## Verdict on the three hypotheses
- (A) label-boundary noise: NO (errors are far from GL boundary, clean labels).
- (B) temporal misalignment / mechanism-signature dominance: YES - the absolute
  time-aligned elementwise signal makes stopped-lead Necessary look like lead
  Optional; mechanism, not decision, dominates the embedding.
- (C) Necessary is multi-modal in formation: PARTIAL - immediate vs gradually
  collapsing modes coexist; a terminal-window-only distinction is what separates
  lead Optional from lead Necessary.
Conclusion for next direction: representation (B), not structure-definition
(A). Reconsider event/onset-relative representation (suppression onset,
saturation onset, reopen) rather than absolute-t elementwise channels. The
108-set is now diagnostic/development; any strong re-validation needs a NEW
untouched confirmatory set.
