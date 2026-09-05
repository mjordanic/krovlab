"""HTTP round-trip for the roof form server.

The seam is GET/POST of the form page, through Flask's test client.
Assert what the power user reads: status, describe lines, which drawing
branch rendered, and the worked-example numbers. Not CSS, not pixels.
"""

from flask.testing import FlaskClient
from web.app import create_app

from krovlab import Failure, Roof, roof

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
    page = _client().post("/", data={"fixture": "rectangle-gabled"}).get_data(
        as_text=True
    )
    assert 'value="rectangle-gabled" selected' in page
    assert "(0.0, 0.0)" in page
    assert "(10.0, 6.0)" in page
    assert "45.0, 90.0, 45.0, 45.0" in page
    assert "0.0 m" in page


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



