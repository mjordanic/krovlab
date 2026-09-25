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
from krovlab.experimental import Apex, roof_from_interiors

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


def test_experimental_post_without_a_face_graph_roofs_the_placed_interior() -> None:
    built = roof_from_interiors(L_SHAPE)
    assert isinstance(built, Roof)
    page = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert f"terrain: {built.validity.is_terrain}" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
    assert "Add apex" in page


def test_skeleton_post_of_the_l_still_has_one_face_per_wall() -> None:
    built = roof(L_SHAPE, 45.0)
    assert isinstance(built, Roof)
    page = _client().post("/", data=_l_post(method="skeleton")).get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    for face in built.faces:
        assert f"edge {face.edge_index}:" in page


def test_switching_to_the_skeleton_starts_that_roof_from_scratch() -> None:
    skeleton = roof(L_SHAPE, 45.0)
    assert isinstance(skeleton, Roof)
    page = _client().post(
        "/",
        data=_l_post(method="skeleton", built_method="experimental"),
    ).get_data(as_text=True)
    assert f"ridge height: {skeleton.ridge_height:.3f} m" in page


def test_a_posted_face_graph_does_not_change_the_interior_roof() -> None:
    built = roof_from_interiors(L_SHAPE)
    assert isinstance(built, Roof)
    page = (
        _client()
        .post("/", data=_l_post(method="experimental", **_mixed_fields()))
        .get_data(as_text=True)
    )
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page


def test_experimental_post_does_not_use_pitch() -> None:
    built = roof_from_interiors(L_SHAPE)
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
    assert "One face over two walls" not in page
    refused = _client().get(
        "/?method=experimental&example=self-intersecting"
    ).get_data(as_text=True)
    assert "kind: self_intersection" in refused


def test_catalog_example_roofs_under_either_method() -> None:
    skeleton = roof(RECTANGLE, 45.0)
    experimental = roof_from_interiors(RECTANGLE)
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
    data.setdefault("apex-0-x", data.get("offset_x", "0"))
    data.setdefault("apex-0-y", data.get("offset_y", "0"))
    data.setdefault("selected_interior", "apex-0")
    return data


def _value(page: str, name: str) -> str:
    name = {"offset_x": "apex-0-x", "offset_y": "apex-0-y"}.get(name, name)
    match = re.search(rf'name="{name}" value="([^"]*)"', page)
    assert match is not None, name
    return match.group(1)


def test_the_rectangle_lists_apexes_and_ridges() -> None:
    page = _client().get("/?method=experimental").get_data(as_text=True)
    assert "Add apex" in page
    assert "Add ridge" in page
    assert "Apex 1" in page
    assert 'name="apex-0-x" value="0"' in page
    ridge_data = _rect_post(roof_height="3")
    del ridge_data["apex-0-x"]
    del ridge_data["apex-0-y"]
    ridge_data.update(
        {
            "ridge-0-x": "0",
            "ridge-0-y": "0",
            "ridge-0-direction": "0",
            "ridge-0-length": "4",
            "selected_interior": "ridge-0",
        }
    )
    ridge = _client().post("/", data=ridge_data).get_data(as_text=True)
    assert "ridge: 4.000 m" in ridge
    assert "terrain: True" in ridge
    assert "Ridge 1" in ridge
    for edge in range(4):
        assert f"edge {edge}: pitch 45°" in ridge
    apex = _client().post("/", data=_rect_post(roof_height="3")).get_data(as_text=True)
    assert "ridge: " not in apex
    assert "terrain: True" in apex
    kept = _client().post(
        "/",
        data=_rect_post(
            **{"ridge-0-x": "1", "ridge-0-y": "-0.5", "ridge-0-length": "2"}
        ),
    ).get_data(as_text=True)
    assert _value(kept, "ridge-0-x") == "1"
    assert _value(kept, "ridge-0-y") == "-0.5"


