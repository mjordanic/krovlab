"""Behaviour of the single public seam: roof(footprint, pitch)."""

import math

import pytest

from krovlab import Arc, Face, Failure, Node, Pitch, Roof, roof

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_pitch_outside_open_zero_to_closed_ninety_is_refused() -> None:
    for pitch in (0.0, -10.0, 90.1):
        result = roof(SQUARE, pitch)
        assert isinstance(result, Failure)
        assert result.kind == "invalid_pitch"
    # 90 is in range: it names a gable, not an invalid pitch.
    gabled = roof(SQUARE, [45.0, 90.0, 45.0, 45.0])
    assert isinstance(gabled, Roof)


def test_square_at_forty_five_has_hand_computed_apex_height() -> None:
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(5.0)


def test_square_at_forty_five_has_four_faces_with_hand_computed_areas() -> None:
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    assert len(result.faces) == 4
    sloped = 25.0 / math.cos(math.radians(45.0))
    edge_indices = []
    for face in result.faces:
        assert face.pitch == pytest.approx(45.0)
        assert face.plan_area == pytest.approx(25.0)
        assert face.sloped_area == pytest.approx(sloped)
        edge_indices.append(face.edge_index)
    assert sorted(edge_indices) == [0, 1, 2, 3]


RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]


def test_rectangle_has_one_ridge_of_hand_computed_length_and_position() -> None:
    result = roof(RECTANGLE, 45.0)
    assert isinstance(result, Roof)
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert len(ridges) == 1
    ridge = ridges[0]
    assert ridge.length == pytest.approx(4.0)
    ends = [
        result.nodes[ridge.start],
        result.nodes[ridge.end],
    ]
    got = sorted((n.x, n.y, n.height) for n in ends)
    expected = [(3.0, 3.0, 3.0), (7.0, 3.0, 3.0)]
    for (gx, gy, gz), (ex, ey, ez) in zip(got, expected, strict=True):
        assert gx == pytest.approx(ex)
        assert gy == pytest.approx(ey)
        assert gz == pytest.approx(ez)
    assert result.ridge_height == pytest.approx(3.0)


def test_each_arc_is_ridge_hip_or_eave_and_reports_its_length() -> None:
    result = roof(RECTANGLE, 45.0)
    assert isinstance(result, Roof)
    kinds = {arc.kind for arc in result.arcs}
    assert kinds == {"ridge", "hip", "eave"}
    by_kind: dict[str, list[float]] = {"ridge": [], "hip": [], "eave": []}
    for arc in result.arcs:
        assert arc.length > 0.0
        by_kind[arc.kind].append(arc.length)
    assert len(by_kind["eave"]) == 4
    assert sorted(by_kind["eave"]) == pytest.approx([6.0, 6.0, 10.0, 10.0])
    assert len(by_kind["hip"]) == 4
    hip_3d = math.hypot(3.0, 3.0, 3.0)
    assert by_kind["hip"] == pytest.approx([hip_3d, hip_3d, hip_3d, hip_3d])
    assert by_kind["ridge"] == pytest.approx([4.0])


