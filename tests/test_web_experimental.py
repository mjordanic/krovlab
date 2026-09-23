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
        "face-0": "0",
        "face-1": "1",
        "face-2": "2,3",
        "face-3": "4",
        "face-4": "5",
    }
    for i, (x, y) in enumerate(L_SHAPE):
        data[f"outer-x-{i}"] = str(x)
        data[f"outer-y-{i}"] = str(y)
        data[f"type-{i}"] = "hip"
        data[f"pitch-{i}"] = "45"
    data.update(overrides)
    return data


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


def test_experimental_copy_says_pitch_is_not_an_input() -> None:
    page = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert "pitch is not an input" in page.lower()
    assert "gable" in page.lower()
    assert "knee" in page.lower()
    assert "gambrel" in page.lower()
    assert "not part of this method" in page.lower()
    assert "network chose" not in page.lower()
    assert "a network chooses" not in page.lower()


def test_experimental_l_shows_plan_and_3d_of_the_face_graph_roof() -> None:
    built = roof_from_face_graph(L_SHAPE, MIXED)
    assert isinstance(built, Roof)
    page = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert "terrain: True" in page
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    assert "Roof plan" in page
    assert "3D solid" in page
    assert "Failure" not in page or "kind:" not in page.split("Failure")[0]


def test_skeleton_post_of_the_l_still_has_one_face_per_wall() -> None:
    built = roof(L_SHAPE, 45.0)
    assert isinstance(built, Roof)
    page = _client().post("/", data=_l_post(method="skeleton")).get_data(as_text=True)
    assert f"ridge height: {built.ridge_height:.3f} m" in page
    for face in built.faces:
        assert f"edge {face.edge_index}:" in page


def test_switching_back_to_the_skeleton_restores_the_skeleton_roof() -> None:
    experimental = roof_from_face_graph(L_SHAPE, MIXED)
    skeleton = roof(L_SHAPE, 45.0)
    assert isinstance(experimental, Roof)
    assert isinstance(skeleton, Roof)
    first = (
        _client().post("/", data=_l_post(method="experimental")).get_data(as_text=True)
    )
    assert f"ridge height: {experimental.ridge_height:.3f} m" in first
    second = _client().post("/", data=_l_post(method="skeleton")).get_data(as_text=True)
    assert f"ridge height: {skeleton.ridge_height:.3f} m" in second


def test_experimental_without_a_face_graph_is_no_face_graph() -> None:
    data = _l_post(method="experimental")
    del data["face-0"]
    del data["face-1"]
    del data["face-2"]
    del data["face-3"]
    del data["face-4"]
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "no_face_graph" in page
    assert "Failure" in page
    assert "3D solid" not in page


def test_experimental_post_does_not_use_pitch() -> None:
    built = roof_from_face_graph(L_SHAPE, MIXED)
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
