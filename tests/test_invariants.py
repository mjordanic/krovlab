"""Invariant harness: named properties over generated simple footprints.

Each test is one property. Later tickets widen the generator in
``tests/generation.py``; they should not copy these assertions.
Per-edge pitch, holes, gables and overhangs are drawn by :func:`generation.roof_cases`.
"""

from typing import cast

from hypothesis import given, settings
from shapely.geometry import JOIN_STYLE, Polygon  # type: ignore[import-untyped]

from generation import footprints, roof_cases
from invariants import (
    arc_classification_matches_geometry,
    drainage_runs_to_each_faces_own_eave,
    every_face_is_planar,
    plan_areas_sum_to_footprint_area,
    roof_is_a_terrain,
    sloped_area_is_at_least_plan_area,
)
from krovlab import Pitch, Roof, Validity, roof

RoofCase = tuple[
    list[tuple[float, float]],
    float | list[float],
    list[list[tuple[float, float]]],
    float,
]

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

_SETTINGS = settings(max_examples=40, deadline=None)


def _built(
    footprint: list[tuple[float, float]],
    pitch: float | list[float],
    holes: list[list[tuple[float, float]]],
    overhang: float = 0.0,
) -> Roof:
    result = roof(
        footprint,
        cast(float | list[Pitch], pitch),
        holes=holes or None,
        overhang=overhang,
    )
    assert isinstance(result, Roof), getattr(result, "reason", result)
    return result


def _roofed_rings(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    overhang: float,
) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    """The polygon the roof covers, via shapely as a second opinion on the offset.

    Vertices are paired back to the caller's order so ``edge_index`` still
    names the same edge after the offset.
    """
    if overhang == 0.0:
        return footprint, holes
    buffered = Polygon(footprint, holes).buffer(
        overhang, join_style=JOIN_STYLE.mitre, mitre_limit=1000.0
    )
    exterior = _align_ring(footprint, list(buffered.exterior.coords)[:-1])
    interiors = [
        _align_ring(hole, list(ring.coords)[:-1])
        for hole, ring in zip(holes, buffered.interiors, strict=True)
    ]
    return exterior, interiors


def _align_ring(
    original: list[tuple[float, float]],
    buffered: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Permute ``buffered`` so vertex i is the nearest to original vertex i."""
    if len(original) != len(buffered):
        return buffered
    used: set[int] = set()
    aligned: list[tuple[float, float]] = []
    for ox, oy in original:
        best = min(
            (i for i in range(len(buffered)) if i not in used),
            key=lambda i: (buffered[i][0] - ox) ** 2 + (buffered[i][1] - oy) ** 2,
        )
        used.add(best)
        aligned.append(buffered[best])
    return aligned


def test_returned_roof_carries_a_validity_result_that_is_a_terrain() -> None:
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    assert isinstance(result.validity, Validity)
    assert result.validity.is_terrain is True
    assert result.validity.reasons == ()


@_SETTINGS
@given(footprints())
def test_generator_produces_simple_polygons(
    footprint: list[tuple[float, float]],
) -> None:
    poly = Polygon(footprint)
    assert poly.is_valid
    assert len(footprint) >= 3
    assert poly.area >= 4.0


@_SETTINGS
@given(roof_cases())
def test_plan_areas_sum_to_the_footprint_area(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    roofed, roofed_holes = _roofed_rings(footprint, holes, overhang)
    plan_areas_sum_to_footprint_area(built, roofed, roofed_holes)


@_SETTINGS
@given(roof_cases())
def test_every_face_is_planar(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    every_face_is_planar(built)


@_SETTINGS
@given(roof_cases())
def test_sloped_area_is_at_least_plan_area(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    sloped_area_is_at_least_plan_area(_built(footprint, pitch, holes, overhang))


@_SETTINGS
@given(roof_cases())
def test_roof_is_a_terrain(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    roofed, roofed_holes = _roofed_rings(footprint, holes, overhang)
    roof_is_a_terrain(built, roofed, roofed_holes)


@_SETTINGS
@given(roof_cases())
def test_drainage_runs_to_each_faces_own_eave(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    roofed, roofed_holes = _roofed_rings(footprint, holes, overhang)
    drainage_runs_to_each_faces_own_eave(built, roofed, roofed_holes)


@_SETTINGS
@given(roof_cases())
def test_arc_classification_matches_geometry(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    roofed, roofed_holes = _roofed_rings(footprint, holes, overhang)
    arc_classification_matches_geometry(built, roofed, roofed_holes)


@_SETTINGS
@given(roof_cases())
def test_same_input_yields_byte_identical_roofs(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    first = _built(footprint, pitch, holes, overhang)
    second = _built(footprint, pitch, holes, overhang)
    assert first == second, (
        "same input yields a byte-identical roof: two runs of roof() differed"
    )


@_SETTINGS
@given(roof_cases())
def test_generated_roofs_are_reported_valid(
    case: RoofCase,
) -> None:
    footprint, pitch, holes, overhang = case
    built = _built(footprint, pitch, holes, overhang)
    assert built.validity.is_terrain is True, built.validity.reasons


def test_validity_reports_the_property_that_broke() -> None:
    from dataclasses import replace

    built = _built(SQUARE, 45.0, [])
    broken_face = replace(built.faces[0], plan_area=0.0)
    broken_faces = (broken_face, *built.faces[1:])
    validity = Validity.assess(built.nodes, broken_faces, built.arcs, SQUARE)
    assert validity.is_terrain is False
    assert any(
        r.startswith("plan areas sum to footprint area") for r in validity.reasons
    )