def _line_distance(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> float:
    """Perpendicular distance from a point to an edge's supporting line."""
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    return abs((px - ax) * dy - (py - ay) * dx) / math.hypot(dx, dy)


def test_skeleton_nodes_are_equidistant_from_their_defining_edges() -> None:
    pitch = 30.0
    result = roof(RECTANGLE, pitch)
    assert isinstance(result, Roof)
    n = len(RECTANGLE)
    cot = 1.0 / math.tan(math.radians(pitch))
    for node in result.nodes:
        if node.height <= 1e-9:
            continue
        distances = [
            _line_distance(
                (node.x, node.y),
                RECTANGLE[i],
                RECTANGLE[(i + 1) % n],
            )
            for i in range(n)
        ]
        inset = node.height * cot
        defining = [d for d in distances if math.isclose(d, inset, abs_tol=1e-8)]
        assert len(defining) >= 2
        assert defining == pytest.approx([inset] * len(defining))


def test_face_plan_areas_sum_to_the_footprint_area() -> None:
    from shapely.geometry import Polygon  # type: ignore[import-untyped]

    result = roof(RECTANGLE, 45.0)
    assert isinstance(result, Roof)
    footprint_area = Polygon(RECTANGLE).area
    assert sum(face.plan_area for face in result.faces) == pytest.approx(footprint_area)
    for face in result.faces:
        poly = Polygon(
            [(result.nodes[i].x, result.nodes[i].y) for i in face.node_indices]
        )
        assert face.plan_area == pytest.approx(poly.area)


def test_each_face_sloped_area_is_plan_area_over_cosine_of_pitch() -> None:
    pitch = 30.0
    result = roof(SQUARE, pitch)
    assert isinstance(result, Roof)
    cosine = math.cos(math.radians(pitch))
    for face in result.faces:
        assert face.edge_index in range(4)
        assert face.pitch == pytest.approx(pitch)
        assert face.sloped_area == pytest.approx(face.plan_area / cosine)


def test_roof_reports_node_heights_ridge_height_and_total_sloped_area() -> None:
    pitch = 30.0
    result = roof(SQUARE, pitch)
    assert isinstance(result, Roof)
    apex = 5.0 * math.tan(math.radians(pitch))
    heights = [node.height for node in result.nodes]
    assert any(h <= 1e-9 for h in heights)
    assert any(h == pytest.approx(apex) for h in heights)
    assert result.ridge_height == pytest.approx(apex)
    assert result.total_sloped_area == pytest.approx(
        100.0 / math.cos(math.radians(pitch))
    )


def test_returned_roof_carries_no_weight() -> None:
    for cls in (Roof, Face, Arc, Node):
        assert "weight" not in cls.__dataclass_fields__
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    dumped = str(result)
    assert "weight" not in dumped
    mixed_pitches: list[Pitch] = [60.0, 45.0, 60.0, 45.0]
    mixed = roof(SQUARE, mixed_pitches)
    assert isinstance(mixed, Roof)
    assert "weight" not in str(mixed)


def test_uniform_pitch_list_matches_the_same_pitch_as_a_scalar() -> None:
    as_scalar = roof(SQUARE, 45.0)
    uniform: list[Pitch] = [45.0, 45.0, 45.0, 45.0]
    as_list = roof(SQUARE, uniform)
    assert isinstance(as_scalar, Roof)
    assert isinstance(as_list, Roof)
    assert as_scalar == as_list


def test_each_face_carries_its_own_pitch_and_names_its_edge() -> None:
    pitches: list[Pitch] = [60.0, 45.0, 30.0, 45.0]
    result = roof(SQUARE, pitches)
    assert isinstance(result, Roof)
    by_edge = {face.edge_index: face for face in result.faces}
    assert sorted(by_edge) == [0, 1, 2, 3]
    for i, pitch in enumerate(pitches):
        assert by_edge[i].pitch == pytest.approx(pitch)


def test_clockwise_per_edge_pitches_follow_the_caller_edge_indices() -> None:
    clockwise = list(reversed(SQUARE))
    pitches: list[Pitch] = [60.0, 45.0, 30.0, 20.0]
    result = roof(clockwise, pitches)
    assert isinstance(result, Roof)
    by_edge = {face.edge_index: face for face in result.faces}
    for i, pitch in enumerate(pitches):
        assert by_edge[i].pitch == pytest.approx(pitch)


# Opposite sides 60°, adjacent sides 45°. East and west (weight 1) meet
# first at t = 5 m; south and north (weight 1/√3) only reach y = 5/√3.
SQUARE_ALT_PITCHES: list[Pitch] = [60.0, 45.0, 60.0, 45.0]


def test_weighted_square_has_hand_computed_ridge() -> None:
    result = roof(SQUARE, SQUARE_ALT_PITCHES)
    assert isinstance(result, Roof)
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert len(ridges) == 1
    ridge = ridges[0]
    inset = 5.0 / math.sqrt(3.0)
    assert ridge.length == pytest.approx(10.0 - 2.0 * inset)
    ends = sorted(
        (n.x, n.y, n.height)
        for n in (result.nodes[ridge.start], result.nodes[ridge.end])
    )
    expected = sorted([(5.0, inset, 5.0), (5.0, 10.0 - inset, 5.0)])
    for (gx, gy, gz), (ex, ey, ez) in zip(ends, expected, strict=True):
        assert gx == pytest.approx(ex)
        assert gy == pytest.approx(ey)
        assert gz == pytest.approx(ez)
    assert result.ridge_height == pytest.approx(5.0)
    assert result.validity.is_terrain is True


def test_steeper_face_has_the_larger_sloped_over_plan_excess() -> None:
    result = roof(SQUARE, SQUARE_ALT_PITCHES)
    assert isinstance(result, Roof)
    by_edge = {face.edge_index: face for face in result.faces}
    for face in result.faces:
        assert face.sloped_area > face.plan_area
    steep = by_edge[0].sloped_area / by_edge[0].plan_area
    shallow = by_edge[1].sloped_area / by_edge[1].plan_area
    assert steep == pytest.approx(1.0 / math.cos(math.radians(60.0)))
    assert shallow == pytest.approx(1.0 / math.cos(math.radians(45.0)))
    assert steep > shallow


def test_core_imports_nothing_outside_the_standard_library() -> None:
    import ast
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "krovlab"
    stdlib = sys.stdlib_module_names
    for path in root.rglob("*.py"):
        # Optional extra: Plotly lives here so the core stays stdlib-only.
        if path.name == "viz.py" or "viz" in path.relative_to(root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for name in names:
                if name == "krovlab":
                    continue
                assert name in stdlib, f"{path} imports {name}"


def test_tie_breaking_rule_is_documented_next_to_the_queue() -> None:
    import krovlab._skeleton as wavefront

    doc = wavefront.__doc__
    assert doc is not None
    assert "split events before edge" in doc
    assert "event point" in doc
    assert "COLLOCATION_M" in doc


def test_adjacent_parallel_weight_ambiguity_is_documented() -> None:
    import krovlab._skeleton as wavefront

    doc = wavefront.__doc__
    assert doc is not None
    assert "adjacent parallel" in doc.lower()
    assert "differing" in doc.lower()


def test_clockwise_square_preserves_caller_edge_indices() -> None:
    clockwise = list(reversed(SQUARE))
    result = roof(clockwise, 45.0)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(5.0)
    face0 = next(face for face in result.faces if face.edge_index == 0)
    eave = {
        (result.nodes[face0.node_indices[0]].x, result.nodes[face0.node_indices[0]].y),
        (result.nodes[face0.node_indices[1]].x, result.nodes[face0.node_indices[1]].y),
    }
    assert eave == {(0.0, 10.0), (10.0, 10.0)}


RIGHT_TRIANGLE = [(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)]

# Asymmetric L: reflex at (3, 6), not on a square diagonal, so the valley
# hits the opposite eave in its interior rather than a corner.
L_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]


def test_right_triangle_at_forty_five_has_hand_computed_incenter_apex() -> None:
    result = roof(RIGHT_TRIANGLE, 45.0)
    assert isinstance(result, Roof)
    assert result.ridge_height == pytest.approx(1.0)
    hips = [arc for arc in result.arcs if arc.kind == "hip"]
    assert len(hips) == 3
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert ridges == []
    apex = [node for node in result.nodes if node.height > 1e-9]
    assert len(apex) == 1
    assert apex[0].x == pytest.approx(1.0)
    assert apex[0].y == pytest.approx(1.0)


def test_l_shape_at_uniform_pitch_has_exactly_one_valley() -> None:
    result = roof(L_SHAPE, 45.0)
    assert isinstance(result, Roof)
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 1
    valley = valleys[0]
    # Reflex at (3, 6) to the split/collapse at (1.5, 4.5, 1.5).
    assert valley.length == pytest.approx(1.5 * math.sqrt(3.0))
    ends = [result.nodes[valley.start], result.nodes[valley.end]]
    eave_end = next(n for n in ends if n.height <= 1e-9)
    assert eave_end.x == pytest.approx(3.0)
    assert eave_end.y == pytest.approx(6.0)
    hips = [arc for arc in result.arcs if arc.kind == "hip"]
    assert hips
    assert all(h.length > 0.0 for h in hips)
    assert result.validity.is_terrain is True


def test_l_shape_with_per_edge_pitch_is_a_terrain_with_a_valley() -> None:
    pitches: list[Pitch] = [45.0, 30.0, 45.0, 60.0, 45.0, 30.0]
    result = roof(L_SHAPE, pitches)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 1
    by_edge = {face.edge_index: face.pitch for face in result.faces}
    assert by_edge == {i: pitches[i] for i in range(6)}


T_SHAPE = [
    (0.0, 6.0),
    (4.0, 6.0),
    (4.0, 0.0),
    (8.0, 0.0),
    (8.0, 6.0),
    (12.0, 6.0),
    (12.0, 10.0),
    (0.0, 10.0),
]

U_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 8.0),
    (7.0, 8.0),
    (7.0, 3.0),
    (3.0, 3.0),
    (3.0, 8.0),
    (0.0, 8.0),
]

