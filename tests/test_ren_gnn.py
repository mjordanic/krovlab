"""Public behaviour of the Ren et al. 2021 face-adjacency network.

The seam is the predicted probability that two walls meet. Tests do not
look at layer activations, optimiser steps, or log lines.
"""

import subprocess
import sys

import torch

from krovlab.ren_gnn import FaceAdjacencyNet, fit, pairwise_meet_probability
from krovlab.ren_gnn.data import drop_four_vertex, split_by_sorted_name

# L-shaped footprint, six walls. Labels are unused in the symmetry test.
L_SHAPE = [
    (0.0, 0.0),
    (6.0, 0.0),
    (6.0, 4.0),
    (3.0, 4.0),
    (3.0, 8.0),
    (0.0, 8.0),
]


def test_probability_that_wall_i_meets_j_equals_j_meets_i() -> None:
    model = FaceAdjacencyNet()
    probs = pairwise_meet_probability(L_SHAPE, model)
    n = len(L_SHAPE)
    assert len(probs) == n
    assert all(len(row) == n for row in probs)
    for i in range(n):
        for j in range(n):
            assert probs[i][j] == probs[j][i]


# Hand-labelled dual of an L: consecutive walls meet, and walls 0 and 3 meet.
MEET = [
    [0, 1, 0, 1, 0, 1],
    [1, 0, 1, 0, 0, 0],
    [0, 1, 0, 1, 0, 0],
    [1, 0, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 1],
    [1, 0, 0, 0, 1, 0],
]


def test_synthetic_labelled_footprint_can_be_memorised() -> None:
    torch.manual_seed(0)
    model = FaceAdjacencyNet()
    fit(model, L_SHAPE, MEET, steps=800, lr=1e-3)
    probs = pairwise_meet_probability(L_SHAPE, model)
    n = len(L_SHAPE)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if MEET[i][j]:
                assert probs[i][j] > 0.5
            else:
                assert probs[i][j] < 0.5


def test_import_krovlab_pulls_in_no_third_party_package() -> None:
    code = """
import sys
import krovlab

banned = {
    "torch",
    "plotly",
    "flask",
    "numpy",
    "shapely",
    "google",
    "dotenv",
    "PIL",
    "sympy",
    "networkx",
}
loaded = sorted(
    {
        name.split(".", 1)[0]
        for name in sys.modules
        if name.split(".", 1)[0] in banned
    }
)
if loaded:
    raise SystemExit(",".join(loaded))
if "krovlab.ren_gnn" in sys.modules:
    raise SystemExit("krovlab.ren_gnn")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_held_out_are_the_last_names_after_sorting() -> None:
    names = ["c.outline", "a.outline", "b.outline", "e.outline", "d.outline"]
    train, held = split_by_sorted_name(names, hold_out=2)
    assert train == ["a.outline", "b.outline", "c.outline"]
    assert held == ["d.outline", "e.outline"]


def test_four_vertex_footprints_are_dropped_from_both_sides() -> None:
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    pent = [(0.0, 0.0), (2.0, 0.0), (3.0, 1.0), (1.0, 2.0), (0.0, 1.0)]
    kept = drop_four_vertex(
        [
            ("square", square, [[0] * 4] * 4),
            ("pent", pent, [[0] * 5] * 5),
        ]
    )
    assert [name for name, _, _ in kept] == ["pent"]
