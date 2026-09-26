"""The experimental page roofs from the links the visitor set.

Opening the L shows the straight skeleton. A typed ridge offset stays in
the field. The page says how to connect a wall, and it does not mention a
graph network.
"""

from __future__ import annotations

import re
from html import unescape

from flask.testing import FlaskClient
from web.app import create_app
from web.interior_form import InteriorRow
from web.link_form import views_for

from krovlab.links import Target


def _client() -> FlaskClient:
    return create_app().test_client()


def test_the_l_opens_on_the_skeleton_links() -> None:
    page = _client().get("/?method=experimental&example=l-shape").get_data(as_text=True)
    assert "terrain: True" in page
    assert "ridge height: 3.000 m" in page
    assert 'name="ridge-0-height"' in page
    assert 'name="ridge-1-height"' in page
    assert "graph network" not in page.lower()
    assert "drains to" in page.lower()
    assert "Add vertex on selected wall" in page
    assert "Both pieces keep" in page


def test_a_typed_ridge_offset_stays_and_an_open_wall_is_named() -> None:
    client = _client()
    page = client.get("/?method=experimental&example=l-shape").get_data(as_text=True)
    fields = _posted_from_page(page)
    fields["ridge-0-x"] = "1.25"
    fields["wall-0-target"] = ""
    updated = client.post("/", data=fields).get_data(as_text=True)
    assert 'name="ridge-0-x" value="1.25"' in updated
    assert "wall 1 is open" in updated
    assert "terrain: True" not in updated


def test_a_split_wall_keeps_the_same_drain_on_both_pieces() -> None:
    client = _client()
    page = client.get(
        "/?method=experimental&example=hip-rectangle"
    ).get_data(as_text=True)
    fields = _posted_from_page(page)
    target = fields["wall-0-target"]
    for index in (3, 2, 1):
        fields[f"outer-x-{index + 1}"] = fields[f"outer-x-{index}"]
        fields[f"outer-y-{index + 1}"] = fields[f"outer-y-{index}"]
        fields[f"wall-{index + 1}-target"] = fields[f"wall-{index}-target"]
        fields[f"corner-{index + 1}-target"] = fields.get(f"corner-{index}-target", "")
    fields["outer-x-1"] = "5"
    fields["outer-y-1"] = "0"
    fields["wall-0-target"] = target
    fields["wall-1-target"] = target
    fields["corner-1-target"] = ""
    updated = _posted_from_page(client.post("/", data=fields).get_data(as_text=True))
    assert updated["wall-0-target"] == target
    assert updated["wall-1-target"] == target
    assert float(updated["outer-x-4"]) == 0
    assert float(updated["outer-y-1"]) == 0


def test_a_join_does_not_offer_the_other_end_of_the_same_ridge() -> None:
    rows = (
        InteriorRow("ridge", 0, "0", "0", direction="0", length="4", height="3"),
        InteriorRow("ridge", 1, "1", "0", direction="90", length="4", height="1.5"),
    )
    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
    views = views_for(
        ring,
        (None, None, None, None),
        (None, None, None, None),
        ((Target("ridge", 0, 0), Target("ridge", 1, 0)),),
        rows,
    )
    left = [option.value for option in views.joins[0].left]
    right = [option.value for option in views.joins[0].right]
    assert "ridge-1-end-1" not in left
    assert "ridge-0-end-1" not in right
    assert "ridge-0-end-0" in left
    assert "ridge-1-end-0" in right


def _posted_from_page(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(r"<input\b([^>]*)>", html):
        attrs = match.group(1)
        name_match = re.search(r'\bname="([^"]*)"', attrs)
        if name_match is None:
            continue
        name = name_match.group(1)
        kind = re.search(r'\btype="([^"]*)"', attrs)
        input_type = kind.group(1) if kind else "text"
        if input_type in {"radio", "checkbox"} and "checked" not in attrs:
            continue
        if input_type == "hidden" and name in fields:
            continue
        value_match = re.search(r'\bvalue="([^"]*)"', attrs)
        fields[name] = unescape(value_match.group(1)) if value_match else ""
    for match in re.finditer(
        r'<select\b[^>]*\bname="([^"]*)"[^>]*>(.*?)</select>', html, re.S
    ):
        body = match.group(2)
        selected = re.search(r'<option\b[^>]*\bselected[^>]*\bvalue="([^"]*)"', body)
        if selected is None:
            selected = re.search(
                r'<option\b[^>]*\bvalue="([^"]*)"[^>]*\bselected', body
            )
        fields[match.group(1)] = unescape(selected.group(1)) if selected else ""
    return fields