SYMMETRIC_U = [
    (0.0, 0.0),
    (12.0, 0.0),
    (12.0, 8.0),
    (9.0, 8.0),
    (9.0, 3.0),
    (3.0, 3.0),
    (3.0, 8.0),
    (0.0, 8.0),
]

# Two reflex corners whose valleys meet the same opposite eave.
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

# Rectangular bite: the reflex at the notch tip hits the opposite eave
# in its interior, so the event log records a split rather than an edge.
NOTCHED = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 8.0),
    (6.0, 8.0),
    (5.0, 6.0),
    (4.0, 8.0),
    (0.0, 8.0),
]


def test_t_shape_is_independent_of_which_vertex_starts_the_ring() -> None:
    areas = []
    for k in range(len(T_SHAPE)):
        rotated = T_SHAPE[k:] + T_SHAPE[:k]
        result = roof(rotated, 45.0)
        assert isinstance(result, Roof)
        assert result.validity.is_terrain is True
        areas.append(sum(face.plan_area for face in result.faces))
    assert areas == pytest.approx([areas[0]] * len(areas))
    result = roof(T_SHAPE, 45.0)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 2
    assert all(v.length > 0.0 for v in valleys)


def test_u_shape_produces_a_valid_roof_with_valleys() -> None:
    result = roof(U_SHAPE, 45.0)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 2
    assert all(v.length > 0.0 for v in valleys)


