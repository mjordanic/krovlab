"""HTTP round-trip for DXF footprint upload.

The seam is GET/POST of the form page, through Flask's test client.
DXFs are built in memory with ezdxf. Assert the visitor-visible form,
describe block, and drawing branch — not CSS, templates, or group codes.
"""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO, StringIO
from typing import Any

import ezdxf
from flask.testing import FlaskClient
from web.app import create_app
from web.examples import (
    DORMER_RING,
    GABLE_DORMER,
    GABLES,
    GARAGE,
    HOUSE,
    RECTANGLE,
)

from krovlab import Cell, Dormer, Project, Roof, project, roof


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
        "outer-y-3": "6",
        "outer-x-3": "0",
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


def _dxf_bytes(build: Callable[[Any], None]) -> bytes:
    doc = ezdxf.new("R2010")  # type: ignore[attr-defined]
    build(doc)
    buf = StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _closed_lw(
    points: list[tuple[float, float]],
    *,
    closed: bool = True,
    insunits: int | None = None,
) -> bytes:
    def build(doc: Any) -> None:
        if insunits is not None:
            doc.header["$INSUNITS"] = insunits
        doc.modelspace().add_lwpolyline(points, close=closed)

    return _dxf_bytes(build)


def _upload(
    client: FlaskClient,
    dxf: bytes,
    form: dict[str, str],
    *,
    units: str = "mm",
    filename: str = "plan.dxf",
) -> str:
    data: dict[str, object] = {**form, "dxf_units": units, "upload_dxf": "1"}
    data["dxf"] = (BytesIO(dxf), filename)
    response = client.post("/", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_get_offers_a_dxf_control_defaulting_to_millimetres() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert 'name="dxf"' in page
    assert 'type="file"' in page
    assert 'name="dxf_units"' in page
    assert "millimetres" in page
    assert "centimetres" in page
    assert 'value="mm" selected' in page or "selected>millimetres" in page.lower()
    assert "DXF" in page
    assert "polyline" in page.lower()


def test_millimetre_polyline_fills_the_first_cell_without_rebuilding() -> None:
    posted = [(0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0)]
    shown = roof(posted, 45.0)
    assert isinstance(shown, Roof)
    rebuilt = roof(RECTANGLE, 45.0)
    assert isinstance(rebuilt, Roof)
    assert shown.ridge_height != rebuilt.ridge_height
    form = {"example": "hip-rectangle", "set_pitch": "45"}
    form.update(_ring_fields(posted))
    dxf = _closed_lw([(0, 0), (10000, 0), (10000, 6000), (0, 6000)])
    page = _upload(_client(), dxf, form)
    assert 'name="outer-x-0" value="0.0"' in page
    assert 'name="outer-y-0" value="0.0"' in page
    assert 'name="outer-x-1" value="10.0"' in page
    assert 'name="outer-y-1" value="0.0"' in page
    assert 'name="outer-x-2" value="10.0"' in page
    assert 'name="outer-y-2" value="6.0"' in page
    assert 'name="outer-x-3" value="0.0"' in page
    assert 'name="outer-y-3" value="6.0"' in page
    assert 'name="outer-x-4"' not in page
    assert page.count('value="hip" checked') >= 4
    for i in range(4):
        assert f'name="pitch-{i}" value="45"' in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page
    assert f"ridge height: {rebuilt.ridge_height:.3f} m" not in page
    assert "3D solid" in page
    assert "Roof plan" in page


def _assert_metre_rectangle(page: str, *, prefix: str = "") -> None:
    assert f'name="{prefix}outer-x-0" value="0.0"' in page
    assert f'name="{prefix}outer-y-0" value="0.0"' in page
    assert f'name="{prefix}outer-x-1" value="10.0"' in page
    assert f'name="{prefix}outer-y-1" value="0.0"' in page
    assert f'name="{prefix}outer-x-2" value="10.0"' in page
    assert f'name="{prefix}outer-y-2" value="6.0"' in page
    assert f'name="{prefix}outer-x-3" value="0.0"' in page
    assert f'name="{prefix}outer-y-3" value="6.0"' in page
    assert f'name="{prefix}outer-x-4"' not in page


def test_centimetres_metres_and_a_unitless_header_use_the_chosen_scale() -> None:
    shown = roof(RECTANGLE, 45.0)
    assert isinstance(shown, Roof)
    client = _client()
    cm = _upload(
        client,
        _closed_lw([(0, 0), (1000, 0), (1000, 600), (0, 600)]),
        _rect_post(),
        units="cm",
    )
    _assert_metre_rectangle(cm)
    metres = _upload(
        client,
        _closed_lw([(0, 0), (10, 0), (10, 6), (0, 6)]),
        _rect_post(),
        units="m",
    )
    _assert_metre_rectangle(metres)
    unitless = _upload(
        client,
        _closed_lw(
            [(0, 0), (10000, 0), (10000, 6000), (0, 6000)],
            insunits=0,
        ),
        _rect_post(),
        units="mm",
    )
    _assert_metre_rectangle(unitless)
    metres_header = _upload(
        client,
        _closed_lw(
            [(0, 0), (10000, 0), (10000, 6000), (0, 6000)],
            insunits=6,
        ),
        _rect_post(),
        units="mm",
    )
    _assert_metre_rectangle(metres_header)
    assert f"ridge height: {shown.ridge_height:.3f} m" in metres_header


def test_repeated_vertex_winding_collinear_and_z_are_kept() -> None:
    shown = roof(RECTANGLE, 45.0)
    assert isinstance(shown, Roof)
    client = _client()
    repeated = _closed_lw(
        [(0, 0), (10000, 0), (10000, 6000), (0, 6000), (0, 0)],
        closed=False,
    )
    page = _upload(client, repeated, _rect_post())
    _assert_metre_rectangle(page)

    clockwise = _closed_lw([(0, 6000), (10000, 6000), (10000, 0), (0, 0)])
    page = _upload(client, clockwise, _rect_post())
    assert 'name="outer-x-0" value="0.0"' in page
    assert 'name="outer-y-0" value="6.0"' in page
    assert 'name="outer-x-1" value="10.0"' in page
    assert 'name="outer-y-1" value="6.0"' in page
    assert 'name="outer-x-2" value="10.0"' in page
    assert 'name="outer-y-2" value="0.0"' in page
    assert 'name="outer-x-3" value="0.0"' in page
    assert 'name="outer-y-3" value="0.0"' in page

    collinear = _closed_lw([(0, 0), (5000, 0), (10000, 0), (10000, 6000), (0, 6000)])
    page = _upload(client, collinear, _rect_post())
    assert 'name="outer-x-1" value="5.0"' in page
    assert 'name="outer-y-1" value="0.0"' in page
    assert 'name="outer-x-2" value="10.0"' in page
    assert 'name="outer-x-4" value="0.0"' in page
    assert 'name="outer-x-5"' not in page

    def with_z(doc: Any) -> None:
        poly = doc.modelspace().add_polyline3d(
            [(0, 0, 80), (10000, 0, 80), (10000, 6000, 80), (0, 6000, 80)]
        )
        poly.close(True)

    page = _upload(client, _dxf_bytes(with_z), _rect_post())
    _assert_metre_rectangle(page)
    assert f"ridge height: {shown.ridge_height:.3f} m" in page


def test_inner_polylines_become_holes() -> None:
    shown = roof(RECTANGLE, 45.0)
    assert isinstance(shown, Roof)

    def one_hole(doc: Any) -> None:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        msp.add_lwpolyline(
            [(2000, 2000), (8000, 2000), (8000, 4000), (2000, 4000)],
            close=True,
        )

    page = _upload(_client(), _dxf_bytes(one_hole), _rect_post())
    _assert_metre_rectangle(page)
    assert 'name="use_hole" checked' in page
    assert 'name="hole-x-0" value="2.0"' in page
    assert 'name="hole-y-0" value="2.0"' in page
    assert 'name="hole-x-1" value="8.0"' in page
    assert 'name="hole-y-2" value="4.0"' in page
    assert page.count('value="hip" checked') >= 8
    assert f"ridge height: {shown.ridge_height:.3f} m" in page

    def two_holes(doc: Any) -> None:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        msp.add_lwpolyline(
            [(1000, 1000), (3000, 1000), (3000, 2500), (1000, 2500)],
            close=True,
        )
        msp.add_lwpolyline(
            [(7000, 1000), (9000, 1000), (9000, 2500), (7000, 2500)],
            close=True,
        )

    page = _upload(_client(), _dxf_bytes(two_holes), _rect_post())
    assert (
        'name="hole-x-0" value="1.0"' in page or 'name="hole-x-0" value="7.0"' in page
    )
    assert 'name="hole-1-x-0"' in page
    assert page.count('value="hip" checked') >= 12


def test_selected_cell_is_replaced_and_the_other_cell_stays() -> None:
    shown = project([Cell(HOUSE, GABLES), Cell(GARAGE, GABLES)])
    assert isinstance(shown, Project)
    form: dict[str, str] = {
        "example": "hip-rectangle",
        "set_pitch": "45",
        "selected_cell": "1",
    }
    form.update(_ring_fields(HOUSE))
    form.update(_ring_fields(GARAGE, prefix="cell-1-"))
    for prefix in ("", "cell-1-"):
        form[f"{prefix}type-1"] = "gable"
        form[f"{prefix}pitch-1"] = "90"
        form[f"{prefix}type-3"] = "gable"
        form[f"{prefix}pitch-3"] = "90"
    dxf = _closed_lw([(0, 0), (10000, 0), (10000, 6000), (0, 6000)])
    page = _upload(_client(), dxf, form)
    assert 'name="outer-x-1" value="5.0"' in page
    assert 'name="outer-y-2" value="6.0"' in page
    assert 'value="gable" checked' in page
    _assert_metre_rectangle(page, prefix="cell-1-")
    assert 'name="cell-1-pitch-0" value="45"' in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page

    without_selection = {k: v for k, v in form.items() if k != "selected_cell"}
    first = _upload(_client(), dxf, without_selection)
    _assert_metre_rectangle(first)
    assert 'name="cell-1-outer-x-0" value="8.0"' in first


def test_overhang_eave_height_and_dormers_stay() -> None:
    shown = project(
        [Cell(RECTANGLE, [45.0, 90.0, 45.0, 45.0], overhang=0.5, eave_height=7.0)],
        [Dormer(0, DORMER_RING, GABLE_DORMER)],
    )
    assert isinstance(shown, Project)
    form = _rect_post(
        use_overhang="on",
        overhang="0.5",
        use_eave_height="on",
        eave_height="7",
        **{"type-1": "gable"},
    )
    form["dormer-0-cell"] = "0"
    for i, (x, y) in enumerate(DORMER_RING):
        form[f"dormer-0-x-{i}"] = str(x)
        form[f"dormer-0-y-{i}"] = str(y)
    for i, pitch in enumerate(GABLE_DORMER):
        if pitch == 90.0:
            form[f"dormer-0-type-{i}"] = "gable"
            form[f"dormer-0-pitch-{i}"] = "90"
        else:
            form[f"dormer-0-type-{i}"] = "hip"
            form[f"dormer-0-pitch-{i}"] = str(pitch)
    dxf = _closed_lw([(0, 0), (10000, 0), (10000, 6000), (0, 6000)])
    page = _upload(_client(), dxf, form)
    _assert_metre_rectangle(page)
    assert 'name="use_overhang" checked' in page
    assert 'name="overhang" value="0.5"' in page
    assert 'name="use_eave_height" checked' in page
    assert 'name="eave_height" value="7"' in page
    assert 'name="dormer-0-x-0"' in page
    assert 'name="dormer-0-y-0" value="0.5"' in page
    assert page.count('value="hip" checked') >= 4
    assert 'name="pitch-1" value="45"' in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page
    assert "3D solid" in page


def test_arcs_are_ignored_and_a_bulged_polyline_is_skipped() -> None:
    shown = roof(RECTANGLE, 45.0)
    assert isinstance(shown, Roof)

    def with_arc(doc: Any) -> None:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        msp.add_arc((20000, 0), 1000, 0, 90)

    page = _upload(_client(), _dxf_bytes(with_arc), _rect_post())
    _assert_metre_rectangle(page)

    def only_bulge(doc: Any) -> None:
        doc.modelspace().add_lwpolyline(
            [(0, 0, 0, 0, 0.5), (10000, 0), (10000, 6000), (0, 6000)],
            close=True,
            format="xyseb",
        )

    page = _upload(_client(), _dxf_bytes(only_bulge), _rect_post())
    assert "straight" in page.lower() or "polyline" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page
    assert 'name="outer-x-1" value="20.0"' not in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page


def test_refusals_leave_the_posted_fields_and_show_a_message() -> None:
    shown = roof(RECTANGLE, 45.0)
    assert isinstance(shown, Roof)
    form = _rect_post()
    client = _client()

    def two_outer(doc: Any) -> None:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        msp.add_lwpolyline(
            [(20000, 0), (30000, 0), (30000, 6000), (20000, 6000)],
            close=True,
        )

    page = _upload(client, _dxf_bytes(two_outer), form)
    assert "outermost" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page
    assert 'name="outer-x-0" value="20.0"' not in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page

    def bowtie(doc: Any) -> None:
        doc.modelspace().add_lwpolyline(
            [(0, 0), (10000, 10000), (10000, 0), (0, 10000)],
            close=True,
        )

    page = _upload(client, _dxf_bytes(bowtie), form)
    assert "intersect" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page
    assert "terrain: True" in _describe_block(page)
    assert "self_intersection" not in _describe_block(page)
    assert "outermost" not in page.lower()

    def inner_bowtie(doc: Any) -> None:
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        msp.add_lwpolyline(
            [(2000, 1000), (8000, 5000), (8000, 1000), (2000, 5000)],
            close=True,
        )

    page = _upload(client, _dxf_bytes(inner_bowtie), form)
    assert "intersect" in page.lower()
    assert "outermost" not in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page

    page = _upload(client, b"this is not a drawing", form, filename="notes.txt")
    assert "not a DXF" in page or "not a dxf" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page

    page = _upload(client, b"x" * (2 * 1024 * 1024 + 1), form, filename="huge.dxf")
    assert "2 MB" in page or "2 mb" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page

    def insert_only(doc: Any) -> None:
        block = doc.blocks.new("OUTLINE")
        block.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True)
        doc.modelspace().add_blockref("OUTLINE", (0, 0))

    page = _upload(client, _dxf_bytes(insert_only), form)
    assert "explode" in page.lower()
    assert 'name="outer-x-1" value="10.0"' in page
    assert f"ridge height: {shown.ridge_height:.3f} m" in page


def _describe_block(page: str) -> str:
    start = page.find("<pre>")
    end = page.find("</pre>")
    return page[start:end] if start != -1 and end != -1 else ""
