"""Form seam for the experimental method choice.

GET/POST of the page: which method is selected, which copy the visitor
reads, and which entry point ran. Not CSS.
"""

from __future__ import annotations

import math
import re
from io import BytesIO, StringIO

import ezdxf
import pytest
from flask.testing import FlaskClient
from web.app import create_app
from web.examples import L_SHAPE, RECTANGLE

from krovlab import Roof, roof
from krovlab.experimental import Placement, roof_from_face_graph

MIXED = [[0], [1], [2, 3], [4], [5]]


def _client() -> FlaskClient:
    return create_app().test_client()


def _l_post(**overrides: str) -> dict[str, str]:
    data: dict[str, str] = {
        "example": "l-shape",
        "set_pitch": "45",
        "method": "skeleton",
    }
    for i, (x, y) in enumerate(L_SHAPE):
        data[f"outer-x-{i}"] = str(x)
        data[f"outer-y-{i}"] = str(y)
        data[f"type-{i}"] = "hip"
        data[f"pitch-{i}"] = "45"
    data.update(overrides)
    return data


def _mixed_fields() -> dict[str, str]:
    return {
        "face-0": "0",
        "face-1": "1",
        "face-2": "2,3",
        "face-3": "4",
        "face-4": "5",
    }


def test_opening_the_page_has_the_skeleton_selected_above_the_catalog() -> None:
    page = _client().get("/").get_data(as_text=True)
    method_at = page.find('name="method"')
    catalog_at = page.find('name="example"')
    assert method_at != -1
    assert catalog_at != -1
    assert method_at < catalog_at
    assert "Standard skeleton" in page
    assert "Experimental graph network" in page
    assert 'value="skeleton"' in page
    assert "checked" in page[method_at : method_at + 200]
    assert 'value="skeleton"' in page and "checked" in page


def test_page_does_not_ask_for_a_face_graph() -> None:
    home = _client().get("/").get_data(as_text=True)
    catalog = _client().get("/?example=l-shape").get_data(as_text=True)
    experimental = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    for page in (home, catalog, experimental):
        assert 'name="face-0"' not in page


def test_experimental_copy_names_the_network_and_when_to_prefer_it() -> None:
    page = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    text = page.lower()
    assert "a network chooses" in text
    assert "planarity" in text
    assert "pitch is not an input" in text
    assert "face over several walls" in text
    assert "ridge layout" in text
    assert "keep the skeleton" in text
    assert "gable" in text
    assert "knee" in text
    assert "gambrel" in text
    assert "not part of this method" in text


def test_experimental_post_without_a_face_graph_roofs_from_the_checkpoint() -> None:
    built = roof_from_face_graph(L_SHAPE)
    assert isinstance(built, Roof)
    page = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert f"terrain: {built.validity.is_terrain}" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
    if built.validity.is_terrain:
        assert "3D solid" in page
    assert "no_face_graph" not in page


def test_skeleton_post_of_the_l_still_has_one_face_per_wall() -> None:
    built = roof(L_SHAPE, 45.0)
    assert isinstance(built, Roof)
    page = _client().post("/", data=_l_post(method="skeleton")).get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    for face in built.faces:
        assert f"edge {face.edge_index}:" in page


def test_switching_back_to_the_skeleton_restores_the_skeleton_roof() -> None:
    experimental = roof_from_face_graph(L_SHAPE)
    skeleton = roof(L_SHAPE, 45.0)
    assert isinstance(experimental, Roof)
    assert isinstance(skeleton, Roof)
    first = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert f"ridge height: {experimental.ridge_height:.3f} m" in first
    second = _client().post("/", data=_l_post(method="skeleton")).get_data(as_text=True)
    assert f"ridge height: {skeleton.ridge_height:.3f} m" in second


def test_supplied_face_graph_still_roofs_without_the_checkpoint() -> None:
    built = roof_from_face_graph(L_SHAPE, MIXED, checkpoint=None)
    assert isinstance(built, Roof)
    page = (
        _client()
        .post("/", data=_l_post(method="experimental", **_mixed_fields()))
        .get_data(as_text=True)
    )
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
    assert "3D solid" in page


def test_experimental_post_does_not_use_pitch() -> None:
    built = roof_from_face_graph(L_SHAPE)
    assert isinstance(built, Roof)
    low_data = _l_post(method="experimental", set_pitch="10")
    high_data = _l_post(method="experimental", set_pitch="80")
    for i in range(6):
        low_data[f"pitch-{i}"] = "10"
        high_data[f"pitch-{i}"] = "80"
    low = _client().post("/", data=low_data).get_data(as_text=True)
    high = _client().post("/", data=high_data).get_data(as_text=True)
    expected = f"ridge height: {built.ridge_height:.3f} m"
    assert expected in low
    assert expected in high


