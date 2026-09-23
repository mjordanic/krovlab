"""Form seam for the experimental method choice.

GET/POST of the page: which method is selected, which copy the visitor
reads, and which entry point ran. Not CSS.
"""

from __future__ import annotations

from flask.testing import FlaskClient
from web.app import create_app
from web.examples import L_SHAPE, RECTANGLE

from krovlab import Roof, roof
from krovlab.experimental import roof_from_face_graph

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
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
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
