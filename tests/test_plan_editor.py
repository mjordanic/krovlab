"""Plan editor: metre-space actions write the same form fields the page POSTs.

The seam is ``createEditor`` in ``web/static/plan-editor.js``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from web.app import create_app

from krovlab import Cell, Pitch, Project, project

EDITOR_JS = Path(__file__).resolve().parents[1] / "web" / "static" / "plan-editor.js"

RECT = {
    "outer-x-0": "0",
    "outer-y-0": "0",
    "outer-x-1": "10",
    "outer-y-1": "0",
    "outer-x-2": "10",
    "outer-y-2": "6",
    "outer-x-3": "0",
    "outer-y-3": "6",
    "type-0": "hip",
    "pitch-0": "45",
    "type-1": "hip",
    "pitch-1": "45",
    "type-2": "hip",
    "pitch-2": "45",
    "type-3": "hip",
    "pitch-3": "45",
}


def _run_editor(body: str) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to drive the plan editor")
    script = f"""
const {{ createEditor }} = require({json.dumps(str(EDITOR_JS))});
const editor = createEditor({{ applyToAll: "45" }});
editor.loadFields({json.dumps(RECT)});
{body}
process.stdout.write(JSON.stringify({{
  fields: editor.fields(),
  rings: editor.rings(),
  selectedCell: editor.selectedCell(),
  selectedEdge: editor.selectedEdge(),
  selectedDormer: editor.selectedDormer()
}}));
"""
    proc = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    data: dict[str, Any] = json.loads(proc.stdout)
    return data


def _xy(fields: dict[str, str], prefix: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    i = 0
    while f"{prefix}outer-x-{i}" in fields:
        points.append(
            (
                float(fields[f"{prefix}outer-x-{i}"]),
                float(fields[f"{prefix}outer-y-{i}"]),
            )
        )
        i += 1
    return points


def test_add_detached_cell_places_a_closed_rectangle() -> None:
    result = _run_editor("editor.addDetachedCell();")
    fields = result["fields"]
    assert _xy(fields, "") == [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
    assert _xy(fields, "cell-1-") == [
        (11.0, 0.0),
        (16.0, 0.0),
        (16.0, 6.0),
        (11.0, 6.0),
    ]
    assert len(result["rings"]) == 2
    assert fields["cell-1-type-0"] == "hip"


def test_cannot_delete_the_last_cell() -> None:
    result = _run_editor("editor.deleteCell();")
    assert len(result["rings"]) == 1
    assert _xy(result["fields"], "")[0] == (0.0, 0.0)


def test_delete_removes_an_extra_cell() -> None:
    result = _run_editor(
        """
editor.addDetachedCell();
editor.deleteCell();
"""
    )
    assert len(result["rings"]) == 1
    assert "cell-1-outer-x-0" not in result["fields"]


def test_add_cell_on_selected_wall_shares_that_edge() -> None:
    result = _run_editor(
        """
editor.clickPlan(5, 0);
editor.addCellOnSelectedWall();
"""
    )
    fields = result["fields"]
    assert len(result["rings"]) == 2
    second = _xy(fields, "cell-1-")
    assert (0.0, 0.0) in second
    assert (10.0, 0.0) in second
    assert all(y <= 0.0 for _, y in second)


def test_add_vertex_splits_the_selected_wall() -> None:
    result = _run_editor(
        """
editor.clickPlan(5, 0);
editor.addVertexOnSelectedWall();
"""
    )
    assert _xy(result["fields"], "") == [
        (0.0, 0.0),
        (5.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (0.0, 6.0),
    ]


def test_clicking_an_edge_sets_pitch_or_marks_a_gable() -> None:
    result = _run_editor(
        """
editor.clickPlan(5, 0);
editor.setGable(true);
editor.clickPlan(5, 6);
editor.setPitch("30");
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 0
    assert result["selectedEdge"] == 2
    assert fields["type-0"] == "gable"
    assert fields["pitch-0"] == "90"
    assert fields["type-2"] == "hip"
    assert fields["pitch-2"] == "30"


def test_clicking_an_edge_sets_knee_height() -> None:
    result = _run_editor(
        """
editor.clickPlan(10, 3);
editor.setKneeHeight(3);
"""
    )
    fields = result["fields"]
    assert result["selectedEdge"] == 1
    assert fields["type-1"] == "knee"
    assert float(fields["knee-1"]) == 3.0


def test_clicking_an_edge_sets_gambrel() -> None:
    result = _run_editor(
        """
editor.clickPlan(5, 0);
editor.setGambrel(60, 30, Math.sqrt(3));
"""
    )
    fields = result["fields"]
    assert result["selectedEdge"] == 0
    assert fields["type-0"] == "gambrel"
    assert float(fields["pitch-0"]) == 60.0
    assert float(fields["gambrel-shallow-0"]) == 30.0
    assert float(fields["gambrel-break-0"]) == pytest.approx(3**0.5)


