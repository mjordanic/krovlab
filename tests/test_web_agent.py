"""Help agent: form-field tools and POST /agent.

The seam is the posted form dict the page already uses, plus one JSON
route. The model is injected; tests never call Gemini.
"""

from __future__ import annotations

from typing import Any

import pytest
from web.agent.loop import ModelTurn, ToolCall, run_turn
from web.agent.prompt import system_prompt
from web.agent.rate_limit import RateLimiter
from web.agent.tools import inspect_project, set_cell, set_wall
from web.app import create_app


def _rect() -> dict[str, str]:
    return {
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


def test_inspect_project_numbers_walls_as_the_page_does() -> None:
    snapshot = inspect_project(_rect())
    walls = snapshot["cells"][0]["walls"]
    assert [wall["wall"] for wall in walls] == [1, 2, 3, 4]
    assert walls[2]["from"] == [10.0, 6.0]
    assert walls[2]["to"] == [0.0, 6.0]
    assert walls[2]["type"] == "hip"
    assert walls[2]["pitch"] == "45"


def test_increase_wall_3_pitch_by_five_degrees_patches_the_form() -> None:
    result = set_wall(_rect(), cell=1, wall=3, pitch_delta=5)
    assert result.ok
    assert result.fields["pitch-2"] == "50"
    assert result.fields["type-2"] == "hip"
    assert "50" in result.note
    assert "Wall 3" in result.note


def test_gable_is_a_type_not_an_increased_pitch() -> None:
    result = set_wall(_rect(), cell=1, wall=2, type="gable")
    assert result.ok
    assert result.fields["type-1"] == "gable"
    assert result.fields["pitch-1"] == "90"


def test_increase_must_not_become_a_gable() -> None:
    steep = dict(_rect())
    steep["pitch-0"] = "88"
    result = set_wall(steep, cell=1, wall=1, pitch_delta=5)
    assert not result.ok
    assert "gable" in result.note.lower()


def test_set_cell_overhang_checks_the_form_box() -> None:
    result = set_cell(_rect(), cell=1, overhang=0.5)
    assert result.ok
    assert result.fields["overhang"] == "0.5"
    assert result.fields["use_overhang"] == "on"


def test_run_turn_keeps_adapter_raw_for_the_next_model_call() -> None:
    raw = object()
    model = ScriptedModel(
        [
            ModelTurn(
                tool_calls=[ToolCall("inspect_project")],
                raw=raw,
            ),
            ModelTurn(text="Wall 3 is 45°."),
        ]
    )
    run_turn(
        model,
        form=_rect(),
        messages=[{"role": "user", "content": "what pitch is wall 3?"}],
    )
    assert any(item.raw is raw for item in model.messages)


class BoomModel:
    def complete(self, *, system: str, messages: Any) -> ModelTurn:
        raise RuntimeError("404 NOT_FOUND")


def test_agent_maps_model_failures_to_a_public_502() -> None:
    client = create_app(model=BoomModel()).test_client()
    response = client.post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "fields": _rect(),
        },
    )
    assert response.status_code == 502
    body = response.get_json()
    assert body is not None
    assert body["error"] == "Help could not reach the language model."


class ScriptedModel:
    """One scripted Gemini-shaped turn at a time."""

    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = list(turns)
        self.system = ""
        self.messages: list[Any] = []

    def complete(self, *, system: str, messages: Any) -> ModelTurn:
        self.system = system
        self.messages = list(messages)
        assert self._turns, "model asked for more turns than the script"
        return self._turns.pop(0)


class EchoModel:
    def complete(self, *, system: str, messages: Any) -> ModelTurn:
        self.system = system
        self.messages = list(messages)
        return ModelTurn(text="Ridge height is 3 m on the takeoff already on the page.")


def test_help_prefers_the_skeleton_and_knows_the_graph_network() -> None:
    text = system_prompt().lower()
    assert "prefer" in text and "standard skeleton" in text
    assert "experimental graph network" in text
    assert "roof height" in text
    assert "face over several" in text
    assert "unliftable" in text
    assert "does not take a pitch" in text or "pitch is not an input" in text
    assert "load dxf" in text
    assert "roof.obj" in text and "roof.glb" in text


def test_set_cell_roof_height_patches_the_experimental_form() -> None:
    form = dict(_rect())
    form["method"] = "experimental"
    result = set_cell(form, cell=1, roof_height=2.0)
    assert result.ok
    assert result.fields["roof_height"] == "2"
    assert "Update roof" in result.note


def test_set_wall_refuses_while_the_graph_network_is_selected() -> None:
    form = dict(_rect())
    form["method"] = "experimental"
    result = set_wall(form, cell=1, wall=3, pitch_delta=5)
    assert not result.ok
    assert "skeleton" in result.note.lower()


def test_roof_height_is_not_a_skeleton_knob() -> None:
    result = set_cell(_rect(), cell=1, roof_height=2.0)
    assert not result.ok
    assert "experimental" in result.note.lower()