def test_experimental_page_sets_roof_height_in_metres() -> None:
    experimental = _client().get("/?method=experimental").get_data(as_text=True)
    skeleton = _client().get("/").get_data(as_text=True)
    assert 'name="roof_height"' in experimental
    assert 'value="3"' in experimental or 'value="3.0"' in experimental
    assert "Roof height" in experimental
    assert 'name="roof_height"' not in skeleton
    posted = _client().post(
        "/",
        data={
            "example": "hip-rectangle",
            "method": "experimental",
            "roof_height": "2",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "0",
            "outer-y-3": "6",
        },
    ).get_data(as_text=True)
    assert "ridge height: 2.000 m" in posted


def test_experimental_dropdown_lists_footprints_the_method_can_roof() -> None:
    page = _client().get("/?method=experimental").get_data(as_text=True)
    assert 'value="experimental" checked' in page or (
        'value="experimental"' in page and "checked" in page
    )
    for slug in (
        "hip-rectangle",
        "l-shape",
        "l-one-face",
        "eaves-overhang",
        "eave-height",
        "self-intersecting",
    ):
        assert f'value="{slug}"' in page
    for slug in (
        "gable-ends",
        "shed",
        "mixed-pitches",
        "knee",
        "gambrel",
        "courtyard",
        "house-and-garage",
        "party-wall-gables",
        "dormer",
    ):
        assert f'<option value="{slug}"' not in page
    assert "Load a catalog example (hip, gable" not in page
    one_face = _client().get("/?method=experimental&example=l-one-face").get_data(
        as_text=True
    )
    assert "two inner walls" in one_face
    assert one_face.count("edge ") == 5
    refused = _client().get(
        "/?method=experimental&example=self-intersecting"
    ).get_data(as_text=True)
    assert "kind: self_intersection" in refused


def test_catalog_example_roofs_under_either_method() -> None:
    skeleton = roof(RECTANGLE, 45.0)
    experimental = roof_from_face_graph(RECTANGLE)
    assert isinstance(skeleton, Roof)
    assert isinstance(experimental, Roof)
    data = {
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
    skeleton_page = (
        _client().post("/", data={**data, "method": "skeleton"}).get_data(as_text=True)
    )
    experimental_page = (
        _client()
        .post("/", data={**data, "method": "experimental"})
        .get_data(as_text=True)
    )
    assert "ridge height: 3.000 m" in skeleton_page
    assert "Roof plan" in skeleton_page
    assert "3D solid" in skeleton_page
    assert f"ridge height: {experimental.ridge_height:.3f} m" in experimental_page
    assert "Roof plan" in experimental_page
    assert "3D solid" in experimental_page
    assert "no_face_graph" not in experimental_page


def test_skeleton_post_of_the_rectangle_still_matches_today() -> None:
    built = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)
    data = {
        "example": "hip-rectangle",
        "set_pitch": "45",
        "method": "skeleton",
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
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.000 m" in page
    assert "ridge: 4.000 m" in page
    assert "Roof plan" in page
    assert "3D solid" in page
    assert f"{built.total_sloped_area:.3f}" in page


def _rect_post(**overrides: str) -> dict[str, str]:
    data = {
        "example": "hip-rectangle",
        "set_pitch": "45",
        "method": "experimental",
        "roof_height": "3",
        "outer-x-0": "0",
        "outer-y-0": "0",
        "outer-x-1": "10",
        "outer-y-1": "0",
        "outer-x-2": "10",
        "outer-y-2": "6",
        "outer-x-3": "0",
        "outer-y-3": "6",
    }
    data.update(overrides)
    return data


def _value(page: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]*)"', page)
    assert match is not None, name
    return match.group(1)


def test_experimental_explanation_says_the_visitor_can_move_the_apex() -> None:
    page = _client().get("/?method=experimental").get_data(as_text=True)
    assert "move the apex" in page.lower()
    assert 'name="offset_x" value="0"' in page
    assert 'name="offset_y" value="0"' in page
    assert "Place at the center" in page
    assert "requestSubmit" in page
    assert 'window.location = "/?method=' not in page


def test_typed_offset_moves_the_apex_and_update_keeps_it() -> None:
    first = _client().post("/", data=_rect_post(offset_x="1", offset_y="0")).get_data(
        as_text=True
    )
    assert _value(first, "offset_x") == "1"
    assert _value(first, "offset_y") == "0"
    short = math.degrees(math.atan(3.0 / 4.0))
    assert f"edge 1: pitch {short:g}°" in first
    assert "ridge height: 3.000 m" in first
    second = _client().post(
        "/", data=_rect_post(offset_x="1", offset_y="0", roof_height="4")
    ).get_data(as_text=True)
    assert _value(second, "offset_x") == "1"
    assert "ridge height: 4.000 m" in second


