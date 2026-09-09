"""Composition of cells through the public ``project`` seam.

Tests of one polygon still go through ``roof``. The wavefront stays
behind those two functions.
"""

import pytest
from hypothesis import assume, given, settings

from generation import PITCHES, footprints
from krovlab import Cell, Dormer, Failure, Pitch, Project, Roof, project, roof

RECT_5X6 = [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
DETACHED_5X6 = [(8.0, 0.0), (13.0, 0.0), (13.0, 6.0), (8.0, 6.0)]
NEIGHBOUR_5X6 = [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)]
# East and west walls gabled: ridge runs north-south. The party wall at
# x = 5 is a 6 m gable, so each cell's ridge is 3 m above its eave.
GABLES: list[Pitch] = [45.0, 90.0, 45.0, 90.0]
L_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
COURTYARD = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]
PLUS = [
    (2.0, 0.0),
    (4.0, 0.0),
    (4.0, 2.0),
    (6.0, 2.0),
    (6.0, 4.0),
    (4.0, 4.0),
    (4.0, 6.0),
    (2.0, 6.0),
    (2.0, 4.0),
    (0.0, 4.0),
    (0.0, 2.0),
    (2.0, 2.0),
]
RECT_10X6 = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
# 2 x 1.5 m rectangle on the long south slope of RECT_10X6.
DORMER_2X15 = [(4.0, 0.5), (6.0, 0.5), (6.0, 2.0), (4.0, 2.0)]
GABLE_DORMER: list[Pitch] = [45.0, 90.0, 45.0, 90.0]
SHED_DORMER: list[Pitch] = [45.0, 90.0, 90.0, 90.0]


def test_empty_list_of_cells_is_a_named_failure() -> None:
    result = project([])
    assert isinstance(result, Failure)
    assert result.kind == "empty"
    assert "cell" in result.reason.lower()


def test_one_cell_matches_that_cell_roofed_alone() -> None:
    alone = roof(RECT_5X6, 45.0, eave_height=5.0)
    wrapped = project([Cell(RECT_5X6, 45.0, eave_height=5.0)])
    assert isinstance(alone, Roof)
    assert isinstance(wrapped, Project)
    assert len(wrapped.roofs) == 1
    assert wrapped.roofs[0] == alone
    assert wrapped.ridge_height == pytest.approx(alone.ridge_height)
    assert wrapped.total_sloped_area == pytest.approx(alone.total_sloped_area)
    assert wrapped.validity.is_terrain is alone.validity.is_terrain
    assert len(wrapped.faces) == len(alone.faces)