def test_reflex_skeleton_nodes_are_equidistant_from_their_defining_edges() -> None:
    pitch = 30.0
    result = roof(L_SHAPE, pitch)
    assert isinstance(result, Roof)
    n = len(L_SHAPE)
    cot = 1.0 / math.tan(math.radians(pitch))
    for node in result.nodes:
        if node.height <= 1e-9:
            continue
        distances = [
            _line_distance((node.x, node.y), L_SHAPE[i], L_SHAPE[(i + 1) % n])
            for i in range(n)
        ]
        inset = node.height * cot
        defining = [d for d in distances if math.isclose(d, inset, abs_tol=1e-8)]
        assert len(defining) >= 2
        assert defining == pytest.approx([inset] * len(defining))


def test_symmetric_u_is_deterministic_under_simultaneous_events() -> None:
    first = roof(SYMMETRIC_U, 45.0)
    second = roof(SYMMETRIC_U, 45.0)
    assert isinstance(first, Roof)
    assert isinstance(second, Roof)
    assert first == second
    assert first.validity.is_terrain is True


def test_colliding_split_footprint_does_not_raise() -> None:
    result = roof(PLUS, 45.0)
    assert isinstance(result, (Roof, Failure))


def test_notched_rectangle_event_log_records_a_split() -> None:
    result = roof(NOTCHED, 45.0, events=True)
    assert not isinstance(result, Failure)
    built, events = result
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is True
    assert any(event.kind == "split" for event in events)
    times = [event.time for event in events]
    assert times == sorted(times)


# 10 m square, 4 m courtyard centred. At 45° both wavefronts move at
# 1 m/m of height, so they meet halfway across the 3 m strip: ridge 1.5 m.
# Plan area is 100 - 16 = 84 m2, eight faces (four outer, four inward).
COURTYARD_HOLE = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]


def test_rectangular_footprint_with_rectangular_hole_is_a_valid_roof() -> None:
    result = roof(SQUARE, 45.0, holes=[COURTYARD_HOLE])
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert result.ridge_height == pytest.approx(1.5)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(84.0)
    assert len(result.faces) == 8


