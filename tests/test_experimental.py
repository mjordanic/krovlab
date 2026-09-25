"""Behaviour of the experimental entry point: roof_from_face_graph.

The seam is a footprint in, a Roof or a Failure out. Pitch is not an
argument. Tests do not look at optimiser iterations or log lines.
"""

import math
import subprocess
import sys
from inspect import signature

import pytest
from shapely.geometry import Point, Polygon  # type: ignore[import-untyped]

from krovlab import Failure, Roof, roof
from krovlab.experimental import Placement, moved_toward_wall, roof_from_face_graph

L_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]
RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
U_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (8.0, 6.0),
    (8.0, 2.0),
    (2.0, 2.0),
    (2.0, 6.0),
    (0.0, 6.0),
]


def test_omitted_roof_height_rises_like_a_45_degree_hip_on_the_10_by_6() -> None:
    result = roof_from_face_graph(RECTANGLE)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(3.0)


def test_omitted_placement_centers_the_apex_on_the_10_by_6() -> None:
    result = roof_from_face_graph(RECTANGLE, roof_height=3.0)
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y, apex.height) == pytest.approx((5.0, 3.0, 3.0))
    assert not any(arc.kind == "ridge" for arc in result.arcs)
    long_walls = [face for face in result.faces if face.edge_index in (0, 2)]
    short_walls = [face for face in result.faces if face.edge_index in (1, 3)]
    assert [face.pitch for face in long_walls] == pytest.approx([45.0, 45.0])
    short_pitch = math.degrees(math.atan(3.0 / 5.0))
    assert [face.pitch for face in short_walls] == pytest.approx(
        [short_pitch, short_pitch]
    )


def test_offset_moves_the_apex_and_place_at_center_returns_it() -> None:
    moved = roof_from_face_graph(
        RECTANGLE, roof_height=3.0, placement=Placement(dx=1.0, dy=0.0)
    )
    assert isinstance(moved, Roof)
    apex = max(moved.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y) == pytest.approx((6.0, 3.0))
    assert moved.ridge_height == pytest.approx(3.0)
    centered = roof_from_face_graph(
        RECTANGLE, roof_height=3.0, placement=Placement(dx=0.0, dy=0.0)
    )
    assert isinstance(centered, Roof)
    back = max(centered.nodes, key=lambda node: node.height)
    assert (back.x, back.y) == pytest.approx((5.0, 3.0))


def test_one_metre_toward_wall_2_puts_the_apex_at_6_3() -> None:
    moved = moved_toward_wall(RECTANGLE, 2)
    assert isinstance(moved, Placement)
    result = roof_from_face_graph(RECTANGLE, roof_height=3.0, placement=moved)
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y, apex.height) == pytest.approx((6.0, 3.0, 3.0))


def test_a_move_adds_to_the_current_offset() -> None:
    moved = Placement(dx=1.0, dy=0.0).added(0.5, -1.0)
    result = roof_from_face_graph(RECTANGLE, roof_height=3.0, placement=moved)
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y) == pytest.approx((6.5, 2.0))


def test_overhang_is_applied_before_the_clearance_midpoint() -> None:
    result = roof_from_face_graph(RECTANGLE, roof_height=3.0, overhang=1.0)
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y) == pytest.approx((5.0, 3.0))
    long_pitch = math.degrees(math.atan(3.0 / 4.0))
    short_pitch = math.degrees(math.atan(3.0 / 6.0))
    long_walls = [face.pitch for face in result.faces if face.edge_index in (0, 2)]
    short_walls = [face.pitch for face in result.faces if face.edge_index in (1, 3)]
    assert long_walls == pytest.approx([long_pitch, long_pitch])
    assert short_walls == pytest.approx([short_pitch, short_pitch])


def test_eave_height_lifts_the_placed_roof() -> None:
    result = roof_from_face_graph(
        RECTANGLE,
        roof_height=3.0,
        eave_height=2.0,
        placement=Placement(dx=1.0, dy=0.0),
    )
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y, apex.height) == pytest.approx((6.0, 3.0, 5.0))