def test_two_detached_rectangles_sum_plan_and_sloped_area() -> None:
    low = roof(RECT_5X6, 45.0, eave_height=5.0)
    high = roof(DETACHED_5X6, 45.0, eave_height=7.0)
    assert isinstance(low, Roof)
    assert isinstance(high, Roof)
    result = project(
        [
            Cell(RECT_5X6, 45.0, eave_height=5.0),
            Cell(DETACHED_5X6, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(result, Project)
    plan = sum(face.plan_area for face in result.faces)
    assert plan == pytest.approx(60.0)
    assert result.total_sloped_area == pytest.approx(
        low.total_sloped_area + high.total_sloped_area
    )
    assert result.ridge_height == pytest.approx(9.5)
    assert result.validity.is_terrain is True
    assert len(result.roofs) == 2


def test_each_face_names_its_cell_and_that_cell_edge() -> None:
    result = project(
        [
            Cell(RECT_5X6, 45.0, eave_height=5.0),
            Cell(DETACHED_5X6, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(result, Project)
    by_cell: dict[int, list[int]] = {0: [], 1: []}
    for face in result.faces:
        by_cell[face.cell_index].append(face.edge_index)
        assert face.cell_index in (0, 1)
    assert sorted(by_cell[0]) == [0, 1, 2, 3]
    assert sorted(by_cell[1]) == [0, 1, 2, 3]


def test_overlapping_cells_are_a_named_failure() -> None:
    overlap = [(2.0, 0.0), (7.0, 0.0), (7.0, 6.0), (2.0, 6.0)]
    result = project([Cell(RECT_5X6, 45.0), Cell(overlap, 45.0)])
    assert isinstance(result, Failure)
    assert result.kind == "overlap"
    assert "overlap" in result.reason.lower()


def test_cells_that_only_share_a_wall_are_not_an_overlap() -> None:
    result = project([Cell(RECT_5X6, 45.0), Cell(NEIGHBOUR_5X6, 45.0)])
    assert isinstance(result, Project)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(60.0)


def test_concatenated_gables_at_5m_and_7m_are_one_project() -> None:
    result = project(
        [
            Cell(RECT_5X6, GABLES, eave_height=5.0),
            Cell(NEIGHBOUR_5X6, GABLES, eave_height=7.0),
        ]
    )
    assert isinstance(result, Project)
    assert result.ridge_height == pytest.approx(10.0)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(60.0)
    assert result.validity.is_terrain is True
    assert all(roof.validity.is_terrain for roof in result.roofs)


def test_a_party_wall_is_not_counted_twice_as_eaves() -> None:
    result = project(
        [
            Cell(RECT_5X6, GABLES, eave_height=5.0),
            Cell(NEIGHBOUR_5X6, GABLES, eave_height=7.0),
        ]
    )
    assert isinstance(result, Project)
    eave_m = sum(arc.length for arc in result.arcs if arc.kind == "eave")
    # Each cell has two 5 m eaves. The 6 m party wall is a gable, not an
    # eave, so it is not counted twice.
    assert eave_m == pytest.approx(20.0)


def test_shared_pitched_eaves_at_the_same_height_are_one_valley() -> None:
    result = project([Cell(RECT_5X6, 45.0), Cell(NEIGHBOUR_5X6, 45.0)])
    assert isinstance(result, Project)
    eave_m = sum(arc.length for arc in result.arcs if arc.kind == "eave")
    valley_m = sum(arc.length for arc in result.arcs if arc.kind == "valley")
    assert eave_m == pytest.approx(32.0)
    assert valley_m == pytest.approx(6.0)


def test_shared_edge_gable_versus_pitch_is_a_named_failure() -> None:
    result = project([Cell(RECT_5X6, GABLES), Cell(NEIGHBOUR_5X6, 45.0)])
    assert isinstance(result, Failure)
    assert result.kind == "gable_versus_pitch"
    assert "gable" in result.reason.lower()


def test_shared_pitched_edge_with_unequal_eave_heights_is_a_named_failure() -> None:
    result = project(
        [
            Cell(RECT_5X6, 45.0, eave_height=5.0),
            Cell(NEIGHBOUR_5X6, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(result, Failure)
    assert result.kind == "unequal_eave_height"
    assert "eave" in result.reason.lower()


def test_two_pitches_on_collinear_edges_of_one_cell_remain_unsupported() -> None:
    ring = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    pitches: list[Pitch] = [45.0, 30.0, 45.0, 45.0, 45.0]
    result = project([Cell(ring, pitches)])
    assert isinstance(result, Failure)
    assert result.kind == "unsupported"


def test_identical_cells_are_an_overlap() -> None:
    result = project([Cell(RECT_5X6, 45.0), Cell(RECT_5X6, 45.0)])
    assert isinstance(result, Failure)
    assert result.kind == "overlap"


def test_an_l_as_one_polygon_is_one_cell() -> None:
    alone = roof(L_SHAPE, 45.0)
    result = project([Cell(L_SHAPE, 45.0)])
    assert isinstance(alone, Roof)
    assert isinstance(result, Project)
    assert len(result.roofs) == 1
    assert result.roofs[0] == alone
    assert len(result.faces) == len(alone.faces)


def test_a_cell_with_a_hole_still_roofs() -> None:
    alone = roof(SQUARE, 45.0, holes=[COURTYARD])
    result = project([Cell(SQUARE, 45.0, holes=[COURTYARD])])
    assert isinstance(alone, Roof)
    assert isinstance(result, Project)
    assert result.roofs[0] == alone


def test_a_cell_with_an_overhang_still_roofs() -> None:
    alone = roof(RECT_5X6, 45.0, overhang=0.5)
    result = project([Cell(RECT_5X6, 45.0, overhang=0.5)])
    assert isinstance(alone, Roof)
    assert isinstance(result, Project)
    assert result.roofs[0] == alone


def test_a_cell_with_the_opposite_winding_still_roofs() -> None:
    ring = list(reversed(RECT_5X6))
    alone = roof(ring, 45.0)
    result = project([Cell(ring, 45.0)])
    assert isinstance(alone, Roof)
    assert isinstance(result, Project)
    assert result.roofs[0] == alone


def test_a_non_terrain_cell_keeps_validity_reasons() -> None:
    alone = roof(PLUS, 45.0)
    result = project([Cell(PLUS, 45.0), Cell(DETACHED_5X6, 45.0)])
    assert isinstance(alone, Roof)
    assert alone.validity.is_terrain is False
    assert isinstance(result, Project)
    assert result.validity.is_terrain is False
    for reason in alone.validity.reasons:
        assert any(reason in item for item in result.validity.reasons)
    assert any(item.startswith("cell 0:") for item in result.validity.reasons)


def test_same_cells_produce_the_same_project() -> None:
    cells = [
        Cell(RECT_5X6, 45.0, eave_height=5.0),
        Cell(DETACHED_5X6, 45.0, eave_height=7.0),
    ]
    first = project(cells)
    second = project(cells)
    assert first == second


def test_knee_on_one_cell_leaves_the_other_cell_unchanged() -> None:
    house = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    garage = [(12.0, 0.0), (22.0, 0.0), (22.0, 6.0), (12.0, 6.0)]
    alone_house = roof(house, 45.0)
    alone_garage = roof(garage, 45.0)
    result = project(
        [
            Cell(house, 45.0, knee_height=[0.0, 3.0, 0.0, 0.0]),
            Cell(garage, 45.0),
        ]
    )
    assert isinstance(alone_house, Roof)
    assert isinstance(alone_garage, Roof)
    assert isinstance(result, Project)
    assert result.roofs[1] == alone_garage
    assert result.roofs[0].ridge_height == pytest.approx(alone_house.ridge_height)
    assert 1 not in {face.edge_index for face in result.roofs[0].faces}
    assert sorted(face.edge_index for face in result.roofs[1].faces) == [0, 1, 2, 3]


def test_wrap_on_a_cell_goes_through_project() -> None:
    l_shape = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (3.0, 6.0),
        (3.0, 10.0),
        (0.0, 10.0),
    ]
    alone = roof(l_shape, 45.0, wrap=[[2, 3]])
    result = project([Cell(l_shape, 45.0, wrap=[[2, 3]])])
    assert isinstance(alone, Roof)
    assert isinstance(result, Project)
    assert result.roofs[0] == alone
    assert len(result.faces) == 5
    assert {face.edge_index for face in result.faces} == {0, 1, 2, 4, 5}
    wrapped = next(face for face in result.faces if face.edge_index == 2)
    assert wrapped.eave_indices == (2, 3)


def test_a_bad_cell_is_a_failure_not_an_exception() -> None:
    bowtie = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    result = project([Cell(bowtie, 45.0)])
    assert isinstance(result, Failure)
    assert result.kind == "self_intersection"


def test_project_faces_are_not_roof_faces() -> None:
    from krovlab import Face

    assert "cell_index" not in Face.__dataclass_fields__
    result = project([Cell(RECT_5X6, 45.0)])
    assert isinstance(result, Project)
    assert all(hasattr(face, "cell_index") for face in result.faces)


def test_gable_dormer_shrinks_host_sloped_area_and_adds_faces() -> None:
    import math

    host = project([Cell(RECT_10X6, 45.0)])
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, DORMER_2X15, GABLE_DORMER)],
    )
    assert isinstance(host, Project)
    assert isinstance(result, Project)
    south = next(face for face in host.faces if face.edge_index == 0)
    south_after = next(face for face in result.faces if face.edge_index == 0)
    opening_plan = 2.0 * 1.5
    opening_sloped = opening_plan / math.cos(math.radians(45.0))
    assert south_after.sloped_area == pytest.approx(south.sloped_area - opening_sloped)
    extra = len(result.faces) - len(host.faces)
    assert extra in (2, 3)


def test_host_plus_dormer_plan_areas_cover_the_footprint() -> None:
    host = project([Cell(RECT_10X6, 45.0)])
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, DORMER_2X15, GABLE_DORMER)],
    )
    assert isinstance(host, Project)
    assert isinstance(result, Project)
    host_plan = sum(face.plan_area for face in host.faces)
    result_plan = sum(face.plan_area for face in result.faces)
    assert host_plan == pytest.approx(60.0)
    assert result_plan == pytest.approx(60.0)


def test_a_project_with_dormers_is_not_a_terrain() -> None:
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, DORMER_2X15, GABLE_DORMER)],
    )
    assert isinstance(result, Project)
    assert result.validity.is_terrain is False
    assert any("dormer" in reason.lower() for reason in result.validity.reasons)


