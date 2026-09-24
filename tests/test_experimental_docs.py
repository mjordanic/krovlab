"""README and notebook for the experimental method.

Seams: the tracked README section, and notebooks/experimental-gnn.ipynb.
They are what a reader sees. Tests do not look at training logs.
"""

import json
from pathlib import Path

import plotly.graph_objects as go  # type: ignore[import-untyped]
import pytest

from krovlab import Failure, Roof

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
NOTEBOOK = ROOT / "notebooks" / "experimental-gnn.ipynb"


def _notebook_source() -> str:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    parts: list[str] = []
    for cell in nb["cells"]:
        src = cell.get("source", [])
        parts.append("".join(src) if isinstance(src, list) else str(src))
    return "\n".join(parts)


def test_readme_describes_the_experimental_entry_point() -> None:
    text = README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "roof_from_face_graph" in text
    assert "footprint" in lowered
    assert "overhang" in lowered
    assert "eave height" in lowered or "eave_height" in text
    assert "does not take a pitch" in lowered or "pitch is not" in lowered
    assert "failure" in lowered
    assert "face over several walls" in lowered
    assert "ridge layout" in lowered
    assert "keep the skeleton" in lowered


def test_readme_names_training_license_and_held_out_score() -> None:
    text = README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "uv run --extra gnn python -m krovlab.ren_gnn" in text
    assert "CC BY-NC 4.0" in text
    assert "commercial" in lowered
    assert "permission" in lowered
    assert "models/ren2021-face-adjacency.md" in text


def test_notebook_roofs_one_footprint_both_ways() -> None:
    source = _notebook_source()
    assert "roof(" in source
    assert "roof_from_face_graph(" in source
    assert "l_shape" in source or "footprint" in source


def test_notebook_shows_a_face_over_several_non_collinear_walls() -> None:
    source = _notebook_source()
    lowered = source.lower()
    assert "non-collinear" in lowered or "several walls" in lowered
    assert "node_indices" in source
    assert "[2, 3]" in source or "[2,3]" in source


def test_notebook_says_keep_the_skeleton_when_pitches_differ() -> None:
    source = _notebook_source()
    lowered = source.lower()
    assert "keep the skeleton" in lowered
    assert "pitches differ" in lowered
    assert "roof(" in source and "[" in source


def test_notebook_shows_a_named_failure_with_kind_and_reason() -> None:
    source = _notebook_source()
    assert "unliftable" in source or "no_face_graph" in source
    assert ".kind" in source
    assert ".reason" in source


def test_notebook_examples_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(go.Figure, "show", lambda *args, **kwargs: None)
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    ns: dict[str, object] = {}
    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", [])
        code = "".join(src) if isinstance(src, list) else str(src)
        exec(compile(code, "notebooks/experimental-gnn.ipynb", "exec"), ns)
    assert isinstance(ns["skeleton"], Roof)
    assert isinstance(ns["experimental"], Roof)
    mixed = ns["mixed"]
    assert isinstance(mixed, Roof)
    covering = [
        face for face in mixed.faces if {2, 3, 4} <= set(face.node_indices)
    ]
    assert covering
    assert len(mixed.faces) == 5
    failed = ns["missing_walls"]
    assert isinstance(failed, Failure)
    assert failed.kind == "unliftable"
    assert failed.reason
