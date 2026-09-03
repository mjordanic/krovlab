"""Invariant harness: named properties over generated convex footprints.

Each test is one property. Later tickets widen the generator in
``tests/generation.py``; they should not copy these assertions.
"""

from hypothesis import given, settings

from generation import PITCHES, footprints
from invariants import (
    arc_classification_matches_geometry,
    drainage_runs_to_each_faces_own_eave,
    every_face_is_planar,
    plan_areas_sum_to_footprint_area,
    roof_is_a_terrain,
    sloped_area_is_at_least_plan_area,
)
from krovlab import Roof, Validity, roof

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

_SETTINGS = settings(max_examples=40, deadline=None)


def _built(footprint: list[tuple[float, float]], pitch: float) -> Roof:
    result = roof(footprint, pitch)
    assert isinstance(result, Roof)
    return result


def test_returned_roof_carries_a_validity_result_that_is_a_terrain() -> None:
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    assert isinstance(result.validity, Validity)
    assert result.validity.is_terrain is True
    assert result.validity.reasons == ()


@_SETTINGS
@given(footprints())
def test_generator_produces_only_convex_footprints(
    footprint: list[tuple[float, float]],
) -> None:
    from shapely.geometry import Polygon  # type: ignore[import-untyped]

    poly = Polygon(footprint)
    assert poly.is_valid
    assert len(footprint) >= 3
    assert poly.equals(poly.convex_hull)


@_SETTINGS
@given(footprints(), PITCHES)
def test_plan_areas_sum_to_the_footprint_area(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    plan_areas_sum_to_footprint_area(built, footprint)


@_SETTINGS
@given(footprints(), PITCHES)
def test_every_face_is_planar(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    every_face_is_planar(built)


@_SETTINGS
@given(footprints(), PITCHES)
def test_sloped_area_is_at_least_plan_area(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    sloped_area_is_at_least_plan_area(_built(footprint, pitch))


@_SETTINGS
@given(footprints(), PITCHES)
def test_roof_is_a_terrain(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    roof_is_a_terrain(built, footprint)


@_SETTINGS
@given(footprints(), PITCHES)
def test_drainage_runs_to_each_faces_own_eave(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    drainage_runs_to_each_faces_own_eave(built, footprint)


@_SETTINGS
@given(footprints(), PITCHES)
def test_arc_classification_matches_geometry(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    arc_classification_matches_geometry(built, footprint)


@_SETTINGS
@given(footprints(), PITCHES)
def test_same_input_yields_byte_identical_roofs(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    first = _built(footprint, pitch)
    second = _built(footprint, pitch)
    assert first == second, (
        "same input yields a byte-identical roof: two runs of roof() differed"
    )


@_SETTINGS
@given(footprints(), PITCHES)
def test_generated_roofs_are_reported_valid(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    built = _built(footprint, pitch)
    assert built.validity.is_terrain is True, built.validity.reasons


def test_validity_reports_the_property_that_broke() -> None:
    from dataclasses import replace

    built = _built(SQUARE, 45.0)
    broken_face = replace(built.faces[0], plan_area=0.0)
    broken_faces = (broken_face, *built.faces[1:])
    validity = Validity.assess(built.nodes, broken_faces, built.arcs, SQUARE)
    assert validity.is_terrain is False
    assert any(
        r.startswith("plan areas sum to footprint area") for r in validity.reasons
    )
