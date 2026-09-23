"""HTTP round-trip for the roof demo.

The seam is GET/POST of the form page, through Flask's test client.
Assert what a visitor reads: example catalog, describe lines, which
drawing branch rendered, and the worked-example numbers. Not CSS.
"""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient
from web.app import create_app
from web.examples import (
    BOWTIE,
    COURTYARD_HOLE,
    DORMER_RING,
    GABLE_DORMER,
    GABLES,
    GAMBREL_BREAK,
    GARAGE,
    HOUSE,
    L_SHAPE,
    NEIGHBOUR,
    RECTANGLE,
    SQUARE,
    load_examples,
)

from krovlab import Cell, Dormer, Failure, Project, Roof, project, roof

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
COLLINEAR = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
PENTAGON = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (4.0, 8.0), (0.0, 6.0)]


def _client() -> FlaskClient:
    return create_app().test_client()


def _rect_post(**overrides: str) -> dict[str, str]:
    data: dict[str, str] = {
        "example": "hip-rectangle",
        "set_pitch": "45",
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
    data.update(overrides)
    return data


def _ring_fields(
    ring: list[tuple[float, float]],
    *,
    prefix: str = "",
    pitch: str = "45",
    kind: str = "hip",
) -> dict[str, str]:
    data: dict[str, str] = {}
    for i, (x, y) in enumerate(ring):
        data[f"{prefix}outer-x-{i}"] = str(x)
        data[f"{prefix}outer-y-{i}"] = str(y)
        data[f"{prefix}type-{i}"] = kind
        data[f"{prefix}pitch-{i}"] = pitch
    return data


def test_get_returns_the_default_rectangle_already_run() -> None:
    built = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)

    response = _client().get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.000 m" in page
    assert "ridge: 4.000 m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "m²" in page
    by_kind: dict[str, float] = {}
    for arc in built.arcs:
        by_kind[arc.kind] = by_kind.get(arc.kind, 0.0) + arc.length
    assert f"eave: {by_kind['eave']:.3f} m" in page
    assert f"hip: {by_kind['hip']:.3f} m" in page
    assert "metres" in page.lower()
    assert "degrees" in page.lower()
    assert "Roof plan" in page
    assert "3D solid" in page
    assert "Building (edit)" in page


def test_get_shows_a_title_description_and_github_link() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "<h1>krovlab</h1>" in page
    assert "https://github.com/mjordanic/krovlab" in page
    assert "Hip rectangle 10x6" in page
    assert "every wall a hip" in page
    assert "Update roof" in page
    assert "Need help?" in page
    assert "detached cell" in page
    assert "courtyard" in page
    assert "README on GitHub" in page


def test_get_hides_coordinate_tables_until_edit_is_checked() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="edit_coordinates"' in page
    assert "Edit coordinates" in page
    assert 'id="vertex-editor" hidden' in page
    assert 'name="outer-x-0"' in page


def test_plotly_js_is_loaded_from_a_cdn_not_inlined() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "cdn.plot.ly" in page
    assert "plotly.js v" not in page.lower()


def test_dropdown_lists_curated_examples_not_corpus_stems() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="example"' in page
    assert '<optgroup label="Walls">' in page
    assert '<optgroup label="Plan">' in page
    assert '<optgroup label="Several cells">' in page
    for slug, example in load_examples().items():
        assert f'value="{slug}"' in page
        assert example.label in page
    assert "rectangle-10x6" not in page
    assert "concatenated-gables" not in page
    assert "U-shape" not in page
    assert "u-shape" not in page


def test_get_example_query_runs_that_example() -> None:
    built = roof(RECTANGLE, GABLES)
    assert isinstance(built, Roof)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")

    response = _client().get("/?example=gable-ends")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'value="gable-ends" selected' in page
    assert "terrain: True" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert "Roof plan" in page
    assert "3D solid" in page
    assert "short walls are gables" in page


def test_unknown_example_falls_back_to_the_hip_rectangle() -> None:
    page = _client().get("/?example=not-a-roof").get_data(as_text=True)
    assert "ridge height: 3.000 m" in page
    assert 'value="hip-rectangle" selected' in page


