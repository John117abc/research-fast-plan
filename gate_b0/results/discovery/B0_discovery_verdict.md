# Gate B0 discovery verdict

G0 engineering health: True
G1 candidate equivalence: False (|Peq|=3, fine pairs=3, coarse combos=1)
G2 one-step closure: True (median D1 Peq=0.0000 vs random-cross=0.2700, ratio=0.000, p=0.0051)
G3 mechanism no extra loss: True (rho=0.000)
G4 keeps same-mechanism-different separation: True (ratio=na)

Overall discovery PASS: False

NOTE: G2/G3/G4 are computed for completeness but are NOT scientific
evidence here: |Peq|=3 is far below the frozen floor (15) and the
few surviving pairs have d0=0 (identical R0), so their D1=0 is
tautological. The gate fails on G1, which is the binding criterion.

## Root cause note (R0 degeneracy)
R0 = max progress per action collapses whenever a safe left lane change is
available: after the forced 1 s, the free search can always resort to the
lateral escape, so V ~ 1 for Optional AND Necessary. Consequence: 47/108
states share the all-ones signature (lead_nec 12/12, lead_opt 12/12), and
the frozen pair rule (mutual-NN + bottom-10% d0) yields only 3 Peq pairs.

Per protocol section 24 Case A: STOP; do not train a network; the missing
consequence is not representation capacity but the R0 definition (scalar max
progress cannot express recourse timing / which corridor is used).
