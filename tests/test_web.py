"""HTTP round-trip for the roof form server.

The seam is GET/POST of the form page, through Flask's test client.
Assert what the power user reads: status, describe lines, which drawing
branch rendered, and the worked-example numbers. Not CSS, not pixels.
"""

import pytest
from flask.testing import FlaskClient
from web.app import create_app

from krovlab import Cell, Failure, Project, Roof, project, roof

RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
BOWTIE = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]


def _client() -> FlaskClient:
    return create_app().test_client()


def test_get_returns_the_default_rectangle_already_run() -> None:
    built = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)

    response = _client().get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain" in page.lower()
    assert "true" in page.lower() or "yes" in page.lower()
    assert "ridge height: 3.000 m" in page
    assert "ridge: 4.000 m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "m²" in page or "m2" in page
    by_kind: dict[str, float] = {}
    for arc in built.arcs:
        by_kind[arc.kind] = by_kind.get(arc.kind, 0.0) + arc.length
    assert f"eave: {by_kind['eave']:.3f} m" in page
    assert f"hip: {by_kind['hip']:.3f} m" in page
    assert "metres" in page.lower()
    assert "degrees" in page.lower()
    assert "Plan" in page
    assert "3D" in page


def test_get_shows_a_title_description_and_github_link() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "<h1>krovlab</h1>" in page
    assert "https://github.com/mjordanic/krovlab" in page
    assert "named footprint" in page
    assert "Edit vertices" in page
    assert "one wall" in page


def test_get_hides_vertex_tables_until_edit_is_checked() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="edit_vertices"' in page
    assert 'id="vertex-editor" hidden' in page
    assert 'name="outer-x-0"' in page


def test_posting_vertices_without_edit_checked_uses_the_named_footprint() -> None:
    short = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    edited = roof(short, 45.0)
    named = roof(RECTANGLE, 45.0)
    assert isinstance(edited, Roof)
    assert isinstance(named, Roof)
    assert f"{edited.ridge_height:.3f}" != f"{named.ridge_height:.3f}"

    page = (
        _client()
        .post(
            "/",
            data={
                "fixture": "rectangle-10x6",
                "loaded_fixture": "rectangle-10x6",
                "outer-x-0": "0",
                "outer-y-0": "0",
                "outer-x-1": "10",
                "outer-y-1": "0",
                "outer-x-2": "10",
                "outer-y-2": "4",
                "outer-x-3": "0",
                "outer-y-3": "4",
                "pitch-0": "45",
                "pitch-1": "45",
                "pitch-2": "45",
                "pitch-3": "45",
                "overhang": "0",
            },
        )
        .get_data(as_text=True)
    )
    assert f"ridge height: {named.ridge_height:.3f} m" in page
    assert f"ridge height: {edited.ridge_height:.3f} m" not in page


def test_plotly_js_is_loaded_from_a_cdn_not_inlined() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "cdn.plot.ly" in page
    assert "plotly.js v" not in page.lower()


REQUIRED_PRESETS = (
    "rectangle-10x6",
    "l-shape",
    "u-shape",
    "courtyard",
    "rectangle-gabled",
    "bowtie",
    "concatenated-gables",
)


def test_dropdown_lists_the_corpus_by_name() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "<form" in page
    assert 'name="fixture"' in page
    for name in REQUIRED_PRESETS:
        assert name in page