@pytest.mark.parametrize("slug", list(load_examples()))
def test_every_example_returns_200(slug: str) -> None:
    response = _client().get(f"/?example={slug}")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Failure" in page or "terrain:" in page


def test_get_self_intersecting_is_a_failure_without_a_roof() -> None:
    refused = roof(BOWTIE, 45.0)
    assert isinstance(refused, Failure)

    page = _client().get("/?example=self-intersecting").get_data(as_text=True)
    assert refused.kind == "self_intersection"
    assert "self_intersection" in page
    assert refused.reason in page
    assert "Failure" in page
    assert "Input footprint" in page
    assert "3D solid" not in page
    assert "<h2>Roof plan</h2>" not in page


def test_get_courtyard_is_a_terrain_with_plan_and_3d() -> None:
    built = roof(SQUARE, 45.0, holes=[COURTYARD_HOLE])
    assert isinstance(built, Roof)
    page = _client().get("/?example=courtyard").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
    assert "3D solid" in page
    assert 'name="use_hole" checked' in page
    assert 'name="hole-x-0" value="3.0"' in page


def test_get_knee_shows_knee_type_and_matches_project() -> None:
    built = project([Cell(RECTANGLE, 45.0, knee_height=[0.0, 3.0, 0.0, 0.0])])
    assert isinstance(built, Project)
    page = _client().get("/?example=knee").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'value="knee" checked' in page
    assert 'name="knee-1"' in page
    assert "gablet, not a gable" in page


def test_get_gambrel_matches_project() -> None:
    built = project(
        [
            Cell(
                RECTANGLE,
                45.0,
                gambrel=[
                    (60.0, 30.0, GAMBREL_BREAK),
                    None,
                    (60.0, 30.0, GAMBREL_BREAK),
                    None,
                ],
            )
        ]
    )
    assert isinstance(built, Project)
    page = _client().get("/?example=gambrel").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"total sloped area: {built.total_sloped_area:.3f} m²" in page
    assert 'value="gambrel" checked' in page
    assert 'name="gambrel-shallow-0"' in page
    assert "3D solid" in page