def test_courtyard_arcs_are_classified_and_measured() -> None:
    result = roof(SQUARE, 45.0, holes=[COURTYARD_HOLE])
    assert isinstance(result, Roof)
    by_kind: dict[str, list[float]] = {"ridge": [], "hip": [], "valley": [], "eave": []}
    for arc in result.arcs:
        assert arc.length > 0.0
        by_kind[arc.kind].append(arc.length)
    # Four outer eaves of 10 m, four courtyard eaves of 4 m.
    assert sorted(by_kind["eave"]) == pytest.approx(
        [4.0, 4.0, 4.0, 4.0, 10.0, 10.0, 10.0, 10.0]
    )
    # Ridge square of side 7 m where the two wavefronts meet.
    assert by_kind["ridge"] == pytest.approx([7.0, 7.0, 7.0, 7.0])
    hip_3d = 1.5 * math.sqrt(3.0)
    assert by_kind["hip"] == pytest.approx([hip_3d, hip_3d, hip_3d, hip_3d])
    assert by_kind["valley"] == pytest.approx([hip_3d, hip_3d, hip_3d, hip_3d])
    valley_eaves = [
        result.nodes[end]
        for arc in result.arcs
        if arc.kind == "valley"
        for end in (arc.start, arc.end)
        if result.nodes[end].height <= 1e-9
    ]
    hole_corners = {(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)}
    got = {(round(n.x, 9), round(n.y, 9)) for n in valley_eaves}
    assert got == hole_corners


TWO_HOLES = [
    [(1.5, 1.5), (4.0, 1.5), (4.0, 4.0), (1.5, 4.0)],
    [(6.0, 6.0), (8.5, 6.0), (8.5, 8.5), (6.0, 8.5)],
]


def test_two_holes_produce_a_valid_roof() -> None:
    result = roof(SQUARE, 45.0, holes=TWO_HOLES)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert sum(face.plan_area for face in result.faces) == pytest.approx(
        100.0 - 2 * 6.25
    )
    assert len(result.faces) == 12
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 8
    assert all(v.length > 0.0 for v in valleys)


def test_clockwise_hole_matches_counterclockwise_hole() -> None:
    ccw = roof(SQUARE, 45.0, holes=[COURTYARD_HOLE])
    cw = roof(SQUARE, 45.0, holes=[list(reversed(COURTYARD_HOLE))])
    assert isinstance(ccw, Roof)
    assert isinstance(cw, Roof)
    assert ccw.ridge_height == pytest.approx(cw.ridge_height)
    assert sum(f.plan_area for f in ccw.faces) == pytest.approx(
        sum(f.plan_area for f in cw.faces)
    )


def test_holes_work_with_per_edge_pitch() -> None:
    # Outer south 60°, courtyard south 30°, the rest 45°. Concatenated
    # pitch list is outer edges then hole edges.
    pitches: list[Pitch] = [60.0, 45.0, 45.0, 45.0, 30.0, 45.0, 45.0, 45.0]
    result = roof(SQUARE, pitches, holes=[COURTYARD_HOLE])
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    by_edge = {face.edge_index: face.pitch for face in result.faces}
    assert by_edge == {i: pitches[i] for i in range(8)}
    hole_faces = [face for face in result.faces if face.edge_index >= 4]
    assert hole_faces
    assert all(face.plan_area > 0.0 for face in hole_faces)


def test_pitch_list_for_a_holed_footprint_must_cover_every_edge() -> None:
    result = roof(SQUARE, [45.0, 45.0, 45.0, 45.0], holes=[COURTYARD_HOLE])
    assert isinstance(result, Failure)
    assert result.kind == "pitch_count"


def test_a_hole_that_cannot_close_is_a_stated_failure() -> None:
    # A 1 cm courtyard strip still roofs (ridge 5 mm). If the wavefront
    # stalls the result is Failure(incomplete), never an exception.
    huge = [(0.01, 0.01), (9.99, 0.01), (9.99, 9.99), (0.01, 9.99)]
    result = roof(SQUARE, 45.0, holes=[huge])
    assert isinstance(result, (Roof, Failure))
    if isinstance(result, Failure):
        assert result.kind == "incomplete"
        assert result.reason
    else:
        assert sum(face.plan_area for face in result.faces) == pytest.approx(
            100.0 - 9.98 * 9.98
        )
        assert result.ridge_height == pytest.approx(0.005)