def test_inspect_reports_the_method_and_roof_height() -> None:
    form = dict(_rect())
    form["method"] = "experimental"
    form["roof_height"] = "3"
    snapshot = inspect_project(form)
    assert snapshot["method"] == "experimental"
    assert snapshot["roof_height_m"] == "3"


def test_system_prompt_carries_glossary_limits_and_readme() -> None:
    text = system_prompt()
    assert "sloped area" in text
    assert "is_terrain" in text
    assert "straight skeleton" in text
    assert "Update roof" in text
    assert "Failure" in text
    assert "0 < pitch" in text or "invalid_pitch" in text
    assert "LaTeX" in text


def test_agent_increases_side_3_through_json() -> None:
    model = ScriptedModel(
        [
            ModelTurn(
                tool_calls=[
                    ToolCall("set_wall", {"cell": 1, "wall": 3, "pitch_delta": 5})
                ]
            ),
            ModelTurn(text="Wall 3 is now 50°."),
        ]
    )
    client = create_app(model=model).test_client()
    response = client.post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "increase the angle of side 3"}],
            "fields": _rect(),
            "describe": "ridge height 3.0 m",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert body["fields"]["pitch-2"] == "50"
    assert "Update roof" in body["reply"]


def _experimental_rect(**overrides: str) -> dict[str, str]:
    form = dict(_rect())
    form["method"] = "experimental"
    form["roof_height"] = "3"
    form["offset_x"] = "0"
    form["offset_y"] = "0"
    form["snap"] = "on"
    form.update(overrides)
    return form


def _turn(form: dict[str, str], args: dict[str, object], text: str) -> dict[str, str]:
    model = ScriptedModel(
        [
            ModelTurn(tool_calls=[ToolCall("set_cell", args)]),
            ModelTurn(text=text),
        ]
    )
    reply = run_turn(
        model,
        form=form,
        messages=[{"role": "user", "content": text}],
    )
    assert "Update roof" in reply.reply
    return reply.fields


def test_helper_places_the_apex_the_ridge_snap_and_symmetry() -> None:
    centered = _turn(
        _experimental_rect(offset_x="1", offset_y="0.5"),
        {"center": True},
        "Center the apex.",
    )
    assert centered["offset_x"] == "0"
    assert centered["offset_y"] == "0"
    moved = _turn(
        _experimental_rect(offset_x="1", offset_y="0"),
        {"move_x": 0.5, "move_y": -1},
        "Add an offset.",
    )
    assert moved["offset_x"] == "1.5"
    assert moved["offset_y"] == "-1"
    toward = _turn(
        _experimental_rect(),
        {"toward_wall": 2},
        "Move toward wall 2.",
    )
    assert toward["offset_x"] == "1"
    assert toward["offset_y"] == "0"
    ridge = _turn(_experimental_rect(), {"style": "ridge"}, "Choose the ridge.")
    assert ridge["style"] == "ridge"
    pyramid = _turn(_experimental_rect(style="ridge"), {"style": "pyramid"}, "Pyramid.")
    assert pyramid["style"] == "apex"
    pyramide = _turn(
        _experimental_rect(style="ridge"), {"style": "pyramide"}, "Pyramide."
    )
    assert pyramide["style"] == "apex"
    snap = _turn(_experimental_rect(), {"snap": "off"}, "Turn snap off.")
    assert snap["snap"] == "off"
    held = _turn(
        _experimental_rect(offset_x="1", offset_y="0.5"),
        {"hold": 0},
        "Hold the first reflection.",
    )
    assert held["offset_x"] == "0"
    assert held["offset_y"] == "0.5"
    assert held["hold-0"] == "on"
    symmetric = _turn(
        _experimental_rect(offset_x="1", offset_y="0.5"),
        {"symmetric": True},
        "Make it symmetric.",
    )
    assert symmetric["offset_x"] == "0"
    assert symmetric["offset_y"] == "0"
    assert symmetric["hold-0"] == "on"
    assert symmetric["hold-1"] == "on"