def test_place_at_center_move_and_toward_wall_2() -> None:
    centered = _client().post(
        "/",
        data=_rect_post(offset_x="1", offset_y="0", place_at_center="1"),
    ).get_data(as_text=True)
    assert _value(centered, "offset_x") == "0"
    assert _value(centered, "offset_y") == "0"
    assert "edge 0: pitch 45°" in centered
    moved = _client().post(
        "/",
        data=_rect_post(
            offset_x="1",
            offset_y="0",
            move_x="0.5",
            move_y="-1",
            move_apex="1",
        ),
    ).get_data(as_text=True)
    assert _value(moved, "offset_x") == "1.5"
    assert _value(moved, "offset_y") == "-1"
    toward = _client().post(
        "/",
        data=_rect_post(
            offset_x="0",
            offset_y="0",
            toward_wall="2",
            step_toward_wall="1",
        ),
    ).get_data(as_text=True)
    assert _value(toward, "offset_x") == "1"
    assert _value(toward, "offset_y") == "0"
    short = math.degrees(math.atan(3.0 / 4.0))
    assert f"edge 1: pitch {short:g}°" in toward


def test_an_offset_past_the_wall_is_shown_pulled_back() -> None:
    page = _client().post("/", data=_rect_post(offset_x="10", offset_y="0")).get_data(
        as_text=True
    )
    used_x = float(_value(page, "offset_x"))
    used_y = float(_value(page, "offset_y"))
    assert used_x < 5.0
    assert used_x == pytest.approx(5.0, abs=1e-2)
    assert used_y == 0.0
    again = _client().post(
        "/",
        data=_rect_post(
            offset_x=_value(page, "offset_x"),
            offset_y=_value(page, "offset_y"),
        ),
    ).get_data(as_text=True)
    assert _value(again, "offset_x") == _value(page, "offset_x")
    assert _value(again, "offset_y") == _value(page, "offset_y")


def test_corner_edit_and_overhang_keep_the_offset_from_the_new_middle() -> None:
    edited = _rect_post(
        offset_x="1",
        offset_y="0",
        **{"outer-y-2": "8", "outer-y-3": "8"},
    )
    page = _client().post("/", data=edited).get_data(as_text=True)
    assert _value(page, "offset_x") == "1"
    assert _value(page, "offset_y") == "0"
    built = roof_from_face_graph(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)],
        roof_height=3.0,
        placement=Placement(dx=1.0, dy=0.0),
    )
    assert isinstance(built, Roof)
    for face in built.faces:
        assert f"edge {face.edge_index}: pitch {face.pitch:g}°" in page
    overhang = _client().post(
        "/",
        data=_rect_post(
            offset_x="1",
            offset_y="0",
            use_overhang="on",
            overhang="1",
        ),
    ).get_data(as_text=True)
    assert _value(overhang, "offset_x") == "1"
    eave = _client().post(
        "/",
        data=_rect_post(
            offset_x="1",
            offset_y="0",
            use_eave_height="on",
            eave_height="2",
        ),
    ).get_data(as_text=True)
    assert _value(eave, "offset_x") == "1"
    assert "ridge height: 5.000 m" in eave


def test_another_example_and_the_skeleton_switch_keep_or_reset_the_offset() -> None:
    fresh = _client().get("/?method=experimental&example=l-shape").get_data(
        as_text=True
    )
    assert _value(fresh, "offset_x") == "0"
    assert _value(fresh, "offset_y") == "0"
    skeleton = _client().post(
        "/",
        data=_rect_post(method="skeleton", offset_x="1", offset_y="0"),
    ).get_data(as_text=True)
    assert "ridge: 4.000 m" in skeleton
    assert _value(skeleton, "offset_x") == "1"
    assert "Place at the center" not in skeleton
    back = _client().post("/", data=_rect_post(offset_x="1", offset_y="0")).get_data(
        as_text=True
    )
    short = math.degrees(math.atan(3.0 / 4.0))
    assert f"edge 1: pitch {short:g}°" in back
    assert "Place at the center" in back


def test_single_plane_and_failure_hide_placement_controls() -> None:
    plane = _client().post(
        "/",
        data=_rect_post(**{"face-0": "0,1,2,3"}),
    ).get_data(as_text=True)
    assert 'name="offset_x"' not in plane
    assert "Place at the center" not in plane
    refused = _client().get(
        "/?method=experimental&example=self-intersecting"
    ).get_data(as_text=True)
    assert 'name="offset_x"' not in refused
    assert "Place at the center" not in refused


def test_a_dxf_resets_the_offset_to_zero() -> None:
    doc = ezdxf.new("R2010")  # type: ignore[attr-defined]
    doc.modelspace().add_lwpolyline(
        [(0, 0), (8000, 0), (8000, 4000), (0, 4000)],
        close=True,
    )
    buf = StringIO()
    doc.write(buf)
    payload = buf.getvalue().encode("utf-8")
    data: dict[str, object] = {
        **_rect_post(offset_x="1", offset_y="0"),
        "dxf_units": "mm",
        "upload_dxf": "1",
        "dxf": (BytesIO(payload), "plan.dxf"),
    }
    page = _client().post("/", data=data, content_type="multipart/form-data").get_data(
        as_text=True
    )
    assert _value(page, "offset_x") == "0"
    assert _value(page, "offset_y") == "0"