def test_get_house_and_garage_is_two_detached_cells() -> None:
    built = project(
        [
            Cell(HOUSE, 45.0, eave_height=5.0),
            Cell(GARAGE, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    page = _client().get("/?example=house-and-garage").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'name="cell-1-outer-x-0"' in page
    assert 'name="use_eave_height" checked' in page
    assert 'name="cell-1-use_eave_height" checked' in page
    assert 'name="eave_height" value="5' in page
    assert 'name="cell-1-eave_height" value="7' in page
    assert "Cell 1" in page
    assert "Cell 2" in page


def test_get_party_wall_gables_matches_project() -> None:
    built = project(
        [
            Cell(HOUSE, GABLES, eave_height=5.0),
            Cell(NEIGHBOUR, GABLES, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    assert built.ridge_height == pytest.approx(10.0)
    page = _client().get("/?example=party-wall-gables").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'value="gable" checked' in page
    assert 'name="cell-1-outer-x-0"' in page
    assert "Roof plan" in page
    assert "3D solid" in page


def test_get_dormer_matches_project_and_still_draws_3d() -> None:
    built = project([Cell(RECTANGLE, 45.0)], [Dormer(0, DORMER_RING, GABLE_DORMER)])
    assert isinstance(built, Project)
    page = _client().get("/?example=dormer").get_data(as_text=True)
    assert "terrain: False" in page
    for reason in built.validity.reasons:
        assert reason in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"{built.total_sloped_area:.3f}" in page
    assert "3D solid" in page
    assert "Roof plan" in page
    assert 'name="dormer-0-x-0"' in page


def test_get_overhang_reports_the_enlarged_roof() -> None:
    built = roof(RECTANGLE, 45.0, overhang=0.5)
    assert isinstance(built, Roof)
    page = _client().get("/?example=eaves-overhang").get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'name="use_overhang" checked' in page
    assert 'name="overhang" value="0.5"' in page


def test_get_l_shape_and_shed_and_mixed_run() -> None:
    l_built = roof(L_SHAPE, 45.0)
    shed = roof(RECTANGLE, [45.0, 90.0, 90.0, 90.0])
    mixed = roof(SQUARE, [60.0, 45.0, 60.0, 45.0])
    assert isinstance(l_built, Roof)
    assert isinstance(shed, Roof)
    assert isinstance(mixed, Roof)
    l_page = _client().get("/?example=l-shape").get_data(as_text=True)
    assert f"ridge height: {l_built.ridge_height:.3f} m" in l_page
    shed_page = _client().get("/?example=shed").get_data(as_text=True)
    assert f"ridge height: {shed.ridge_height:.3f} m" in shed_page
    mixed_page = _client().get("/?example=mixed-pitches").get_data(as_text=True)
    assert f"ridge height: {mixed.ridge_height:.3f} m" in mixed_page


def test_get_shows_exclusive_wall_types_and_hints() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="type-0"' in page
    assert 'value="hip"' in page
    assert 'value="gable"' in page
    assert 'value="knee"' in page
    assert 'value="gambrel"' in page
    assert "Hips meet at the corners" in page
    assert "Set pitch on all sloping walls" in page
    assert 'name="set_pitch"' in page
    assert "Wall 1" in page
    assert "Close ring" not in page
    assert "Add detached cell" in page
    assert "Add cell on selected wall" in page
    assert "Add vertex on selected wall" in page
    assert "Delete cell" in page


def test_unusual_options_are_unchecked_on_the_hip_example() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="use_overhang"' in page
    assert 'name="use_eave_height"' in page
    assert 'name="use_hole"' in page
    assert 'name="use_overhang" checked' not in page
    assert 'name="use_eave_height" checked' not in page
    assert 'name="use_hole" checked' not in page
    assert "Overhang" in page
    assert "Eave height" in page
    assert "Courtyard" in page


def test_core_does_not_import_flask_or_the_web_app() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "krovlab"
    banned = ("flask", "web", "ezdxf", "pygltflib")
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
    assert "### Help agent" in text
    assert "Need help?" in text


def test_posting_edited_vertices_builds_that_footprint() -> None:
    short = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    built = roof(short, 45.0)
    assert isinstance(built, Roof)
    page = (
        _client()
        .post("/", data=_rect_post(**{"outer-y-2": "4", "outer-y-3": "4"}))
        .get_data(as_text=True)
    )
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert 'name="outer-y-2" value="4.0"' in page
    assert "3D solid" in page
    assert 'data-ring="0.0,0.0 10.0,0.0 10.0,4.0 0.0,4.0"' in page


def test_posting_a_gable_writes_90_and_shows_a_verge() -> None:
    built = roof(RECTANGLE, [45.0, 90.0, 45.0, 45.0])
    assert isinstance(built, Roof)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")
    page = (
        _client()
        .post("/", data=_rect_post(**{"type-1": "gable"}))
        .get_data(as_text=True)
    )
    assert "terrain: True" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert 'value="gable" checked' in page


def test_posting_set_pitch_on_sloping_walls() -> None:
    built = roof(RECTANGLE, "4:12")
    assert isinstance(built, Roof)
    page = (
        _client()
        .post(
            "/",
            data=_rect_post(
                set_pitch="4:12",
                **{
                    "pitch-0": "4:12",
                    "pitch-1": "4:12",
                    "pitch-2": "4:12",
                    "pitch-3": "4:12",
                },
            ),
        )
        .get_data(as_text=True)
    )
    assert "ridge height: 1.000 m" in page
    assert f"{built.total_sloped_area:.3f}" in page


def test_posting_overhang_requires_the_checkbox() -> None:
    built = roof(RECTANGLE, 45.0, overhang=0.5)
    assert isinstance(built, Roof)
    ignored = (
        _client().post("/", data=_rect_post(overhang="0.5")).get_data(as_text=True)
    )
    assert "ridge height: 3.000 m" in ignored
    page = (
        _client()
        .post("/", data=_rect_post(use_overhang="on", overhang="0.5"))
        .get_data(as_text=True)
    )
    assert "ridge height: 3.500 m" in page
    assert f"{built.total_sloped_area:.3f}" in page


def test_posting_eave_height_requires_the_checkbox() -> None:
    ignored = (
        _client().post("/", data=_rect_post(eave_height="7")).get_data(as_text=True)
    )
    assert "ridge height: 3.000 m" in ignored
    page = (
        _client()
        .post("/", data=_rect_post(use_eave_height="on", eave_height="7"))
        .get_data(as_text=True)
    )
    assert "ridge height: 10.000 m" in page


def test_posting_knee_type_matches_project() -> None:
    built = project([Cell(RECTANGLE, 45.0, knee_height=[0.0, 3.0, 0.0, 0.0])])
    assert isinstance(built, Project)
    verge_m = sum(arc.length for arc in built.arcs if arc.kind == "verge")
    page = (
        _client()
        .post("/", data=_rect_post(**{"type-1": "knee", "knee-1": "3"}))
        .get_data(as_text=True)
    )
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert f"verge: {verge_m:.3f} m" in page
    assert 'value="knee" checked' in page


def test_posting_gambrel_type_matches_project() -> None:
    built = project(
        [
            Cell(
                RECTANGLE,
                [60.0, 45.0, 60.0, 45.0],
                gambrel=[
                    (60.0, 30.0, GAMBREL_BREAK),
                    None,
                    (60.0, 30.0, GAMBREL_BREAK),
                    None,
                ],
            )
        ]
    )
    assert isinstance(built, Project)
    page = (
        _client()
        .post(
            "/",
            data=_rect_post(
                **{
                    "type-0": "gambrel",
                    "pitch-0": "60",
                    "gambrel-shallow-0": "30",
                    "gambrel-break-0": str(GAMBREL_BREAK),
                    "type-2": "gambrel",
                    "pitch-2": "60",
                    "gambrel-shallow-2": "30",
                    "gambrel-break-2": str(GAMBREL_BREAK),
                }
            ),
        )
        .get_data(as_text=True)
    )
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "edge 0: pitch 60" in page
    assert "edge 0: pitch 30" in page


def test_posting_a_hole_requires_the_checkbox() -> None:
    built = roof(SQUARE, 45.0, holes=[COURTYARD_HOLE])
    assert isinstance(built, Roof)
    without = roof(SQUARE, 45.0)
    assert isinstance(without, Roof)
    data = _rect_post(
        **{
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
            "type-4": "hip",
            "pitch-4": "45",
            "type-5": "hip",
            "pitch-5": "45",
            "type-6": "hip",
            "pitch-6": "45",
            "type-7": "hip",
            "pitch-7": "45",
        }
    )
    ignored = _client().post("/", data=data).get_data(as_text=True)
    assert f"ridge height: {without.ridge_height:.3f} m" in ignored
    data["use_hole"] = "on"
    page = _client().post("/", data=data).get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page


def test_posting_an_unreadable_pitch_returns_invalid_pitch_not_500() -> None:
    refused = roof(RECTANGLE, "not-a-pitch")
    assert isinstance(refused, Failure)
    assert refused.kind == "invalid_pitch"
    page = (
        _client()
        .post("/", data=_rect_post(**{"pitch-0": "not-a-pitch"}))
        .get_data(as_text=True)
    )
    assert "invalid_pitch" in page
    assert "3D solid" not in page
    assert "<h2>Roof plan</h2>" not in page


def test_posting_unreadable_coordinates_returns_a_failure_not_500() -> None:
    page = (
        _client()
        .post("/", data=_rect_post(**{"outer-x-0": "abc"}))
        .get_data(as_text=True)
    )
    assert "Failure" in page
    assert "degenerate" in page
    assert 'name="outer-x-0" value="abc"' in page
    assert "3D solid" not in page


def test_posting_unreadable_overhang_returns_a_failure_not_500() -> None:
    page = (
        _client()
        .post("/", data=_rect_post(use_overhang="on", overhang="nope"))
        .get_data(as_text=True)
    )
    assert "Failure" in page
    assert "degenerate" in page
    assert 'name="overhang" value="nope"' in page


def test_posting_a_plus_shape_shows_plan_and_validity_reasons() -> None:
    built = roof(PLUS, 45.0)
    assert isinstance(built, Roof)
    assert built.validity.is_terrain is False
    data: dict[str, str] = {"example": "hip-rectangle", "set_pitch": "45"}
    for i, (x, y) in enumerate(PLUS):
        data[f"outer-x-{i}"] = str(x)
        data[f"outer-y-{i}"] = str(y)
        data[f"type-{i}"] = "hip"
        data[f"pitch-{i}"] = "45"
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: False" in page
    for reason in built.validity.reasons:
        assert reason in page
    assert "<h2>Roof plan</h2>" in page
    assert "3D solid" not in page


def test_posting_a_collinear_extra_vertex_is_a_terrain() -> None:
    built = roof(COLLINEAR, 45.0)
    assert isinstance(built, Roof)
    data = {"example": "hip-rectangle", "set_pitch": "45"}
    data.update(_ring_fields(COLLINEAR))
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert "Roof plan" in page
    assert "3D solid" in page


def test_posting_an_extra_vertex_relabels_walls() -> None:
    built = roof(PENTAGON, 45.0)
    assert isinstance(built, Roof)
    data = {"example": "hip-rectangle", "set_pitch": "45"}
    data.update(_ring_fields(PENTAGON))
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "Wall 5" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "pitch_count" not in page


def test_posting_two_detached_cells_shows_combined_plan_and_3d() -> None:
    built = project(
        [
            Cell(HOUSE, 45.0, eave_height=5.0),
            Cell(GARAGE, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    data: dict[str, str] = {
        "example": "hip-rectangle",
        "set_pitch": "45",
        "use_eave_height": "on",
        "eave_height": "5",
        "cell-1-use_eave_height": "on",
        "cell-1-eave_height": "7",
    }
    data.update(_ring_fields(HOUSE))
    data.update(_ring_fields(GARAGE, prefix="cell-1-"))
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "<h2>Roof plan</h2>" in page
    assert "3D solid" in page
    assert 'data-cell="0"' in page
    assert 'data-cell="1"' in page
    assert 'data-ring="0.0,0.0 5.0,0.0 5.0,6.0 0.0,6.0"' in page
    assert 'data-ring="8.0,0.0 13.0,0.0 13.0,6.0 8.0,6.0"' in page


def test_posting_overlapping_cells_is_a_failure_not_500() -> None:
    overlap = [(2.0, 0.0), (7.0, 0.0), (7.0, 6.0), (2.0, 6.0)]
    data: dict[str, str] = {"example": "hip-rectangle", "set_pitch": "45"}
    data.update(_ring_fields(HOUSE))
    data.update(_ring_fields(overlap, prefix="cell-1-"))
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "Failure" in page
    assert "overlap" in page
    assert "Input footprint" in page
    assert "3D solid" not in page
    assert "<h2>Roof plan</h2>" not in page


def test_posting_a_dormer_rectangle_matches_project() -> None:
    built = project([Cell(RECTANGLE, 45.0)], [Dormer(0, DORMER_RING, GABLE_DORMER)])
    assert isinstance(built, Project)
    data = _rect_post()
    data["dormer-0-cell"] = "0"
    for i, (x, y) in enumerate(DORMER_RING):
        data[f"dormer-0-x-{i}"] = str(x)
        data[f"dormer-0-y-{i}"] = str(y)
    for i, pitch in enumerate(GABLE_DORMER):
        if pitch == 90.0:
            data[f"dormer-0-type-{i}"] = "gable"
            data[f"dormer-0-pitch-{i}"] = "90"
        else:
            data[f"dormer-0-type-{i}"] = "hip"
            data[f"dormer-0-pitch-{i}"] = str(pitch)
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: False" in page
    for reason in built.validity.reasons:
        assert reason in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "3D solid" in page
    assert 'name="dormer-0-x-0"' in page


def test_get_shows_a_plan_editor_with_the_default_rectangle() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'id="plan-editor"' in page
    assert 'data-cell="0"' in page
    assert 'data-ring="0.0,0.0 10.0,0.0 10.0,6.0 0.0,6.0"' in page
    assert "plan-editor.js" in page
    response = _client().get("/static/plan-editor.js")
    assert response.status_code == 200
    assert b"createEditor" in response.data
    assert "Close ring" not in page


def test_app_has_no_roof_json_api() -> None:
    app = create_app()
    rules = sorted(
        rule.rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"
    )
    assert "/" in rules
    assert "/api/roofs" not in rules
    response = _client().get("/api/roofs")
    assert response.status_code == 404