def test_helper_leaves_fields_unchanged_when_the_control_is_absent() -> None:
    ell = _experimental_rect(
        **{
            "example": "l-shape",
            "outer-x-0": "0",
            "outer-y-0": "0",
            "outer-x-1": "10",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "6",
            "outer-x-3": "3",
            "outer-y-3": "6",
            "outer-x-4": "3",
            "outer-y-4": "10",
            "outer-x-5": "0",
            "outer-y-5": "10",
            "offset_x": "1",
        }
    )
    ridge = set_cell(ell, style="ridge")
    assert ridge.fields == {}
    assert "no ridge" in ridge.note.lower()
    missing = set_cell(ell, symmetric=True)
    assert missing.fields == {}
    assert "reflection" in missing.note.lower()
    spanned = _experimental_rect(
        **{
            "outer-x-1": "5",
            "outer-y-1": "0",
            "outer-x-2": "10",
            "outer-y-2": "0",
            "outer-x-3": "10",
            "outer-y-3": "6",
            "outer-x-4": "0",
            "outer-y-4": "6",
            "face-0": "0,1",
            "face-1": "2",
            "face-2": "3",
            "face-3": "4",
            "offset_x": "1",
        }
    )
    spanned_ridge = set_cell(spanned, style="ridge")
    assert spanned_ridge.fields == {}
    assert "ridge" in spanned_ridge.note.lower()
    plane = _experimental_rect(**{"face-0": "0,1,2,3"})
    nowhere = set_cell(plane, center=True)
    assert nowhere.fields == {}
    assert "single plane" in nowhere.note.lower() or "failure" in nowhere.note.lower()
    bowtie = _experimental_rect(
        **{
            "outer-x-1": "10",
            "outer-y-1": "10",
            "outer-x-2": "10",
            "outer-y-2": "0",
            "outer-x-3": "0",
            "outer-y-3": "10",
        }
    )
    failed = set_cell(bowtie, center=True)
    assert failed.fields == {}
    unknown = set_cell(_experimental_rect(), placement="spin the apex")
    assert unknown.fields == {}
    model = ScriptedModel(
        [
            ModelTurn(tool_calls=[ToolCall("set_cell", {"style": "ridge"})]),
            ModelTurn(text="This footprint has no ridge. The apex stays."),
        ]
    )
    reply = run_turn(
        model,
        form=ell,
        messages=[{"role": "user", "content": "Give this L a ridge."}],
    )
    assert reply.fields == {}


def test_helper_still_sets_roof_height_and_refuses_a_wall_type() -> None:
    form = _experimental_rect()
    result = set_cell(form, cell=1, roof_height=2.0, overhang=0.4, eave_height=1.0)
    assert result.ok
    assert result.fields["roof_height"] == "2"
    assert result.fields["overhang"] == "0.4"
    assert result.fields["eave_height"] == "1"
    assert "Update roof" in result.note
    refused = set_wall(form, cell=1, wall=2, type="gable")
    assert not refused.ok
    assert refused.fields == {}


def test_helper_instructions_name_placement_and_absent_controls() -> None:
    text = system_prompt().lower()
    assert "apex" in text
    assert "ridge" in text
    assert "offset" in text
    assert "move toward a wall" in text
    assert "snap" in text
    assert "symmetry" in text
    assert "no ridge on an l" in text
    assert "spanned face" in text
    assert "no symmetry the footprint lacks" in text
    assert "single plane" in text
    assert "failure" in text


def test_agent_sets_roof_height_on_the_experimental_form() -> None:
    model = ScriptedModel(
        [
            ModelTurn(tool_calls=[ToolCall("set_cell", {"cell": 1, "roof_height": 2})]),
            ModelTurn(text="Roof height is 2 m above the eaves."),
        ]
    )
    fields = dict(_rect())
    fields["method"] = "experimental"
    client = create_app(model=model).test_client()
    response = client.post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "make the roof 2 m above the eaves"}],
            "fields": fields,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert body["fields"]["roof_height"] == "2"


def test_agent_answers_from_the_page_takeoff() -> None:
    model = EchoModel()
    client = create_app(model=model).test_client()
    response = client.post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "what is the ridge height?"}],
            "fields": _rect(),
            "describe": "ridge height 3.0 m\nterrain: yes",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert "3 m" in body["reply"]
    blob = " ".join(item.content for item in model.messages)
    assert "ridge height 3.0 m" in blob


def test_agent_requires_the_current_project() -> None:
    client = create_app(model=EchoModel()).test_client()
    response = client.post(
        "/agent",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400


def test_agent_is_off_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = create_app().test_client()
    response = client.post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "fields": _rect(),
        },
    )
    assert response.status_code == 503
    page = client.get("/").get_data(as_text=True)
    assert 'id="need-help"' not in page
    assert 'id="help-root"' not in page


def test_need_help_is_on_the_page_when_the_agent_is_configured() -> None:
    page = create_app(model=EchoModel()).test_client().get("/").get_data(as_text=True)
    assert "Need help?" in page
    assert 'id="help-root"' in page
    assert 'id="need-help"' in page
    assert "noindex" in page
    assert "no-referrer" in page


def test_agent_rate_limit_trips_per_address() -> None:
    client = create_app(
        model=EchoModel(),
        limiter=RateLimiter(per_minute=2, per_hour=10),
    ).test_client()
    payload = {
        "messages": [{"role": "user", "content": "hi"}],
        "fields": _rect(),
        "describe": "ok",
    }
    assert client.post("/agent", json=payload).status_code == 200
    assert client.post("/agent", json=payload).status_code == 200
    blocked = client.post("/agent", json=payload)
    assert blocked.status_code == 429


def test_json_api_is_only_the_agent_route() -> None:
    app = create_app(model=EchoModel())
    rules = sorted(
        rule.rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"
    )
    assert rules == ["/", "/agent", "/roof.glb", "/roof.obj"]
    assert app.test_client().get("/api/roofs").status_code == 404
