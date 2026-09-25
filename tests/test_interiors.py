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
    assert result.apexes == (Apex(5.0, 3.0),)
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


def test_an_apex_sitting_on_a_ridge_still_roofs() -> None:
    result = roof_from_interiors(
        RECTANGLE,
        apexes=(Apex(5.0, 3.0),),
        ridges=(Ridge(4.0, 3.0, 6.0, 3.0),),
        roof_height=3.0,
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