def test_shed_and_gable_dormers_use_the_same_placement() -> None:
    gable = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, DORMER_2X15, GABLE_DORMER)],
    )
    shed = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, DORMER_2X15, SHED_DORMER)],
    )
    assert isinstance(gable, Project)
    assert isinstance(shed, Project)
    assert not isinstance(gable, Failure)
    assert not isinstance(shed, Failure)
    gable_extra = len(gable.faces) - 4
    shed_extra = len(shed.faces) - 4
    assert gable_extra in (2, 3)
    assert shed_extra == 1


def test_several_dormers_are_several_placements() -> None:
    second = [(2.2, 0.5), (3.5, 0.5), (3.5, 1.5), (2.2, 1.5)]
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [
            Dormer(0, DORMER_2X15, GABLE_DORMER),
            Dormer(0, second, GABLE_DORMER),
        ],
    )
    assert isinstance(result, Project)
    assert len(result.faces) == 4 + 2 + 2
    assert result.validity.is_terrain is False


def test_dormer_overlapping_two_faces_is_a_named_failure() -> None:
    across_ridge = [(4.5, 2.0), (5.5, 2.0), (5.5, 4.0), (4.5, 4.0)]
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, across_ridge, GABLE_DORMER)],
    )
    assert isinstance(result, Failure)
    assert result.kind == "dormer_two_faces"
    assert "face" in result.reason.lower()


