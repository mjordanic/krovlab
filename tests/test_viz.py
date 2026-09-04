"""Smoke tests for the optional visualisation module.

Visualisation consumes a Roof and returns a Plotly figure. Tests assert
the figure builds and that the public contract is met — not pixels.
"""

import re
from pathlib import Path

from krovlab import Roof, roof

RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]


def _rectangle_roof() -> Roof:
    result = roof(RECTANGLE, 45.0)
    assert isinstance(result, Roof)
    return result


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