def test_the_l_stays_editable_so_two_ridges_can_replace_the_apex() -> None:
    client = _client()
    fresh = client.get("/?method=experimental&example=l-shape").get_data(as_text=True)
    alone = client.post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="3",
            selected_interior="apex-0",
            delete_interior="1",
            **{
                "apex-0-x": _value(fresh, "apex-0-x"),
                "apex-0-y": _value(fresh, "apex-0-y"),
            },
        ),
    ).get_data(as_text=True)
    assert "Add another apex or ridge before deleting this one." in alone
    assert "Apex 1" in alone
    assert "<fieldset disabled>" not in alone
    added = client.post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="3",
            selected_interior="apex-0",
            add_ridge="1",
            **{
                "apex-0-x": _value(fresh, "apex-0-x"),
                "apex-0-y": _value(fresh, "apex-0-y"),
            },
        ),
    ).get_data(as_text=True)
    assert "Ridge 1" in added
    assert "Apex 1" in added
    assert "<fieldset disabled>" not in added
    assert _value(added, "roof_height") == "3"
    removed = client.post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="3",
            selected_interior="apex-0",
            delete_interior="1",
            **{
                "apex-0-x": _value(added, "apex-0-x"),
                "apex-0-y": _value(added, "apex-0-y"),
                "ridge-0-x": _value(added, "ridge-0-x"),
                "ridge-0-y": _value(added, "ridge-0-y"),
                "ridge-0-direction": _value(added, "ridge-0-direction"),
                "ridge-0-length": _value(added, "ridge-0-length"),
            },
        ),
    ).get_data(as_text=True)
    assert "Apex 1" not in removed
    assert "Ridge 1" in removed
    assert "<fieldset disabled>" not in removed
    roof = client.post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="3",
            selected_interior="ridge-1",
            **{
                "ridge-0-x": "-1",
                "ridge-0-y": "0",
                "ridge-0-direction": "0",
                "ridge-0-length": "4",
                "ridge-1-x": "-3",
                "ridge-1-y": "3",
                "ridge-1-direction": "90",
                "ridge-1-length": "6",
            },
        ),
    ).get_data(as_text=True)
    assert "terrain: True" in roof
    assert "Apex 1" not in roof
    assert "Ridge 1" in roof
    assert "Ridge 2" in roof
    assert _value(roof, "ridge-0-length") == "4"
    assert _value(roof, "ridge-1-length") == "6"


def test_the_l_form_keeps_a_different_height_on_each_ridge() -> None:
    page = _client().post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="2",
            selected_interior="ridge-1",
            **{
                "ridge-0-x": "0",
                "ridge-0-y": "0",
                "ridge-0-direction": "0",
                "ridge-0-length": "4",
                "ridge-0-height": "3",
                "ridge-1-x": "-3.5",
                "ridge-1-y": "3.5",
                "ridge-1-direction": "90",
                "ridge-1-length": "4",
                "ridge-1-height": "1.5",
            },
        ),
    ).get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.000 m" in page
    assert _value(page, "ridge-0-height") == "3"
    assert _value(page, "ridge-1-height") == "1.5"
    assert "Apex 1" not in page


def test_roof_height_box_keeps_rows_and_seeds_a_new_ridge() -> None:
    kept = _client().post(
        "/",
        data=_l_post(
            method="experimental",
            built_method="experimental",
            roof_height="4",
            selected_interior="ridge-0",
            **{
                "ridge-0-x": "0",
                "ridge-0-y": "0",
                "ridge-0-direction": "0",
                "ridge-0-length": "4",
                "ridge-0-height": "3",
                "ridge-1-x": "-3.5",
                "ridge-1-y": "3.5",
                "ridge-1-direction": "90",
                "ridge-1-length": "4",
                "ridge-1-height": "1.5",
            },
        ),
    ).get_data(as_text=True)
    assert _value(kept, "roof_height") == "4"
    assert _value(kept, "ridge-0-height") == "3"
    assert _value(kept, "ridge-1-height") == "1.5"
    assert "ridge height: 3.000 m" in kept
    added = _client().post(
        "/",
        data=_rect_post(roof_height="4", add_ridge="1", **{"apex-0-height": "3"}),
    ).get_data(as_text=True)
    assert _value(added, "roof_height") == "4"
    assert _value(added, "apex-0-height") == "3"
    assert _value(added, "ridge-0-height") == "4"


