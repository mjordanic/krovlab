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