def test_placement_does_not_change_which_walls_share_a_face() -> None:
    centered = roof_from_face_graph(
        L_SHAPE, MIXED, roof_height=3.0, checkpoint=None
    )
    moved = roof_from_face_graph(
        L_SHAPE,
        MIXED,
        roof_height=3.0,
        checkpoint=None,
        placement=Placement(dx=0.5, dy=0.0),
    )
    assert isinstance(centered, Roof)
    assert isinstance(moved, Roof)
    assert [face.edge_index for face in moved.faces] == [
        face.edge_index for face in centered.faces
    ]
    spanning = next(face for face in moved.faces if face.edge_index == 2)
    assert {2, 3, 4} <= set(spanning.node_indices)


def test_the_l_starts_at_the_clearance_midpoint() -> None:
    result = roof_from_face_graph(
        L_SHAPE, [[0], [1], [2], [3], [4], [5]], roof_height=3.0, checkpoint=None
    )
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y) == pytest.approx((5.0, 3.0))


def test_an_offset_outside_the_footprint_pulls_back_along_the_segment() -> None:
    result = roof_from_face_graph(
        RECTANGLE, roof_height=3.0, placement=Placement(dx=10.0, dy=0.0)
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    apex = max(result.nodes, key=lambda node: node.height)
    assert apex.y == pytest.approx(3.0)
    assert apex.x < 10.0
    assert apex.x == pytest.approx(10.0, abs=1e-2)
    settled = roof_from_face_graph(
        RECTANGLE,
        roof_height=3.0,
        placement=Placement(dx=apex.x - 5.0, dy=apex.y - 3.0),
    )
    assert isinstance(settled, Roof)
    again = max(settled.nodes, key=lambda node: node.height)
    assert (again.x, again.y) == pytest.approx((apex.x, apex.y))


def test_roof_height_sets_the_rise_above_the_eaves() -> None:
    result = roof_from_face_graph(RECTANGLE, roof_height=2.0)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(2.0)


def test_roof_height_must_be_above_the_eaves() -> None:
    result = roof_from_face_graph(RECTANGLE, roof_height=0.0)
    assert isinstance(result, Failure)
    assert result.kind == "degenerate"
    negative = roof_from_face_graph(RECTANGLE, roof_height=-1.0)
    assert isinstance(negative, Failure)
    assert negative.kind == "degenerate"


def test_omitted_graph_roofs_from_the_committed_checkpoint() -> None:
    result = roof_from_face_graph(L_SHAPE)
    assert isinstance(result, Roof)
    apex = max(result.nodes, key=lambda node: node.height)
    assert (apex.x, apex.y) == pytest.approx((5.0, 3.0))
    assert "pitch" not in signature(roof_from_face_graph).parameters


def test_omitted_graph_without_a_checkpoint_is_no_face_graph() -> None:
    result = roof_from_face_graph(L_SHAPE, checkpoint=None)
    assert isinstance(result, Failure)
    assert result.kind == "no_face_graph"


def test_supplied_graph_roofs_without_the_checkpoint() -> None:
    missing = "/no/such/ren2021-face-adjacency.pt"
    result = roof_from_face_graph(L_SHAPE, MIXED, checkpoint=missing)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert len(result.faces) == 5


def test_a_graph_that_does_not_cover_every_wall_is_unliftable() -> None:
    result = roof_from_face_graph(L_SHAPE, [[0], [1]])
    assert isinstance(result, Failure)
    assert result.kind == "unliftable"


# Walls 2 and 3 of L_SHAPE are non-collinear and belong to one face.
ONE_FACE = [[0, 1, 2, 3, 4, 5]]
MIXED = [[0], [1], [2, 3], [4], [5]]


def test_l_with_two_non_collinear_walls_on_one_face_returns_that_face() -> None:
    result = roof_from_face_graph(L_SHAPE, MIXED)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert len(result.faces) == 5
    covering = next(
        (face for face in result.faces if {2, 3, 4} <= set(face.node_indices)),
        None,
    )
    assert covering is not None
    assert (result.nodes[2].x, result.nodes[2].y) == pytest.approx((10.0, 6.0))
    assert (result.nodes[3].x, result.nodes[3].y) == pytest.approx((3.0, 6.0))
    assert (result.nodes[4].x, result.nodes[4].y) == pytest.approx((3.0, 10.0))


def test_skeleton_on_the_same_l_has_one_face_per_wall() -> None:
    built = roof(L_SHAPE, 45.0)
    assert isinstance(built, Roof)
    assert len(built.faces) == 6
    assert sorted(face.edge_index for face in built.faces) == [0, 1, 2, 3, 4, 5]


def test_terrain_quantities_use_the_same_definitions_as_roof() -> None:
    result = roof_from_face_graph(L_SHAPE, MIXED)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    footprint_area = Polygon(L_SHAPE).area
    assert footprint_area == pytest.approx(72.0)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(72.0)
    for face in result.faces:
        expected = face.plan_area / math.cos(math.radians(face.pitch))
        assert face.sloped_area == pytest.approx(expected)
    assert result.total_sloped_area == pytest.approx(
        sum(face.sloped_area for face in result.faces)
    )
    kinds = {arc.kind for arc in result.arcs}
    assert "eave" in kinds
    for arc in result.arcs:
        a, b = result.nodes[arc.start], result.nodes[arc.end]
        length = math.hypot(a.x - b.x, a.y - b.y, a.height - b.height)
        assert arc.length == pytest.approx(length)


def test_roof_and_project_do_not_take_a_placement() -> None:
    from krovlab import project

    assert "placement" not in signature(roof).parameters
    assert "placement" not in signature(project).parameters


def test_import_krovlab_does_not_load_the_experimental_module() -> None:
    code = """
import sys
import krovlab
if "krovlab.experimental" in sys.modules:
    raise SystemExit("krovlab.experimental")
if "torch" in sys.modules:
    raise SystemExit("torch")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_overhang_puts_the_eaves_outside_the_walls() -> None:
    result = roof_from_face_graph(L_SHAPE, ONE_FACE, overhang=0.5)
    assert isinstance(result, Roof)
    walls = Polygon(L_SHAPE)
    eaves = [arc for arc in result.arcs if arc.kind == "eave"]
    assert eaves
    for arc in eaves:
        a, b = result.nodes[arc.start], result.nodes[arc.end]
        mid = Point(0.5 * (a.x + b.x), 0.5 * (a.y + b.y))
        assert not walls.covers(mid)


def test_eave_height_shifts_the_roof_by_that_height() -> None:
    at_datum = roof_from_face_graph(L_SHAPE, ONE_FACE)
    lifted = roof_from_face_graph(L_SHAPE, ONE_FACE, eave_height=7.0)
    assert isinstance(at_datum, Roof)
    assert isinstance(lifted, Roof)
    assert lifted.ridge_height == pytest.approx(at_datum.ridge_height + 7.0)
    assert [face.plan_area for face in lifted.faces] == pytest.approx(
        [face.plan_area for face in at_datum.faces]
    )


def _meet_pairs(built: Roof) -> set[frozenset[int]]:
    """Which faces share a node, keyed by the caller's wall index."""
    at_node: dict[int, set[int]] = {}
    for face in built.faces:
        for idx in face.node_indices:
            at_node.setdefault(idx, set()).add(face.edge_index)
    pairs: set[frozenset[int]] = set()
    for ids in at_node.values():
        listed = list(ids)
        for i, left in enumerate(listed):
            for right in listed[i + 1 :]:
                pairs.add(frozenset((left, right)))
    return pairs


def test_checkpoint_roof_has_a_different_face_arrangement_from_the_skeleton() -> None:
    experimental = roof_from_face_graph(RECTANGLE)
    skeleton = roof(RECTANGLE, 45.0)
    assert isinstance(experimental, Roof)
    assert isinstance(skeleton, Roof)
    assert _meet_pairs(experimental) != _meet_pairs(skeleton)


def test_predicted_graph_that_cannot_be_lifted_is_unliftable() -> None:
    result = roof_from_face_graph(U_SHAPE)
    assert isinstance(result, Failure)
    assert result.kind == "unliftable"


def test_omitted_graph_does_not_fetch_the_published_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("fetched the published pairs")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    result = roof_from_face_graph(L_SHAPE)
    assert isinstance(result, Roof)


def test_supplied_graph_does_not_load_torch() -> None:
    code = """
import sys
from krovlab.experimental import roof_from_face_graph
from krovlab import Roof
result = roof_from_face_graph(
    [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (3.0, 6.0), (3.0, 10.0), (0.0, 10.0)],
    [[0], [1], [2, 3], [4], [5]],
    checkpoint="/no/such/ren2021-face-adjacency.pt",
)
if not isinstance(result, Roof):
    raise SystemExit(getattr(result, "kind", type(result).__name__))
if "torch" in sys.modules:
    raise SystemExit("torch")
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