def test_a_blank_ridge_height_uses_the_roof_height_box() -> None:
    data = _rect_post(roof_height="3", selected_interior="ridge-0")
    del data["apex-0-x"]
    del data["apex-0-y"]
    data.update(
        {
            "ridge-0-x": "0",
            "ridge-0-y": "0",
            "ridge-0-direction": "0",
            "ridge-0-length": "4",
            "ridge-0-height": "",
        }
    )
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.000 m" in page
    assert _value(page, "ridge-0-height") == "3"
    for edge in range(4):
        assert f"edge {edge}: pitch 45°" in page


def test_the_l_keeps_the_same_interior_card() -> None:
    ell = _client().get("/?method=experimental&example=l-shape").get_data(as_text=True)
    assert "Add ridge" in ell
    assert "Add apex" in ell
    assert "This footprint has no reflection." in ell
    asked = _client().post(
        "/",
        data=_l_post(method="experimental", **{"apex-0-x": "0", "apex-0-y": "0"}),
    ).get_data(as_text=True)
    assert "Add ridge" in asked
    assert "terrain: True" in asked
    assert "Apex 1" in asked


def test_a_corner_edit_keeps_the_ridge_offset() -> None:
    kept = _client().post(
        "/",
        data=_rect_post(
            **{
                "ridge-0-x": "1",
                "ridge-0-y": "0",
                "ridge-0-direction": "0",
                "ridge-0-length": "2",
                "outer-y-2": "8",
                "outer-y-3": "8",
            },
        ),
    ).get_data(as_text=True)
    assert "Ridge 1" in kept
    assert _value(kept, "ridge-0-x") == "1"


def test_experimental_explanation_says_the_visitor_can_move_the_apex() -> None:
    page = _client().get("/?method=experimental").get_data(as_text=True)
    assert "add an apex or a ridge" in page.lower()
    assert 'name="apex-0-x" value="0"' in page
    assert 'name="apex-0-y" value="0"' in page
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


def test_place_at_center_returns_the_apex_to_the_middle() -> None:
    centered = _client().post(
        "/",
        data=_rect_post(offset_x="1", offset_y="0", place_at_center="1"),
    ).get_data(as_text=True)
    assert _value(centered, "offset_x") == "0"
    assert _value(centered, "offset_y") == "0"
    assert "edge 0: pitch 45°" in centered


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


def test_a_move_pulls_back_from_the_spot_already_shown() -> None:
    page = _client().post(
        "/",
        data=_rect_post(
            offset_x="2",
            **{
                "apex-0-y": "10",
                "was-apex-0-x": "2",
                "was-apex-0-y": "0",
            },
        ),
    ).get_data(as_text=True)
    assert float(_value(page, "apex-0-x")) == pytest.approx(2.0, abs=0.05)
    assert float(_value(page, "apex-0-y")) <= 3.0
    assert "terrain: True" in page


def test_corner_edit_and_overhang_keep_the_offset_from_the_new_middle() -> None:
    edited = _rect_post(
        offset_x="1",
        offset_y="0",
        **{"outer-y-2": "8", "outer-y-3": "8"},
    )
    page = _client().post("/", data=edited).get_data(as_text=True)
    assert _value(page, "offset_x") == "1"
    assert _value(page, "offset_y") == "0"
    built = roof_from_interiors(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)],
        (Apex(6.0, 4.0),),
        roof_height=3.0,
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


def test_another_example_resets_and_a_method_switch_starts_fresh() -> None:
    fresh = _client().get("/?method=experimental&example=l-shape").get_data(
        as_text=True
    )
    assert "Apex 1" in fresh
    assert "Add apex" in fresh
    skeleton = _client().post(
        "/",
        data=_rect_post(
            method="skeleton",
            built_method="experimental",
            offset_x="1",
            offset_y="0",
        ),
    ).get_data(as_text=True)
    assert "ridge: 4.000 m" in skeleton
    assert "Place at the center" not in skeleton
    back = _client().post(
        "/",
        data=_rect_post(built_method="skeleton", offset_x="1", offset_y="0"),
    ).get_data(as_text=True)
    assert _value(back, "apex-0-x") == "0"
    assert "Place at the center" in back


