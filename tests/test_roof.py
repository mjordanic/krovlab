"""Behaviour of the single public seam: roof(footprint, pitch)."""

import math

import pytest

from krovlab import Arc, Face, Failure, Node, Roof, roof

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_pitch_outside_open_zero_to_closed_ninety_is_refused() -> None:
    for pitch in (0.0, -10.0, 90.1):
        result = roof(SQUARE, pitch)
        assert isinstance(result, Failure)
    assert not isinstance(roof(SQUARE, 90.0), Failure)


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


def test_core_imports_nothing_outside_the_standard_library() -> None:
    import ast
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "krovlab"
    stdlib = sys.stdlib_module_names
    for path in root.rglob("*.py"):
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
    assert "vanishing original-edge index" in doc
    assert "COLLOCATION_M" in doc


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
