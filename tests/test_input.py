"""Input boundary of the single public seam: roof(footprint, pitch).

Winding, pitch spellings, validation and Failure-as-a-value. Tests go
through ``roof`` only — the parser, the intersection check and the
winding flip are implementation.
"""

import pytest

from krovlab import Failure, Pitch, Roof, roof

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_pitch_outside_range_is_a_failure_with_kind_invalid_pitch() -> None:
    result = roof(SQUARE, 0.0)
    assert isinstance(result, Failure)
    assert result.kind == "invalid_pitch"
    assert "0 < pitch <= 90" in result.reason


def _geometry(built: Roof) -> tuple[object, ...]:
    """Quantities that must match when the same building is wound either way."""
    nodes = tuple(sorted((n.x, n.y, n.height) for n in built.nodes))
    areas = tuple(sorted(face.plan_area for face in built.faces))
    arcs = tuple(sorted((arc.kind, round(arc.length, 9)) for arc in built.arcs))
    return built.ridge_height, built.total_sloped_area, nodes, areas, arcs


def test_clockwise_and_counterclockwise_produce_the_same_roof() -> None:
    ccw = roof(SQUARE, 45.0)
    cw = roof(list(reversed(SQUARE)), 45.0)
    assert isinstance(ccw, Roof)
    assert isinstance(cw, Roof)
    assert _geometry(ccw) == _geometry(cw)


def test_degrees_rise_run_and_percent_of_the_same_slope_produce_the_same_roof() -> None:
    # tan(45°) = 1 = 1/1 = 100/100, so these are three spellings of one pitch.
    as_degrees = roof(SQUARE, 45.0)
    as_ratio = roof(SQUARE, (1.0, 1.0))
    as_percent = roof(SQUARE, "100%")
    assert isinstance(as_degrees, Roof)
    assert isinstance(as_ratio, Roof)
    assert isinstance(as_percent, Roof)
    assert as_degrees == as_ratio == as_percent
    assert all(face.pitch == 45.0 for face in as_degrees.faces)


def test_returned_roof_values_are_in_metres_and_degrees() -> None:
    result = roof(SQUARE, "100%")
    assert isinstance(result, Roof)
    # 45°, not radians; 5 m apex on a 10 m square, not some internal unit.
    assert all(face.pitch == 45.0 for face in result.faces)
    assert result.ridge_height == pytest.approx(5.0)
    assert result.nodes[0].height == 0.0


def test_self_intersecting_footprint_returns_self_intersection_failure() -> None:
    bowtie = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    result = roof(bowtie, 45.0)
    assert isinstance(result, Failure)
    assert result.kind == "self_intersection"
    assert "self-intersect" in result.reason.lower()


def test_single_point_is_degenerate() -> None:
    result = roof([(0.0, 0.0)], 45.0)
    assert isinstance(result, Failure)
    assert result.kind == "degenerate"


def test_line_is_degenerate() -> None:
    result = roof([(0.0, 0.0), (10.0, 0.0), (4.0, 0.0)], 45.0)
    assert isinstance(result, Failure)
    assert result.kind == "degenerate"


def test_two_points_are_degenerate() -> None:
    result = roof([(0.0, 0.0), (10.0, 0.0)], 45.0)
    assert isinstance(result, Failure)
    assert result.kind == "degenerate"


def test_coincident_consecutive_vertices_are_degenerate() -> None:
    result = roof(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        45.0,
    )
    assert isinstance(result, Failure)
    assert result.kind == "degenerate"
    assert "coincident" in result.reason


def test_closed_ring_spelling_is_roofable() -> None:
    closed = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    result = roof(closed, 45.0)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(5.0)


def test_collinear_edges_that_leave_area_are_roofable() -> None:
    # Midpoint on the south eave: same rectangle, one extra vertex.
    result = roof(
        [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)],
        45.0,
    )
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(3.0)


def test_adjacent_parallel_edges_of_differing_pitch_are_refused() -> None:
    # Collinear south eave split at the midpoint; the two halves disagree.
    ring = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    pitches: list[Pitch] = [45.0, 30.0, 45.0, 45.0, 45.0]
    first = roof(ring, pitches)
    second = roof(ring, pitches)
    assert isinstance(first, Failure)
    assert first == second
    assert first.kind == "unsupported"
    assert "parallel" in first.reason.lower()
    assert "pitch" in first.reason.lower()


def test_pitch_list_of_wrong_length_is_pitch_count_failure() -> None:
    result = roof(SQUARE, [45.0, 45.0, 45.0])
    assert isinstance(result, Failure)
    assert result.kind == "pitch_count"
    assert "4" in result.reason
    assert "3" in result.reason


def test_uniform_pitch_list_matching_edges_produces_a_roof() -> None:
    result = roof(SQUARE, [45.0, "100%", (1.0, 1.0), "1:1"])
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(5.0)


def test_differing_pitch_list_produces_a_roof() -> None:
    result = roof(SQUARE, [45.0, 30.0, 45.0, 45.0])
    assert isinstance(result, Roof)


def test_hole_touching_outer_ring_is_hole_intersects() -> None:
    hole = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    result = roof(SQUARE, 45.0, holes=[hole])
    assert isinstance(result, Failure)
    assert result.kind == "hole_intersects"


def test_hole_crossing_outer_ring_is_hole_intersects() -> None:
    hole = [(-1.0, 2.0), (4.0, 2.0), (4.0, 8.0), (-1.0, 8.0)]
    result = roof(SQUARE, 45.0, holes=[hole])
    assert isinstance(result, Failure)
    assert result.kind == "hole_intersects"


def test_valid_hole_is_unsupported_until_holes_are_built() -> None:
    hole = [(2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)]
    result = roof(SQUARE, 45.0, holes=[hole])
    assert isinstance(result, Failure)
    assert result.kind == "unsupported"
    assert "hole" in result.reason.lower()


def test_malformed_input_does_not_raise() -> None:
    cases: list[tuple[object, object]] = [
        (None, 45.0),
        ([], 45.0),
        ([(0.0, 0.0)], 45.0),
        ("not a ring", 45.0),
        (SQUARE, None),
        (SQUARE, "steep"),
        (SQUARE, float("nan")),
        (SQUARE, [45.0]),
        (SQUARE, True),
    ]
    for footprint, pitch in cases:
        result = roof(footprint, pitch)  # type: ignore[call-overload]
        assert isinstance(result, Failure), (footprint, pitch, result)
    hole_cases: list[object] = [
        "not rings",
        [[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]],
        [[(-1.0, -1.0), (11.0, -1.0), (11.0, 11.0), (-1.0, 11.0)]],
    ]
    for holes in hole_cases:
        result = roof(SQUARE, 45.0, holes=holes)  # type: ignore[call-overload]
        assert isinstance(result, Failure), holes