# 10 x 6 m rectangle. East (the 6 m edge at x = 10) gabled; the rest 45.
# The east wall does not move. South and north meet it at (10, 3, 3).
# West still hips in to (3, 3, 3). Ridge 7 m. Two verges of length 3*sqrt(2).
ONE_GABLE: list[Pitch] = [45.0, 90.0, 45.0, 45.0]


def test_rectangle_with_one_gabled_edge_has_no_face_there_and_two_verges() -> None:
    result = roof(RECTANGLE, ONE_GABLE)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    by_edge = {face.edge_index: face for face in result.faces}
    assert 1 not in by_edge
    assert sorted(by_edge) == [0, 2, 3]
    verges = [arc for arc in result.arcs if arc.kind == "verge"]
    assert len(verges) == 2
    verge_3d = 3.0 * math.sqrt(2.0)
    assert sorted(arc.length for arc in verges) == pytest.approx([verge_3d, verge_3d])
    hips = [arc for arc in result.arcs if arc.kind == "hip"]
    assert len(hips) == 2
    eaves = [arc for arc in result.arcs if arc.kind == "eave"]
    assert len(eaves) == 3
    assert result.ridge_height == pytest.approx(3.0)


BOTH_SHORT_GABLES: list[Pitch] = [45.0, 90.0, 45.0, 90.0]


def test_rectangle_with_both_short_edges_gabled_is_a_ridged_roof() -> None:
    result = roof(RECTANGLE, BOTH_SHORT_GABLES)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    assert sorted(face.edge_index for face in result.faces) == [0, 2]
    for face in result.faces:
        assert face.plan_area == pytest.approx(30.0)
    verges = [arc for arc in result.arcs if arc.kind == "verge"]
    assert len(verges) == 4
    verge_3d = 3.0 * math.sqrt(2.0)
    assert sorted(arc.length for arc in verges) == pytest.approx(
        [verge_3d, verge_3d, verge_3d, verge_3d]
    )
    assert [arc for arc in result.arcs if arc.kind == "hip"] == []
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    assert len(ridges) == 1
    assert ridges[0].length == pytest.approx(10.0)
    eaves = [arc for arc in result.arcs if arc.kind == "eave"]
    assert sorted(arc.length for arc in eaves) == pytest.approx([10.0, 10.0])
    assert result.ridge_height == pytest.approx(3.0)


def test_gabled_plan_areas_sum_to_the_footprint_area() -> None:
    from shapely.geometry import Polygon

    result = roof(RECTANGLE, ONE_GABLE)
    assert isinstance(result, Roof)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(
        Polygon(RECTANGLE).area
    )


def test_gabling_every_edge_is_a_stated_failure() -> None:
    result = roof(SQUARE, 90.0)
    assert isinstance(result, Failure)
    assert result.kind == "incomplete"
    assert result.reason
    listed = roof(RECTANGLE, [90.0, 90.0, 90.0, 90.0])
    assert isinstance(listed, Failure)
    assert listed.kind == "incomplete"


def test_gables_work_with_reflex_corners_and_per_edge_pitch() -> None:
    # East end of the L gabled; mixed pitch on the remaining edges.
    pitches: list[Pitch] = [45.0, 90.0, 30.0, 45.0, 45.0, 30.0]
    result = roof(L_SHAPE, pitches)
    assert isinstance(result, Roof)
    assert result.validity.is_terrain is True
    by_edge = {face.edge_index: face.pitch for face in result.faces}
    assert 1 not in by_edge
    assert by_edge == {0: 45.0, 2: 30.0, 3: 45.0, 4: 45.0, 5: 30.0}
    valleys = [arc for arc in result.arcs if arc.kind == "valley"]
    assert len(valleys) == 1
    verges = [arc for arc in result.arcs if arc.kind == "verge"]
    assert len(verges) == 2
    assert all(v.length > 0.0 for v in verges)
    assert sum(face.plan_area for face in result.faces) == pytest.approx(72.0)