def test_selecting_a_cell_and_setting_eave_height_posts_on_that_cell() -> None:
    result = _run_editor(
        """
editor.setEaveHeight(5);
editor.addDetachedCell();
editor.setEaveHeight(7);
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 1
    assert float(fields["eave_height"]) == 5.0
    assert fields.get("use_eave_height") == "on"
    assert float(fields["cell-1-eave_height"]) == 7.0
    assert fields.get("cell-1-use_eave_height") == "on"


def test_editing_a_table_vertex_moves_it_on_the_plan() -> None:
    result = _run_editor("editor.moveVertex(0, 2, 10, 4);")
    assert _xy(result["fields"], "") == [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 4.0),
        (0.0, 6.0),
    ]
    assert result["rings"][0][2] == [10, 4]


def test_posted_editor_fields_for_the_5m_7m_pair_match_project() -> None:
    low = [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
    high = [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)]
    gables: list[Pitch] = [45.0, 90.0, 45.0, 90.0]
    built = project(
        [
            Cell(low, gables, eave_height=5.0),
            Cell(high, gables, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    result = _run_editor(
        """
editor.loadFields({
  "outer-x-0": "0", "outer-y-0": "0",
  "outer-x-1": "5", "outer-y-1": "0",
  "outer-x-2": "5", "outer-y-2": "6",
  "outer-x-3": "0", "outer-y-3": "6",
  "type-0": "hip", "pitch-0": "45",
  "type-1": "gable", "pitch-1": "90",
  "type-2": "hip", "pitch-2": "45",
  "type-3": "gable", "pitch-3": "90",
  "use_eave_height": "on", "eave_height": "5",
  "cell-1-outer-x-0": "5", "cell-1-outer-y-0": "0",
  "cell-1-outer-x-1": "10", "cell-1-outer-y-1": "0",
  "cell-1-outer-x-2": "10", "cell-1-outer-y-2": "6",
  "cell-1-outer-x-3": "5", "cell-1-outer-y-3": "6",
  "cell-1-type-0": "hip", "cell-1-pitch-0": "45",
  "cell-1-type-1": "gable", "cell-1-pitch-1": "90",
  "cell-1-type-2": "hip", "cell-1-pitch-2": "45",
  "cell-1-type-3": "gable", "cell-1-pitch-3": "90",
  "cell-1-use_eave_height": "on", "cell-1-eave_height": "7"
});
"""
    )
    data = {"example": "hip-rectangle", **result["fields"]}
    page = create_app().test_client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page


def test_apply_settings_keeps_typed_pitch_when_adding_a_cell() -> None:
    result = _run_editor(
        """
editor.applySettings(Object.assign({}, {
  "outer-x-0": "0", "outer-y-0": "0",
  "outer-x-1": "10", "outer-y-1": "0",
  "outer-x-2": "10", "outer-y-2": "6",
  "outer-x-3": "0", "outer-y-3": "6",
  "type-0": "hip", "pitch-0": "30",
  "type-1": "hip", "pitch-1": "45",
  "type-2": "hip", "pitch-2": "45",
  "type-3": "hip", "pitch-3": "45"
}));
editor.addDetachedCell();
"""
    )
    assert result["fields"]["pitch-0"] == "30"
    assert result["fields"]["cell-1-type-0"] == "hip"
    assert len(result["rings"]) == 2


def test_dormer_vertex_can_be_moved() -> None:
    dormer = {
        **RECT,
        "dormer-0-cell": "0",
        "dormer-0-x-0": "4",
        "dormer-0-y-0": "0.5",
        "dormer-0-x-1": "6",
        "dormer-0-y-1": "0.5",
        "dormer-0-x-2": "6",
        "dormer-0-y-2": "2",
        "dormer-0-x-3": "4",
        "dormer-0-y-3": "2",
        "dormer-0-type-0": "hip",
        "dormer-0-pitch-0": "45",
        "dormer-0-type-1": "gable",
        "dormer-0-pitch-1": "90",
        "dormer-0-type-2": "hip",
        "dormer-0-pitch-2": "45",
        "dormer-0-type-3": "gable",
        "dormer-0-pitch-3": "90",
    }
    result = _run_editor(
        f"""
editor.loadFields({json.dumps(dormer)});
editor.clickPlan(4, 0.5);
editor.moveDormerVertex(0, 0, 4.2, 0.6);
"""
    )
    fields = result["fields"]
    assert fields["dormer-0-x-0"] == "4.2"
    assert fields["dormer-0-y-0"] == "0.6"
    assert result["selectedDormer"] == 0


def test_hole_vertices_round_trip_in_fields() -> None:
    hole = {
        **RECT,
        "use_hole": "on",
        "hole-x-0": "3",
        "hole-y-0": "3",
        "hole-x-1": "7",
        "hole-y-1": "3",
        "hole-x-2": "7",
        "hole-y-2": "7",
        "hole-x-3": "3",
        "hole-y-3": "7",
        "type-4": "hip",
        "pitch-4": "45",
        "type-5": "hip",
        "pitch-5": "45",
        "type-6": "hip",
        "pitch-6": "45",
        "type-7": "hip",
        "pitch-7": "45",
    }
    result = _run_editor(f"editor.loadFields({json.dumps(hole)});")
    fields = result["fields"]
    assert fields["use_hole"] == "on"
    assert (fields["hole-x-0"], fields["hole-y-0"]) == ("3", "3")
    assert (fields["hole-x-2"], fields["hole-y-2"]) == ("7", "7")
    assert fields["type-4"] == "hip"


def test_roof_height_round_trips_in_fields() -> None:
    result = _run_editor(
        f"editor.loadFields({json.dumps({**RECT, 'roof_height': '2'})});"
    )
    assert result["fields"]["roof_height"] == "2"
