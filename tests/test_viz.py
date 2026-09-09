"""Smoke tests for the optional visualisation module.

Visualisation consumes a Roof and returns a Plotly figure. Tests assert
the figure builds and that the public contract is met — not pixels.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from krovlab import Pitch, Roof, roof

RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
L_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]
COURTYARD = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]


def _rectangle_roof() -> Roof:
    result = roof(RECTANGLE, 45.0)
    assert isinstance(result, Roof)
    return result


def _mesh_plan_area(mesh: Any) -> float:
    total = 0.0
    for a, b, c in zip(mesh.i, mesh.j, mesh.k, strict=True):
        ax, ay = float(mesh.x[a]), float(mesh.y[a])
        bx, by = float(mesh.x[b]), float(mesh.y[b])
        cx, cy = float(mesh.x[c]), float(mesh.y[c])
        total += abs(0.5 * ((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)))
    return total


def test_plan_view_builds_from_a_roof() -> None:
    from plotly.graph_objects import Figure  # type: ignore[import-untyped]

    from krovlab.viz import plan_view

    fig = plan_view(_rectangle_roof())
    assert isinstance(fig, Figure)
    assert fig.data


def test_plan_view_builds_from_a_gabled_roof() -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import plan_view

    result = roof(RECTANGLE, [45.0, 90.0, 45.0, 45.0])
    assert isinstance(result, Roof)
    fig = plan_view(result)
    assert isinstance(fig, Figure)
    verge = next(trace for trace in fig.data if trace.name == "verge")
    assert any(x == x for x in verge.x)


GLOSSARY_ARC_KINDS = ("ridge", "hip", "valley", "eave", "verge")


def test_plan_view_legend_uses_glossary_arc_names() -> None:
    from krovlab.viz import plan_view

    names = {trace.name for trace in plan_view(_rectangle_roof()).data}
    for kind in GLOSSARY_ARC_KINDS:
        assert kind in names


def test_plan_view_annotates_node_heights() -> None:
    from krovlab.viz import plan_view

    built = _rectangle_roof()
    fig = plan_view(built)
    texts: list[str] = []
    for trace in fig.data:
        if trace.text is not None:
            texts.extend(str(t) for t in trace.text)
    for node in built.nodes:
        assert any(f"{node.height:.2f}" in text for text in texts)


def test_plan_view_writes_self_contained_html(tmp_path: Path) -> None:
    from krovlab.viz import plan_view, write_html

    path = tmp_path / "plan.html"
    write_html(plan_view(_rectangle_roof()), path)
    html = path.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<")
    assert "Plotly" in html
    sources = re.findall(r"<script[^>]+src=['\"]([^'\"]+)['\"]", html, flags=re.I)
    assert not any(src.startswith(("http://", "https://", "//")) for src in sources)


def test_viz_reaches_only_the_roof_value() -> None:
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "src" / "krovlab" / "viz.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    internals = ("krovlab._skeleton", "krovlab._input", "krovlab._validity")
    for name in imported:
        assert name not in internals
        assert not any(name.startswith(f"{mod}.") for mod in internals)


def test_solid_view_builds_from_a_roof() -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import solid_view

    fig = solid_view(_rectangle_roof())
    assert isinstance(fig, Figure)
    assert fig.data
    assert fig.layout.scene is not None


def test_solid_view_face_heights_match_the_roof_nodes() -> None:
    from krovlab.viz import solid_view

    built = _rectangle_roof()
    mesh = next(trace for trace in solid_view(built).data if trace.type == "mesh3d")
    assert list(mesh.z) == [node.height for node in built.nodes]
    used = set(mesh.i) | set(mesh.j) | set(mesh.k)
    for face in built.faces:
        assert set(face.node_indices) <= used


def test_solid_view_legend_uses_glossary_arc_names() -> None:
    from krovlab.viz import solid_view

    names = {trace.name for trace in solid_view(_rectangle_roof()).data}
    for kind in GLOSSARY_ARC_KINDS:
        assert kind in names


def test_solid_view_writes_self_contained_html(tmp_path: Path) -> None:
    from krovlab.viz import solid_view, write_html

    path = tmp_path / "solid.html"
    write_html(solid_view(_rectangle_roof()), path)
    html = path.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<")
    assert "Plotly" in html
    sources = re.findall(r"<script[^>]+src=['\"]([^'\"]+)['\"]", html, flags=re.I)
    assert not any(src.startswith(("http://", "https://", "//")) for src in sources)


@pytest.mark.parametrize(
    ("footprint", "pitch", "roof_kwargs"),
    [
        (RECTANGLE, 45.0, {}),
        (L_SHAPE, 45.0, {}),
        (SQUARE, 45.0, {"holes": [COURTYARD]}),
        (RECTANGLE, [45.0, 90.0, 45.0, 45.0], {}),
        (RECTANGLE, 45.0, {"overhang": 0.5}),
        (SQUARE, [60.0, 45.0, 60.0, 45.0], {}),
    ],
    ids=["convex", "reflex", "holed", "gabled", "overhung", "per-edge-pitch"],
)
def test_solid_view_builds_from_supported_footprint_classes(
    footprint: list[tuple[float, float]],
    pitch: Pitch | list[Pitch],
    roof_kwargs: dict[str, Any],
) -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import solid_view

    result = roof(footprint, pitch, **roof_kwargs)
    assert isinstance(result, Roof)
    fig = solid_view(result)
    assert isinstance(fig, Figure)
    mesh = next(trace for trace in fig.data if trace.type == "mesh3d")
    assert list(mesh.z) == [node.height for node in result.nodes]
    assert len(mesh.i) > 0
    assert _mesh_plan_area(mesh) == pytest.approx(
        sum(face.plan_area for face in result.faces)
    )


def test_wavefront_view_builds_from_a_roof_at_a_chosen_time() -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import wavefront_view

    built = _rectangle_roof()
    fig = wavefront_view(built, time=1.5)
    assert isinstance(fig, Figure)
    assert fig.data
    names = {trace.name for trace in fig.data}
    assert "footprint" in names
    assert "wavefront" in names


def test_wavefront_steps_produces_a_sequence_of_views() -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import wavefront_steps

    figs = wavefront_steps(_rectangle_roof())
    assert len(figs) > 1
    for fig in figs:
        assert isinstance(fig, Figure)
        assert fig.data
        names = {trace.name for trace in fig.data}
        assert "footprint" in names
        assert "wavefront" in names


def test_event_times_from_the_log_are_reachable_as_step_points() -> None:
    from krovlab.viz import wavefront_steps, wavefront_view

    result = roof(RECTANGLE, 45.0, events=True)
    assert isinstance(result, tuple)
    built, events = result
    assert events
    figs = wavefront_steps(built, events)
    assert len(figs) == 1 + len({event.time for event in events})
    for event in events:
        fig = wavefront_view(built, event.time)
        assert fig.data
        names = {trace.name for trace in fig.data}
        assert "wavefront" in names


def test_wavefront_view_accepts_negative_and_past_end_times() -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import wavefront_view

    built = _rectangle_roof()
    for time in (-1.0, built.ridge_height + 10.0):
        fig = wavefront_view(built, time)
        assert isinstance(fig, Figure)
        names = {trace.name for trace in fig.data}
        assert "footprint" in names
        assert "wavefront" in names
        wavefront = next(trace for trace in fig.data if trace.name == "wavefront")
        assert not any(x == x for x in wavefront.x)


def test_wavefront_view_writes_self_contained_html(tmp_path: Path) -> None:
    from krovlab.viz import wavefront_view, write_html

    path = tmp_path / "wavefront.html"
    write_html(wavefront_view(_rectangle_roof(), time=1.5), path)
    html = path.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<")
    assert "Plotly" in html
    sources = re.findall(r"<script[^>]+src=['\"]([^'\"]+)['\"]", html, flags=re.I)
    assert not any(src.startswith(("http://", "https://", "//")) for src in sources)


@pytest.mark.parametrize(
    ("footprint", "pitch", "roof_kwargs"),
    [
        (RECTANGLE, 45.0, {}),
        (L_SHAPE, 45.0, {}),
        (SQUARE, 45.0, {"holes": [COURTYARD]}),
        (RECTANGLE, [45.0, 90.0, 45.0, 45.0], {}),
        (RECTANGLE, 45.0, {"overhang": 0.5}),
        (SQUARE, [60.0, 45.0, 60.0, 45.0], {}),
    ],
    ids=["convex", "reflex", "holed", "gabled", "overhung", "per-edge-pitch"],
)
def test_wavefront_view_builds_from_supported_footprint_classes(
    footprint: list[tuple[float, float]],
    pitch: Pitch | list[Pitch],
    roof_kwargs: dict[str, Any],
) -> None:
    from plotly.graph_objects import Figure

    from krovlab.viz import wavefront_steps, wavefront_view

    result = roof(footprint, pitch, **roof_kwargs)
    assert isinstance(result, Roof)
    mid = result.ridge_height / 2.0
    fig = wavefront_view(result, time=mid)
    assert isinstance(fig, Figure)
    assert next(trace for trace in fig.data if trace.name == "wavefront")
    figs = wavefront_steps(result)
    assert len(figs) > 1


def test_plan_view_without_walls_has_no_walls_trace() -> None:
    from krovlab.viz import plan_view

    names = {trace.name for trace in plan_view(_rectangle_roof()).data}
    assert "walls" not in names
    assert "footprint" in names


def test_plan_view_draws_walls_inside_overhanging_eaves() -> None:
    from krovlab.viz import plan_view

    result = roof(RECTANGLE, 45.0, overhang=0.5)
    assert isinstance(result, Roof)
    fig = plan_view(result, walls=RECTANGLE)
    names = {trace.name for trace in fig.data}
    assert "walls" in names
    assert "roof" in names
    walls = next(trace for trace in fig.data if trace.name == "walls")
    assert 0.0 in list(walls.x)
    assert 10.0 in list(walls.x)
    eaves = next(trace for trace in fig.data if trace.name == "eave")
    finite = [x for x in eaves.x if x == x]
    assert any(abs(x - (-0.5)) < 1e-9 for x in finite)
    assert any(abs(x - 10.5) < 1e-9 for x in finite)


def test_plan_view_draws_wall_holes() -> None:
    from krovlab.viz import plan_view

    result = roof(SQUARE, 45.0, holes=[COURTYARD], overhang=0.5)
    assert isinstance(result, Roof)
    fig = plan_view(result, walls=SQUARE, wall_holes=[COURTYARD])
    hole = next(trace for trace in fig.data if trace.name == "walls (hole)")
    assert 3.0 in list(hole.x)
    assert 7.0 in list(hole.x)


def test_solid_view_draws_walls_at_height_zero() -> None:
    from krovlab.viz import solid_view

    result = roof(RECTANGLE, 45.0, overhang=0.5)
    assert isinstance(result, Roof)
    fig = solid_view(result, walls=RECTANGLE)
    walls = next(trace for trace in fig.data if trace.name == "walls")
    assert set(walls.z) <= {0.0}
    assert 0.0 in list(walls.x)
    assert 10.0 in list(walls.x)


def test_core_does_not_import_viz() -> None:
    import ast

    root = Path(__file__).resolve().parents[1] / "src" / "krovlab"
    for path in root.rglob("*.py"):
        if path.name == "viz.py" or "viz" in path.relative_to(root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert module != "krovlab.viz"
                assert not module.startswith("krovlab.viz.")
                assert "viz" not in module.split(".")


def test_plan_view_of_a_project_draws_every_cell() -> None:
    from krovlab import Cell, Project, project
    from krovlab.viz import plan_view

    garage = [(12.0, 0.0), (17.0, 0.0), (17.0, 6.0), (12.0, 6.0)]
    result = project([Cell(RECTANGLE, 45.0), Cell(garage, 45.0)])
    assert isinstance(result, Project)
    fig = plan_view(result)
    fills = [trace for trace in fig.data if trace.name and "footprint" in trace.name]
    assert len(fills) == len(result.roofs)
    xs = [float(x) for trace in fills for x in trace.x if x == x]
    assert min(xs) == pytest.approx(0.0)
    assert max(xs) == pytest.approx(17.0)


def test_plan_view_builds_from_a_two_cell_project() -> None:
    from plotly.graph_objects import Figure

    from krovlab import Cell, Project, project
    from krovlab.viz import plan_view

    garage = [(12.0, 0.0), (17.0, 0.0), (17.0, 6.0), (12.0, 6.0)]
    result = project([Cell(RECTANGLE, 45.0), Cell(garage, 45.0)])
    assert isinstance(result, Project)
    fig = plan_view(result)
    assert isinstance(fig, Figure)
    assert fig.data
    names = {trace.name for trace in fig.data}
    for kind in GLOSSARY_ARC_KINDS:
        assert kind in names


def test_solid_view_builds_from_a_two_cell_project() -> None:
    from plotly.graph_objects import Figure

    from krovlab import Cell, Project, project
    from krovlab.viz import solid_view

    garage = [(12.0, 0.0), (17.0, 0.0), (17.0, 6.0), (12.0, 6.0)]
    result = project(
        [
            Cell(RECTANGLE, 45.0, eave_height=5.0),
            Cell(garage, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(result, Project)
    fig = solid_view(result)
    assert isinstance(fig, Figure)
    mesh = next(trace for trace in fig.data if trace.type == "mesh3d")
    assert list(mesh.z) == [node.height for node in result.nodes]
    used = set(mesh.i) | set(mesh.j) | set(mesh.k)
    for face in result.faces:
        assert set(face.node_indices) <= used
