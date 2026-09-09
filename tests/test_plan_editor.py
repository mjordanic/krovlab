"""Plan editor: metre-space clicks write the same form fields the page POSTs.

The seam is ``createEditor`` in ``web/static/plan-editor.js``. Clicks are
metres, not pixels. HTTP tests in ``test_web.py`` assert the page still
POSTs those fields and has no JSON API.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from web.app import create_app

from krovlab import Cell, Dormer, Pitch, Project, project

EDITOR_JS = Path(__file__).resolve().parents[1] / "web" / "static" / "plan-editor.js"


def _run_editor(body: str) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to drive the plan editor")
    script = f"""
const {{ createEditor }} = require({json.dumps(str(EDITOR_JS))});
const editor = createEditor({{ applyToAll: "45" }});
{body}
process.stdout.write(JSON.stringify({{
  fields: editor.fields(),
  rings: editor.rings(),
  selectedCell: editor.selectedCell(),
  selectedEdge: editor.selectedEdge(),
  selectedEdges: editor.selectedEdges()
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


def test_closing_a_clicked_ring_writes_that_cells_tables() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
"""
    )
    fields = result["fields"]
    assert fields["edit_vertices"] == "on"
    assert _xy(fields, "") == [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
    assert fields["pitch-0"] == "45"
    assert fields["pitch-3"] == "45"
    assert "cell-1-outer-x-0" not in fields


def test_a_second_drawn_cell_does_not_insert_into_the_first() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.addCell();
editor.clickPlan(5, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(5, 6);
editor.closeRing();
"""
    )
    fields = result["fields"]
    assert _xy(fields, "") == [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
    assert _xy(fields, "cell-1-") == [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)]
    assert len(result["rings"]) == 2
    assert fields["cell-1-pitch-0"] == "45"


def test_selecting_a_cell_and_setting_eave_height_posts_on_that_cell() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.setEaveHeight(5);
editor.addCell();
editor.clickPlan(5, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(5, 6);
editor.closeRing();
editor.clickPlan(2.5, 3);
editor.clickPlan(7.5, 3);
editor.setEaveHeight(7);
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 1
    assert float(fields["eave_height"]) == 5.0
    assert float(fields["cell-1-eave_height"]) == 7.0


def test_clicking_an_edge_sets_pitch_or_marks_a_gable() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.clickPlan(2.5, 0);
editor.setGable(true);
editor.clickPlan(2.5, 6);
editor.setPitch("30");
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 0
    assert result["selectedEdge"] == 2
    assert fields["gable-0"] == "on"
    assert fields["pitch-0"] == "90"
    assert fields["pitch-2"] == "30"
    assert "gable-2" not in fields


def test_clicking_an_edge_sets_knee_height() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.clickPlan(10, 3);
editor.setKneeHeight(3);
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 0
    assert result["selectedEdge"] == 1
    assert float(fields["knee-1"]) == 3.0
    assert fields.get("knee-0", "0") in ("0", "0.0", "")


def test_clicking_an_edge_sets_gambrel() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.clickPlan(5, 0);
editor.setGambrel(60, 30, Math.sqrt(3));
"""
    )
    fields = result["fields"]
    assert result["selectedCell"] == 0
    assert result["selectedEdge"] == 0
    assert float(fields["pitch-0"]) == 60.0
    assert float(fields["gambrel-shallow-0"]) == 30.0
    assert float(fields["gambrel-break-0"]) == pytest.approx(3**0.5)
    assert "gambrel-shallow-1" not in fields or fields.get("gambrel-break-1", "0") in (
        "0",
        "0.0",
        "",
    )


def test_selecting_consecutive_edges_sets_one_plane() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.clickPlan(5, 0);
editor.clickPlan(10, 3);
editor.setOnePlane();
"""
    )
    fields = result["fields"]
    assert result["selectedEdges"] == [0, 1]
    assert fields["wrap-0"] == "0,1"


def test_drawing_a_dormer_rectangle_writes_millimetre_fields() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.startDormer();
editor.clickPlan(4, 0.5);
editor.clickPlan(6, 0.5);
editor.clickPlan(6, 2);
editor.clickPlan(4, 2);
editor.closeRing();
"""
    )
    fields = result["fields"]
    assert fields["dormer-0-cell"] == "0"
    assert float(fields["dormer-0-x-0"]) == 4.0
    assert float(fields["dormer-0-y-0"]) == 0.5
    assert float(fields["dormer-0-x-1"]) == 6.0
    assert float(fields["dormer-0-y-1"]) == 0.5
    assert float(fields["dormer-0-x-2"]) == 6.0
    assert float(fields["dormer-0-y-2"]) == 2.0
    assert float(fields["dormer-0-x-3"]) == 4.0
    assert float(fields["dormer-0-y-3"]) == 2.0
    assert fields["dormer-0-pitch-0"] == "45"
    assert fields["dormer-0-pitch-3"] == "45"


def test_posted_drawn_dormer_matches_project() -> None:
    ring = [(4.0, 0.5), (6.0, 0.5), (6.0, 2.0), (4.0, 2.0)]
    host = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (0.0, 6.0),
    ]
    built = project([Cell(host, 45.0)], [Dormer(0, ring, 45.0)])
    assert isinstance(built, Project)
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.startDormer();
editor.clickPlan(4, 0.5);
editor.clickPlan(6, 0.5);
editor.clickPlan(6, 2);
editor.clickPlan(4, 2);
editor.closeRing();
"""
    )
    data = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        **result["fields"],
    }
    page = create_app().test_client().post("/", data=data).get_data(as_text=True)
    assert "terrain: False" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "3D solid" in page


def test_editing_a_table_vertex_moves_it_on_the_plan() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.moveVertex(0, 2, 5, 4);
"""
    )
    fields = result["fields"]
    assert _xy(fields, "") == [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 6.0)]
    assert result["rings"][0][2] == [5, 4]


def test_a_cell_can_be_deleted() -> None:
    result = _run_editor(
        """
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.addCell();
editor.clickPlan(5, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(5, 6);
editor.closeRing();
editor.deleteCell();
"""
    )
    fields = result["fields"]
    assert _xy(fields, "") == [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
    assert "cell-1-outer-x-0" not in fields
    assert len(result["rings"]) == 1


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
editor.clickPlan(0, 0);
editor.clickPlan(5, 0);
editor.clickPlan(5, 6);
editor.clickPlan(0, 6);
editor.closeRing();
editor.clickPlan(5, 3);
editor.setGable(true);
editor.clickPlan(0, 3);
editor.setGable(true);
editor.setEaveHeight(5);
editor.addCell();
editor.clickPlan(5, 0);
editor.clickPlan(10, 0);
editor.clickPlan(10, 6);
editor.clickPlan(5, 6);
editor.closeRing();
editor.clickPlan(10, 3);
editor.setGable(true);
editor.clickPlan(5, 3);
editor.setGable(true);
editor.setEaveHeight(7);
"""
    )
    data = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        **result["fields"],
    }
    page = create_app().test_client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
