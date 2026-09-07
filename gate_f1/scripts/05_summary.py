#!/usr/bin/env python3
"""Gate F1 05: the four summary figures from f1_all_summary.csv + run<g>.summary.json.
 fig1 quadrants scatter (G0 vs GL)
 fig2 per-class P0(t)/PL(t) representative run
 fig3 same-structure cross-scene (A1 vs A2 normalized P^0)
 fig4 same-scene different-structure (B1 vs D1 current + alternative)
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "common"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = "gate_f1/figures"
os.makedirs(OUT, exist_ok=True)
EPS = 0.10


def load_rows():
    return list(csv.DictReader(open("gate_f1/results/f1_all_summary.csv")))


def fig1(rows):
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    colors = {"A1": "#c44", "A2": "#e88", "B1": "#4a7", "B2": "#8c9",
              "C1": "#48c", "C2": "#8af", "D1": "#a7a", "D2": "#c7b"}
    for r in rows:
        g0 = float(r["G0"]); gl = r["GL"]
        gl = 0.5 if gl == "" else float(gl)
        ax.scatter([g0], [gl], c=colors[r["scene"]], s=40, alpha=.75,
                   label=r["scene"] if r["group"] == "1" else None)
    ax.axhline(0, color="k", lw=.8); ax.axvline(0, color="k", lw=.8)
    ax.set_xlabel("G0 (current corridor terminal growth, m/s)")
    ax.set_ylabel("GL (alternative corridor terminal growth, m/s)")
    ax.legend(ncol=4, fontsize=8)
    ax.grid(alpha=.3)
    fig.savefig(f"{OUT}/f1_quadrants.png", dpi=140)
    print("fig1 ok")


def fine(scene, group):
    p = f"gate_f1/results/{scene}/run{group}.summary.json"
    if not os.path.isfile(p):
        return None
    return json.load(open(p))


def fig2(rows):
    reprs = {"A1": 1, "B1": 1, "C1": 1, "D1": 1}
    fig, axes = plt.subplots(2, 2, figsize=(9, 7))
    for (sc, g), ax in zip(reprs.items(), axes.ravel()):
        j = fine(sc, g)
        if not j:
            continue
        t = j["fine"]["t"]
        ax.plot(t, j["fine"]["P0"], "-o", ms=2.5, label="P0 (current)")
        ax.plot(t, [x if x is not None else float("nan") for x in j["fine"]["PL"]],
                "-s", ms=2.5, label="PL (alternative)")
        ax.set_title(f"{sc}  quadrant={j['quadrant']}")
        ax.set_xlabel("t (s)"); ax.set_ylabel("reachable s (m)"); ax.legend(fontsize=7)
        ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/f1_P_t_classes.png", dpi=140)
    print("fig2 ok")


def fig3(rows):
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for sc, col in (("A1", "#c44"), ("A2", "#e88")):
        j = fine(sc, 1)
        if not j:
            continue
        P0 = j["fine"]["P0"]; Pf = j["fine"]["Pfree"]
        norm = [a / b if b > 0 else None for a, b in zip(P0, Pf)]
        ax.plot(j["fine"]["t"], norm, f"-o", ms=2.5, c=col, label=sc)
    ax.set_title("Same feasible structure from different physics (A1 pedestrian vs A2 vehicle)")
    ax.set_xlabel("t (s)"); ax.set_ylabel("normalized P^0(t) = P0/Pfree")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/f1_same_structure_cross_scene.png", dpi=140)
    print("fig3 ok")


def fig4(rows):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for sc, ax in (("B1", axes[0]), ("D1", axes[1])):
        j = fine(sc, 1)
        if not j:
            continue
        t = j["fine"]["t"]
        ax.plot(t, j["fine"]["P0"], "-o", ms=2.5, label="P0 (current)")
        ax.plot(t, [x if x is not None else float("nan") for x in j["fine"]["PL"]],
                "-s", ms=2.5, label="PL (alternative)")
        ax.set_title(f"{sc}  ({j['quadrant']})")
        ax.set_xlabel("t (s)"); ax.legend(fontsize=8); ax.grid(alpha=.3)
    fig.suptitle("Same scene start (static blocker), different alternative -> different structure")
    fig.tight_layout()
    fig.savefig(f"{OUT}/f1_same_scene_diff_structure.png", dpi=140)
    print("fig4 ok")


def fig5(rows):
    """State-induced structural transition: same crossing physics (A1), normal
    state (g1) vs non-braking state (g4) -> different feasible topology."""
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    jn = fine("A1", 1)
    js = fine("A1", 4)
    if jn and js:
        t = jn["fine"]["t"]
        ax.plot(t, jn["fine"]["P0"], "-o", ms=2.5, c="#2a7",
                label=f"A1 g1 normal  ({jn['quadrant']}, G0={jn['G0']:.1f})")
        ax.plot(t, js["fine"]["P0"], "-s", ms=2.5, c="#c33",
                label=f"A1 g4 too-close-fast ({js['quadrant']}, G0={js['G0']:.1f})")
        ax.axhline(0, color="k", lw=.6)
    ax.set_title("A1 pedestrian crossing: state-induced structural transition")
    ax.set_xlabel("t (s)"); ax.set_ylabel("P0(t) (reachable s)")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/f1_state_induced_transition.png", dpi=140)
    print("fig5 ok")


def main():
    rows = load_rows()
    fig1(rows); fig2(rows); fig3(rows); fig4(rows); fig5(rows)
    print("figures ->", OUT)


if __name__ == "__main__":
    main()
