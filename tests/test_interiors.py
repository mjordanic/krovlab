"""A visitor-placed interior: apexes and ridges in, a roof or a Failure out.

The seam is :func:`krovlab.experimental.roof_from_interiors`. Tests use
worked plan positions, not the triangulation's private steps.
"""

import math

import pytest

from krovlab import Roof
from krovlab.experimental import Apex, Ridge, roof_from_interiors

RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]


def test_omitted_interior_is_one_apex_at_the_middle_of_the_10_by_6() -> None:
    result = roof_from_interiors(RECTANGLE, roof_height=3.0)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.apexes == (Apex(5.0, 3.0, height=3.0),)
    assert result.ridges == ()
    tip = max(result.nodes, key=lambda node: node.height)
    assert (tip.x, tip.y, tip.height) == pytest.approx((5.0, 3.0, 3.0))
    assert not any(arc.kind == "ridge" for arc in result.arcs)
    long_pitch = [face.pitch for face in result.faces if face.edge_index in (0, 2)]
    short_pitch = [face.pitch for face in result.faces if face.edge_index in (1, 3)]
    assert long_pitch == pytest.approx([45.0, 45.0])
    assert short_pitch == pytest.approx([math.degrees(math.atan(3.0 / 5.0))] * 2)


def test_a_level_ridge_parallel_to_the_long_walls_is_a_45_degree_hip() -> None:
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(),
        ridges=(Ridge(3.0, 3.0, 7.0, 3.0),),
        roof_height=3.0,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert [face.pitch for face in result.faces] == pytest.approx([45.0] * 4)
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert len(ridges) == 1
    ends = sorted(
        [
            (result.nodes[ridges[0].start].x, result.nodes[ridges[0].start].y),
            (result.nodes[ridges[0].end].x, result.nodes[ridges[0].end].y),
        ]
    )
    assert ends == pytest.approx([(3.0, 3.0), (7.0, 3.0)])
    assert sum(face.plan_area for face in result.faces) == pytest.approx(60.0)


def test_the_l_roofs_two_ridges_at_different_heights() -> None:
    ell = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (3.0, 6.0),
        (3.0, 10.0),
        (0.0, 10.0),
    ]
    result = roof_from_interiors(
        ell,
        apexes=(),
        ridges=(
            Ridge(3.0, 3.0, 7.0, 3.0, height=3.0),
            Ridge(1.5, 4.5, 1.5, 8.5, height=1.5),
        ),
        roof_height=2.0,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.ridge_height == pytest.approx(3.0)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(72.0)
    ridge_arcs = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert len(ridge_arcs) == 2
    heights = sorted(result.nodes[arc.start].height for arc in ridge_arcs)
    assert heights == pytest.approx([1.5, 3.0])


def test_equal_l_ridge_heights_pull_back() -> None:
    ell = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (3.0, 6.0),
        (3.0, 10.0),
        (0.0, 10.0),
    ]
    working = (
        Ridge(3.0, 3.0, 7.0, 3.0, height=3.0),
        Ridge(1.5, 4.5, 1.5, 8.5, height=1.5),
    )
    result = roof_from_interiors(
        ell,
        apexes=(),
        ridges=(
            Ridge(3.0, 3.0, 7.0, 3.0, height=3.0),
            Ridge(1.5, 4.5, 1.5, 8.5, height=3.0),
        ),
        roof_height=3.0,
        previous_apexes=(),
        previous_ridges=working,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.ridges[0].height == pytest.approx(3.0)
    assert result.ridges[1].height == pytest.approx(1.5)


def test_a_ridge_end_stops_short_of_an_apex_at_a_different_height() -> None:
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(Apex(5.0, 3.0, height=3.0),),
        ridges=(Ridge(5.0, 3.0, 9.0, 2.0, height=2.0),),
        roof_height=3.0,
        previous_apexes=(Apex(5.0, 3.0, height=3.0),),
        previous_ridges=(Ridge(7.0, 2.0, 9.0, 2.0, height=2.0),),
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.apexes[0].height == pytest.approx(3.0)
    assert result.ridges[0].height == pytest.approx(2.0)
    end = (result.ridges[0].x0, result.ridges[0].y0)
    assert math.hypot(end[0] - 5.0, end[1] - 3.0) > 0.25


def test_ridge_ends_within_a_quarter_metre_share_one_point() -> None:
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(),
        ridges=(
            Ridge(3.0, 3.0, 5.0, 3.0, height=3.0),
            Ridge(5.2, 3.0, 7.2, 3.0, height=3.0),
        ),
        roof_height=3.0,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    raised = [node for node in result.nodes if node.height > 1.0]
    assert len(raised) == 3


def test_different_ridge_heights_stop_short_of_a_join() -> None:
    previous = (
        Ridge(3.0, 3.0, 5.0, 3.0, height=3.0),
        Ridge(5.3, 3.0, 7.3, 3.0, height=3.0),
    )
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(),
        ridges=(
            Ridge(3.0, 3.0, 5.0, 3.0, height=3.0),
            Ridge(5.15, 3.0, 7.3, 3.0, height=2.0),
        ),
        roof_height=3.0,
        previous_apexes=(),
        previous_ridges=previous,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.ridges[0].height == pytest.approx(3.0)
    assert result.ridges[1].height == pytest.approx(3.0)
    gap = math.hypot(result.ridges[1].x0 - 5.0, result.ridges[1].y0 - 3.0)
    assert gap > 0.25


def test_an_apex_sitting_on_a_ridge_still_roofs() -> None:
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(Apex(5.0, 3.0),),
        ridges=(Ridge(4.0, 3.0, 6.0, 3.0),),
        roof_height=3.0,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