def test_failure_keeps_the_card_and_says_why() -> None:
    refused = _client().get(
        "/?method=experimental&example=self-intersecting"
    ).get_data(as_text=True)
    assert "Place at the center" in refused
    assert "This footprint has no roof to place." in refused
    assert "<fieldset disabled>" in refused


def test_snap_starts_on_survives_update_and_returns_for_a_new_building() -> None:
    fresh = _client().get("/?method=experimental").get_data(as_text=True)
    assert 'name="snap" value="on" checked' in fresh
    assert 'name="apex-0-x"' in fresh
    updated = _client().post(
        "/", data=_rect_post(snap="off", offset_x="1", offset_y="0")
    ).get_data(as_text=True)
    assert 'name="snap" value="on" checked' not in updated
    assert 'name="snap" value="off"' in updated
    assert _value(updated, "offset_x") == "1"
    other = _client().get("/?method=experimental&example=l-shape").get_data(
        as_text=True
    )
    assert 'name="snap" value="on" checked' in other
    doc = ezdxf.new("R2010")  # type: ignore[attr-defined]
    doc.modelspace().add_lwpolyline(
        [(0, 0), (8000, 0), (8000, 4000), (0, 4000)],
        close=True,
    )
    buf = StringIO()
    doc.write(buf)
    payload = buf.getvalue().encode("utf-8")
    data: dict[str, object] = {
        **_rect_post(snap="off", offset_x="1", offset_y="0"),
        "dxf_units": "mm",
        "upload_dxf": "1",
        "dxf": (BytesIO(payload), "plan.dxf"),
    }
    replaced = _client().post(
        "/", data=data, content_type="multipart/form-data"
    ).get_data(as_text=True)
    assert 'name="snap" value="on" checked' in replaced


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
    assert _value(page, "apex-0-x") == "0"
    assert _value(page, "apex-0-y") == "0"
    assert "Apex 1" in page
    assert _checked(page, "snap")
    assert _checked(page, "hold-0")
    assert _checked(page, "hold-1")


def _checked(page: str, name: str) -> bool:
    return f'name="{name}" value="on" checked' in page


def test_the_rectangle_starts_with_both_reflections_checked() -> None:
    page = _client().get("/?method=experimental").get_data(as_text=True)
    assert _checked(page, "hold-0")
    assert _checked(page, "hold-1")
    assert _value(page, "apex-0-x") == "0"


def test_a_centered_ridge_can_leave_the_middle_with_symmetry_off() -> None:
    data = _rect_post()
    data.pop("apex-0-x")
    data.pop("apex-0-y")
    data.update(
        {
            "ridge-0-x": "1",
            "ridge-0-y": "0.5",
            "ridge-0-direction": "0",
            "ridge-0-length": "2",
            "was-ridge-0-x": "0",
            "was-ridge-0-y": "0",
            "was-ridge-0-direction": "0",
            "was-ridge-0-length": "2",
            "hold-0": "off",
            "hold-1": "off",
            "was-hold-0": "on",
            "was-hold-1": "on",
            "selected_interior": "ridge-0",
        }
    )
    page = _client().post("/", data=data).get_data(as_text=True)
    assert _value(page, "ridge-0-x") == "1"
    assert _value(page, "ridge-0-y") == "0.5"
    assert not _checked(page, "hold-0")
    assert not _checked(page, "hold-1")
    assert "terrain: True" in page


def test_checking_one_reflection_adds_the_mirror_copy() -> None:
    page = _client().post(
        "/",
        data=_rect_post(offset_x="1", offset_y="0.5", **{"hold-0": "on"}),
    ).get_data(as_text=True)
    assert _value(page, "apex-0-x") == "1"
    assert _value(page, "apex-0-y") == "0.5"
    assert "Apex 2" in page
    assert _checked(page, "hold-0")
    assert not _checked(page, "hold-1")