def test_dormer_outside_the_host_is_a_named_failure() -> None:
    floating = [(20.0, 20.0), (22.0, 20.0), (22.0, 21.5), (20.0, 21.5)]
    result = project(
        [Cell(RECT_10X6, 45.0)],
        [Dormer(0, floating, GABLE_DORMER)],
    )
    assert isinstance(result, Failure)
    assert result.kind == "dormer_outside"
    assert "host" in result.reason.lower()


def test_a_dormer_on_a_wrapped_face_clips_that_plane() -> None:
    import math

    l_shape = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (3.0, 6.0),
        (3.0, 10.0),
        (0.0, 10.0),
    ]
    ring = [(5.0, 5.2), (6.5, 5.2), (6.5, 5.7), (5.0, 5.7)]
    host = project([Cell(l_shape, 45.0, wrap=[[2, 3]])])
    result = project(
        [Cell(l_shape, 45.0, wrap=[[2, 3]])],
        [Dormer(0, ring, GABLE_DORMER)],
    )
    assert isinstance(host, Project)
    assert isinstance(result, Project)
    wrapped = next(face for face in host.faces if face.edge_index == 2)
    wrapped_after = next(face for face in result.faces if face.edge_index == 2)
    opening_plan = 1.5 * 0.5
    opening_sloped = opening_plan / math.cos(math.radians(45.0))
    assert wrapped_after.sloped_area == pytest.approx(
        wrapped.sloped_area - opening_sloped
    )
    assert wrapped_after.eave_indices == (2, 3)
    assert len(result.faces) == len(host.faces) + 2


def test_dormers_are_not_a_third_engine() -> None:
    import krovlab
    import krovlab.roof as roof_mod

    assert not hasattr(krovlab, "from_graph")
    assert not hasattr(roof_mod, "from_graph")
    assert "from_graph" not in krovlab.__all__
    assert "Dormer" in krovlab.__all__
    assert "project" in krovlab.__all__
    assert "roof" in krovlab.__all__


_SETTINGS = settings(max_examples=25, deadline=None)


@_SETTINGS
@given(footprints(), footprints(), PITCHES, PITCHES)
def test_generated_non_overlapping_cells_sum_takeoff(
    first: list[tuple[float, float]],
    second: list[tuple[float, float]],
    pitch_a: float,
    pitch_b: float,
) -> None:
    from shapely.geometry import Polygon  # type: ignore[import-untyped]

    shifted = [(x + 1000.0, y + 1000.0) for x, y in second]
    left = roof(first, pitch_a)
    right = roof(shifted, pitch_b)
    assume(isinstance(left, Roof) and isinstance(right, Roof))
    result = project([Cell(first, pitch_a), Cell(shifted, pitch_b)])
    assume(isinstance(result, Project))
    assert isinstance(left, Roof)
    assert isinstance(right, Roof)
    assert isinstance(result, Project)
    assert result.total_sloped_area == pytest.approx(
        left.total_sloped_area + right.total_sloped_area
    )
    assert result.ridge_height == pytest.approx(
        max(left.ridge_height, right.ridge_height)
    )
    plan = sum(face.plan_area for face in result.faces)
    union = Polygon(first).union(Polygon(shifted)).area
    assert plan == pytest.approx(union)
    assert project([Cell(first, pitch_a), Cell(shifted, pitch_b)]) == result
