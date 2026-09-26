"""A roof whose hips are the links the visitor set.

The seam is :func:`krovlab.links.roof_from_links`. Expected areas are the
straight skeleton of the L at 45°, not a quantity this module computes.
"""

import pytest

from krovlab import Failure, Roof, roof
from krovlab.experimental import Ridge
from krovlab.links import Target, links_from_skeleton, roof_from_links

ELL = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]
HIGH = Target("ridge", 0)
LOW = Target("ridge", 1)
RIDGES = (
    Ridge(3.0, 3.0, 7.0, 3.0, height=3.0),
    Ridge(1.5, 4.5, 1.5, 8.5, height=1.5),
)


def test_the_l_skeleton_links_are_a_terrain() -> None:
    result = roof_from_links(
        ELL,
        ridges=RIDGES,
        walls=(HIGH, HIGH, HIGH, LOW, LOW, LOW),
        corners=(
            Target("ridge", 0, 0),
            None,
            None,
            Target("ridge", 1, 0),
            None,
            None,
        ),
        joins=((Target("ridge", 1, 0), Target("ridge", 0, 0)),),
    )
    assert isinstance(result, Roof)
    assert result.validity.reasons == ()
    assert result.validity.is_terrain is True
    assert result.ridge_height == pytest.approx(3.0)
    assert sorted(face.plan_area for face in result.faces) == pytest.approx(
        [2.25, 6.0, 9.0, 15.0, 18.75, 21.0]
    )


def test_skeleton_links_rebuild_the_straight_skeleton() -> None:
    rectangle = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    for footprint in (ELL, rectangle):
        plan = links_from_skeleton(footprint)
        assert not isinstance(plan, Failure)
        built = roof_from_links(
            footprint,
            plan.apexes,
            plan.ridges,
            walls=plan.walls,
            corners=plan.corners,
            joins=plan.joins,
        )
        straight = roof(footprint, 45)
        assert isinstance(built, Roof)
        assert isinstance(straight, Roof)
        assert built.validity.reasons == ()
        assert sorted(face.plan_area for face in built.faces) == pytest.approx(
            sorted(face.plan_area for face in straight.faces)
        )


def test_an_open_wall_is_named_and_the_ridge_is_unchanged() -> None:
    result = roof_from_links(
        ELL,
        ridges=RIDGES,
        walls=(None, HIGH, HIGH, LOW, LOW, LOW),
        corners=(
            Target("ridge", 0, 0),
            None,
            None,
            Target("ridge", 1, 0),
            None,
            None,
        ),
        joins=((Target("ridge", 1, 0), Target("ridge", 0, 0)),),
    )
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is False
    assert "wall 1 is open" in result.validity.reasons
    assert any(
        node.x == pytest.approx(3.0)
        and node.y == pytest.approx(3.0)
        and node.height == pytest.approx(3.0)
        for node in result.nodes
    )


def test_a_wall_whose_ridge_is_not_parallel_keeps_the_link() -> None:
    rectangle = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    result = roof_from_links(
        rectangle,
        ridges=(Ridge(2.0, 2.0, 8.0, 4.0, height=3.0),),
        walls=(Target("ridge", 0), None, None, None),
    )
    assert isinstance(result, Roof)
    assert any(
        "wall 1's ridge is not parallel" in reason
        for reason in result.validity.reasons
    )