def test_one_reflection_has_one_checkbox_and_the_l_has_none() -> None:
    triangle = _client().post(
        "/",
        data={
            "example": "hip-rectangle",
            "set_pitch": "45",
            "method": "experimental",
            "roof_height": "3",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "4",
            "outer-y-1": "0",
            "outer-x-2": "2",
            "outer-y-2": "3",
            "type-0": "hip",
            "pitch-0": "45",
            "type-1": "hip",
            "pitch-1": "45",
            "type-2": "hip",
            "pitch-2": "45",
        },
    ).get_data(as_text=True)
    assert 'name="hold-0"' in triangle
    assert 'name="hold-1"' not in triangle
    ell = _client().get("/?method=experimental&example=l-shape").get_data(as_text=True)
    assert 'name="hold-0"' not in ell
    assert "This footprint has no reflection." in ell
    asked = _client().post(
        "/",
        data=_l_post(
            method="experimental",
            **{"apex-0-x": "1", "apex-0-y": "0", "make_symmetric": "1"},
        ),
    ).get_data(as_text=True)
    assert "This footprint has no reflection." in asked
    assert "Apex 1" in asked
    assert "Apex 2" not in asked


def test_make_it_symmetric_adds_the_missing_copies() -> None:
    page = _client().post(
        "/",
        data=_rect_post(offset_x="1", offset_y="0.5", make_symmetric="1"),
    ).get_data(as_text=True)
    assert "Apex 2" in page
    assert "Apex 4" in page
    assert _checked(page, "hold-0")
    assert _checked(page, "hold-1")


def test_a_corner_edit_drops_the_reflection_the_walls_lose() -> None:
    page = _client().post(
        "/",
        data=_rect_post(
            offset_x="1",
            offset_y="0.5",
            **{
                "outer-x-2": "8",
                "outer-y-2": "6",
                "outer-x-3": "2",
                "outer-y-3": "6",
                "axis-0": "1,0,5",
                "hold-0": "off",
                "axis-1": "0,1,3",
                "hold-1": "on",
            },
        ),
    ).get_data(as_text=True)
    assert 'name="hold-0"' in page
    assert 'name="hold-1"' not in page
    assert _value(page, "apex-0-x") == "1"
    assert _value(page, "apex-0-y") == "0.5"
    assert "This footprint has no such reflection. The roof stays." in page
    assert "ridge height:" in page


def test_update_keeps_the_offset_checkboxes_and_snap() -> None:
    page = _client().post(
        "/",
        data=_rect_post(
            offset_x="1",
            offset_y="0",
            snap="off",
            **{"axis-0": "1,0,5", "hold-0": "off", "axis-1": "0,1,3", "hold-1": "on"},
        ),
    ).get_data(as_text=True)
    assert _value(page, "apex-0-x") == "1"
    assert not _checked(page, "hold-0")
    assert _checked(page, "hold-1")
    assert not _checked(page, "snap")
    fresh = _client().get("/?method=experimental&example=l-shape").get_data(
        as_text=True
    )
    assert "Apex 1" in fresh
    assert _checked(fresh, "snap")
    assert 'name="hold-0"' not in fresh


def test_switching_method_starts_the_other_roof_from_scratch() -> None:
    skeleton = _client().post(
        "/",
        data=_rect_post(
            method="skeleton",
            built_method="experimental",
            offset_x="1",
            snap="off",
        ),
    ).get_data(as_text=True)
    assert "ridge: 4.000 m" in skeleton
    assert "Place at the center" not in skeleton
    back = _client().post(
        "/",
        data=_rect_post(built_method="skeleton", offset_x="1", snap="off"),
    ).get_data(as_text=True)
    assert _value(back, "apex-0-x") == "0"
    assert _checked(back, "snap")
    assert "Place at the center" in back