def test_posting_the_bowtie_returns_self_intersection_without_a_roof() -> None:
    refused = roof(BOWTIE, 45.0)
    assert isinstance(refused, Failure)

    response = _client().post("/", data={"fixture": "bowtie"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert refused.kind == "self_intersection"
    assert "self_intersection" in page
    assert refused.reason in page
    assert "Failure" in page
    assert "Input footprint" in page
    assert "3D solid" not in page
    assert "<h2>Plan</h2>" not in page


def test_posting_the_courtyard_returns_a_terrain_roof_with_plan_and_3d() -> None:
    response = _client().post("/", data={"fixture": "courtyard"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert "Input footprint" not in page
    assert "(3.0, 3.0)" in page


def test_posting_the_gabled_rectangle_shows_a_verge_and_3d() -> None:
    built = roof(RECTANGLE, [45.0, 90.0, 45.0, 45.0])
    assert isinstance(built, Roof)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")

    response = _client().post("/", data={"fixture": "rectangle-gabled"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page


def test_posting_a_fixture_fills_the_form_from_the_corpus() -> None:
    page = (
        _client().post("/", data={"fixture": "rectangle-gabled"}).get_data(as_text=True)
    )
    assert 'value="rectangle-gabled" selected' in page
    assert "(0.0, 0.0)" in page
    assert "(10.0, 6.0)" in page
    assert 'name="pitch-0" value="45.0"' in page
    assert 'name="pitch-1" value="90" disabled' in page
    assert 'name="pitch-2" value="45.0"' in page
    assert 'name="pitch-3" value="45.0"' in page
    assert 'name="gable-1" checked' in page
    assert 'name="overhang" value="0.0"' in page


def test_core_does_not_import_flask_or_the_web_app() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "krovlab"
    banned = ("flask", "web")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for name in names:
                assert name not in banned, f"{path} imports {name}"


def test_readme_documents_one_local_command() -> None:
    from pathlib import Path

    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "## Web demo" in text
    assert "python -m web" in text


def test_posting_apply_to_all_builds_the_roof_at_that_pitch() -> None:
    built = roof(RECTANGLE, "4:12")
    assert isinstance(built, Roof)

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "apply_to_all": "4:12",
            "pitch-0": "4:12",
            "pitch-1": "4:12",
            "pitch-2": "4:12",
            "pitch-3": "4:12",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 1.000 m" in page
    assert "ridge: 4.000 m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert 'name="pitch-0" value="4:12"' in page
    assert 'name="pitch-1" value="4:12"' in page
    assert 'name="pitch-2" value="4:12"' in page
    assert 'name="pitch-3" value="4:12"' in page


def test_posting_a_gable_on_one_rectangle_edge_writes_90() -> None:
    built = roof(RECTANGLE, [45.0, 90.0, 45.0, 45.0])
    assert isinstance(built, Roof)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "pitch-0": "45",
            "gable-1": "on",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert 'name="pitch-1" value="90" disabled' in page
    assert 'name="gable-1" checked' in page


def test_posting_overhang_returns_the_enlarged_footprint_roof() -> None:
    built = roof(RECTANGLE, 45.0, overhang=0.5)
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is True

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0.5",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.500 m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert 'name="overhang" value="0.5"' in page


def test_posting_eave_height_seven_reports_ridge_height_ten() -> None:
    built = roof(RECTANGLE, 45.0, eave_height=7.0)
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is True
    assert built.ridge_height == 10.0

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
            "eave_height": "7",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 10.000 m" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert 'name="eave_height" value="7.0"' in page


def test_posting_a_two_edge_wrap_shows_one_face_in_describe() -> None:
    l_shape = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 6.0),
        (3.0, 6.0),
        (3.0, 10.0),
        (0.0, 10.0),
    ]
    built = roof(l_shape, 45.0, wrap=[[2, 3]])
    assert isinstance(built, Roof)
    assert len(built.faces) == 5

    response = _client().post(
        "/",
        data={
            "fixture": "l-shape",
            "loaded_fixture": "l-shape",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "pitch-4": "45",
            "pitch-5": "45",
            "wrap-0": "2,3",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "edges 2, 3: one plane" in page
    assert "3D solid" in page
    assert 'name="wrap-0" value="2,3"' in page


def test_posting_knee_height_on_an_edge_matches_project() -> None:
    built = project([Cell(RECTANGLE, 45.0, knee_height=[0.0, 3.0, 0.0, 0.0])])
    assert isinstance(built, Project)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "knee-1": "3",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert 'name="knee-1" value="3.0"' in page or 'name="knee-1" value="3"' in page


def test_get_without_eave_height_still_shows_ridge_height_three() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "ridge height: 3.000 m" in page
    assert 'name="eave_height"' in page
    assert "3D solid" in page


def test_get_shows_apply_to_all_and_a_pitch_row_per_edge() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="apply_to_all"' in page
    assert "Apply to all" in page
    assert 'name="overhang"' in page
    assert "0: (0.0, 0.0) → (10.0, 0.0)" in page
    assert "1: (10.0, 0.0) → (10.0, 6.0)" in page
    assert "2: (10.0, 6.0) → (0.0, 6.0)" in page
    assert "3: (0.0, 6.0) → (0.0, 0.0)" in page
    assert 'name="pitch-0"' in page
    assert 'name="pitch-3"' in page
    assert 'name="gable-0"' in page
    assert "Gable" in page


def test_get_shows_an_editable_outer_vertex_table() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="outer-x-0" value="0.0"' in page
    assert 'name="outer-y-0" value="0.0"' in page
    assert 'name="outer-x-1" value="10.0"' in page
    assert 'name="outer-y-1" value="0.0"' in page
    assert 'name="outer-x-2" value="10.0"' in page
    assert 'name="outer-y-2" value="6.0"' in page
    assert 'name="outer-x-3" value="0.0"' in page
    assert 'name="outer-y-3" value="6.0"' in page


def test_posting_edited_outer_vertices_builds_that_footprint() -> None:
    short = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    built = roof(short, 45.0)
    assert isinstance(built, Roof)
    default = roof(RECTANGLE, 45.0)
    assert isinstance(default, Roof)
    assert f"{built.ridge_height:.3f}" != f"{default.ridge_height:.3f}"

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "4",
            "outer-x-3": "0",
            "outer-y-3": "4",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'name="outer-y-2" value="4.0"' in page
    assert "3D solid" in page


def test_posting_a_courtyard_fixture_fills_the_hole_table() -> None:
    page = _client().post("/", data={"fixture": "courtyard"}).get_data(as_text=True)
    assert 'name="outer-x-0" value="0.0"' in page
    assert 'name="outer-x-2" value="10.0"' in page
    assert 'name="hole-x-0" value="3.0"' in page
    assert 'name="hole-y-0" value="3.0"' in page
    assert 'name="hole-x-1" value="7.0"' in page
    assert 'name="hole-y-1" value="3.0"' in page
    assert 'name="hole-x-2" value="7.0"' in page
    assert 'name="hole-y-2" value="7.0"' in page
    assert 'name="hole-x-3" value="3.0"' in page
    assert 'name="hole-y-3" value="7.0"' in page
    assert "4: (3.0, 3.0) → (7.0, 3.0)" in page


def test_posting_one_hole_with_outer_vertices_roofs_that_plan() -> None:
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    well = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]
    built = roof(square, 45.0, holes=[well])
    assert isinstance(built, Roof)
    without_hole = roof(square, 45.0)
    assert isinstance(without_hole, Roof)
    assert f"{built.ridge_height:.3f}" != f"{without_hole.ridge_height:.3f}"

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "10",
            "outer-x-3": "0",
            "outer-y-3": "10",
            "hole-x-0": "3",
            "hole-y-0": "3",
            "hole-x-1": "7",
            "hole-y-1": "3",
            "hole-x-2": "7",
            "hole-y-2": "7",
            "hole-x-3": "3",
            "hole-y-3": "7",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "pitch-4": "45",
            "pitch-5": "45",
            "pitch-6": "45",
            "pitch-7": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "3D solid" in page
    assert 'name="hole-x-0" value="3.0"' in page


PENTAGON = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (4.0, 8.0), (0.0, 6.0)]


def test_posting_an_extra_vertex_relabels_pitch_rows_from_the_new_edges() -> None:
    built = roof(PENTAGON, 45.0)
    assert isinstance(built, Roof)

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "4",
            "outer-y-3": "8",
            "outer-x-4": "0",
            "outer-y-4": "6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "pitch-4": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "0: (0.0, 0.0) → (10.0, 0.0)" in page
    assert "2: (10.0, 6.0) → (4.0, 8.0)" in page
    assert "3: (4.0, 8.0) → (0.0, 6.0)" in page
    assert "4: (0.0, 6.0) → (0.0, 0.0)" in page
    assert 'name="pitch-4"' in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "pitch_count" not in page


def test_extra_vertex_without_a_new_pitch_does_not_return_pitch_count() -> None:
    built = roof(PENTAGON, 45.0)
    assert isinstance(built, Roof)

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-gabled",
            "loaded_fixture": "rectangle-gabled",
            "edit_vertices": "on",
            "apply_to_all": "45",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "4",
            "outer-y-3": "8",
            "outer-x-4": "0",
            "outer-y-4": "6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "pitch_count" not in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'name="pitch-4" value="45"' in page


def test_posting_a_new_fixture_ignores_stale_vertex_fields() -> None:
    refused = roof(BOWTIE, 45.0)
    assert isinstance(refused, Failure)

    response = _client().post(
        "/",
        data={
            "fixture": "bowtie",
            "loaded_fixture": "rectangle-10x6",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "0",
            "outer-y-3": "6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "self_intersection" in page
    assert refused.reason in page
    assert "3D solid" not in page


def test_get_offers_add_and_remove_vertex_rows() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "Add outer vertex" in page
    assert "Remove outer vertex" in page
    assert "Add hole vertex" in page
    assert "Remove hole vertex" in page


COLLINEAR = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
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


def test_posting_an_unreadable_pitch_returns_invalid_pitch_not_500() -> None:
    refused = roof(RECTANGLE, "not-a-pitch")
    assert isinstance(refused, Failure)
    assert refused.kind == "invalid_pitch"

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "0",
            "outer-y-3": "6",
            "pitch-0": "not-a-pitch",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "invalid_pitch" in page
    assert "not-a-pitch" in page
    assert "3D solid" not in page
    assert "<h2>Plan</h2>" not in page


def test_posting_a_collinear_extra_vertex_is_a_terrain() -> None:
    built = roof(COLLINEAR, 45.0)
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is True

    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "5",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "0",
            "outer-x-3": "10",
            "outer-y-3": "6",
            "outer-x-4": "0",
            "outer-y-4": "6",
            "apply_to_all": "45",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "pitch-4": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert "Input footprint" not in page


def test_posting_a_plus_shape_shows_plan_and_validity_reasons() -> None:
    built = roof(PLUS, 45.0)
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is False
    assert built.validity.reasons

    data: dict[str, str] = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        "edit_vertices": "on",
        "apply_to_all": "45",
        "overhang": "0",
    }
    for i, (x, y) in enumerate(PLUS):
        data[f"outer-x-{i}"] = str(x)
        data[f"outer-y-{i}"] = str(y)
        data[f"pitch-{i}"] = "45"
    response = _client().post("/", data=data)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: False" in page
    for reason in built.validity.reasons:
        assert reason in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" not in page
    assert "Input footprint" not in page


def test_posting_unreadable_coordinates_returns_a_failure_not_500() -> None:
    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "abc",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "0",
            "outer-y-3": "6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "0",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Failure" in page
    assert "degenerate" in page
    assert "not an (x, y) metre pair" in page
    assert 'name="outer-x-0" value="abc"' in page
    assert "3D solid" not in page
    assert "<h2>Plan</h2>" not in page


def test_posting_unreadable_overhang_returns_a_failure_not_500() -> None:
    response = _client().post(
        "/",
        data={
            "fixture": "rectangle-10x6",
            "loaded_fixture": "rectangle-10x6",
            "edit_vertices": "on",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "0",
            "outer-y-3": "6",
            "pitch-0": "45",
            "pitch-1": "45",
            "pitch-2": "45",
            "pitch-3": "45",
            "overhang": "nope",
        },
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Failure" in page
    assert "degenerate" in page
    assert "overhang must be a finite number of metres" in page
    assert 'name="overhang" value="nope"' in page
    assert "3D solid" not in page


CELL_A = [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
CELL_B = [(8.0, 0.0), (13.0, 0.0), (13.0, 6.0), (8.0, 6.0)]


def _cell_fields(
    ring: list[tuple[float, float]],
    *,
    prefix: str = "",
    pitch: str = "45",
    overhang: str = "0",
    eave_height: str = "0",
) -> dict[str, str]:
    data: dict[str, str] = {
        f"{prefix}overhang": overhang,
        f"{prefix}eave_height": eave_height,
    }
    for i, (x, y) in enumerate(ring):
        data[f"{prefix}outer-x-{i}"] = str(x)
        data[f"{prefix}outer-y-{i}"] = str(y)
        data[f"{prefix}pitch-{i}"] = pitch
    return data


def test_posting_two_detached_cells_shows_combined_plan_and_3d() -> None:
    built = project(
        [
            Cell(CELL_A, 45.0, eave_height=5.0),
            Cell(CELL_B, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    assert built.validity.is_terrain is True

    data: dict[str, str] = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        "edit_vertices": "on",
    }
    data.update(_cell_fields(CELL_A, eave_height="5"))
    data.update(_cell_fields(CELL_B, prefix="cell-1-", eave_height="7"))
    response = _client().post("/", data=data)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert "Input footprint" not in page
    assert 'name="cell-1-outer-x-0"' in page


def test_posting_a_one_ring_preset_is_still_one_cell() -> None:
    built = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)
    page = (
        _client()
        .post(
            "/",
            data={
                "fixture": "rectangle-10x6",
                "cell-1-outer-x-0": "8",
                "cell-1-outer-y-0": "0",
                "cell-1-outer-x-1": "13",
                "cell-1-outer-y-1": "0",
                "cell-1-outer-x-2": "13",
                "cell-1-outer-y-2": "6",
                "cell-1-outer-x-3": "8",
                "cell-1-outer-y-3": "6",
                "cell-1-pitch-0": "45",
                "cell-1-eave_height": "7",
            },
        )
        .get_data(as_text=True)
    )
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "ridge height: 9.500 m" not in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page


def test_get_offers_a_second_cell_table() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "Add cell" in page
    assert "ridge height: 3.000 m" in page


def test_posting_concatenated_gables_preset() -> None:
    built = project(
        [
            Cell(CELL_A, [45.0, 90.0, 45.0, 90.0], eave_height=5.0),
            Cell(
                [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)],
                [45.0, 90.0, 45.0, 90.0],
                eave_height=7.0,
            ),
        ]
    )
    assert isinstance(built, Project)
    assert built.ridge_height == pytest.approx(10.0)
    assert built.validity.is_terrain is True

    response = _client().post("/", data={"fixture": "concatenated-gables"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'value="concatenated-gables" selected' in page
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "<h2>Plan</h2>" in page
    assert "3D solid" in page
    assert "Input footprint" not in page
    assert "(0.0, 0.0)" in page
    assert "(10.0, 6.0)" in page
    assert 'name="cell-1-outer-x-0"' in page
    assert 'name="eave_height" value="5' in page
    assert 'name="cell-1-eave_height" value="7' in page
    assert 'name="gable-1" checked' in page
    assert 'name="cell-1-gable-3" checked' in page


def test_get_shows_a_plan_editor_with_the_default_rectangle() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'id="plan-editor"' in page
    assert "Close ring" in page
    assert "Delete cell" in page
    assert 'data-cell="0"' in page
    assert 'data-ring="0.0,0.0 10.0,0.0 10.0,6.0 0.0,6.0"' in page
    assert "ridge height: 3.000 m" in page
    assert "Click" in page and "plan" in page.lower()


def test_get_serves_the_plan_editor_script() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "plan-editor.js" in page
    response = _client().get("/static/plan-editor.js")
    assert response.status_code == 200
    assert b"createEditor" in response.data


def test_app_has_no_json_api() -> None:
    app = create_app()
    rules = sorted(
        rule.rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"
    )
    assert rules == ["/"]
    response = _client().get("/api/roofs")
    assert response.status_code == 404


def test_posting_two_cells_draws_both_rings_on_the_plan_editor() -> None:
    data: dict[str, str] = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        "edit_vertices": "on",
    }
    data.update(_cell_fields(CELL_A, eave_height="5"))
    data.update(_cell_fields(CELL_B, prefix="cell-1-", eave_height="7"))
    page = _client().post("/", data=data).get_data(as_text=True)
    assert 'data-cell="0"' in page
    assert 'data-ring="0.0,0.0 5.0,0.0 5.0,6.0 0.0,6.0"' in page
    assert 'data-cell="1"' in page
    assert 'data-ring="8.0,0.0 13.0,0.0 13.0,6.0 8.0,6.0"' in page


def test_posting_edited_vertices_moves_the_plan_editor_ring() -> None:
    page = (
        _client()
        .post(
            "/",
            data={
                "fixture": "rectangle-10x6",
                "loaded_fixture": "rectangle-10x6",
                "edit_vertices": "on",
                "outer-x-0": "0",
                "outer-y-0": "0",
                "outer-x-1": "10",
                "outer-y-1": "0",
                "outer-x-2": "10",
                "outer-y-2": "4",
                "outer-x-3": "0",
                "outer-y-3": "4",
                "pitch-0": "45",
                "pitch-1": "45",
                "pitch-2": "45",
                "pitch-3": "45",
                "overhang": "0",
            },
        )
        .get_data(as_text=True)
    )
    assert 'data-ring="0.0,0.0 10.0,0.0 10.0,4.0 0.0,4.0"' in page
    assert 'data-ring="0.0,0.0 10.0,0.0 10.0,6.0 0.0,6.0"' not in page


def test_posting_the_5m_7m_pair_shows_both_rings_and_project_numbers() -> None:
    neighbour = [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)]
    built = project(
        [
            Cell(CELL_A, [45.0, 90.0, 45.0, 90.0], eave_height=5.0),
            Cell(neighbour, [45.0, 90.0, 45.0, 90.0], eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    data: dict[str, str] = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        "edit_vertices": "on",
        "gable-1": "on",
        "gable-3": "on",
        "cell-1-gable-1": "on",
        "cell-1-gable-3": "on",
    }
    data.update(_cell_fields(CELL_A, eave_height="5"))
    data.update(_cell_fields(neighbour, prefix="cell-1-", eave_height="7"))
    data["pitch-1"] = "90"
    data["pitch-3"] = "90"
    data["cell-1-pitch-1"] = "90"
    data["cell-1-pitch-3"] = "90"
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert 'data-ring="0.0,0.0 5.0,0.0 5.0,6.0 0.0,6.0"' in page
    assert 'data-ring="5.0,0.0 10.0,0.0 10.0,6.0 5.0,6.0"' in page


def test_posting_overlapping_cells_is_a_failure_not_500() -> None:
    overlap = [(2.0, 0.0), (7.0, 0.0), (7.0, 6.0), (2.0, 6.0)]
    data: dict[str, str] = {
        "fixture": "rectangle-10x6",
        "loaded_fixture": "rectangle-10x6",
        "edit_vertices": "on",
    }
    data.update(_cell_fields(CELL_A))
    data.update(_cell_fields(overlap, prefix="cell-1-"))
    response = _client().post("/", data=data)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Failure" in page
    assert "overlap" in page
    assert "Input footprint" in page
    assert "3D solid" not in page
    assert "<h2>Plan</h2>" not in page
