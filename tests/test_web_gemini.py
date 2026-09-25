"""Gemini adapter: current Flash id, thinking_level, thought signatures."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from google.genai import types
from web.agent.gemini import MODEL_ID, GeminiModel, _from_response, _to_content
from web.agent.loop import LoopMessage, ToolCall


def test_help_uses_gemini_36_flash() -> None:
    assert MODEL_ID == "gemini-3.6-flash"


def test_complete_sends_minimal_thinking_not_a_budget(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    class FakeModels:
        def generate_content(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            part = types.Part.from_text(text="ok")
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(content=types.Content(role="model", parts=[part]))
                ]
            )

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.models = FakeModels()

    monkeypatch.setattr("web.agent.gemini.genai.Client", FakeClient)
    turn = GeminiModel(api_key="x").complete(
        system="s",
        messages=[LoopMessage(role="user", content="hi")],
    )
    assert turn.text == "ok"
    assert captured["model"] == "gemini-3.6-flash"
    thinking = captured["config"].thinking_config
    assert thinking.thinking_level == types.ThinkingLevel.MINIMAL
    assert thinking.thinking_budget is None


def test_tool_turns_replay_the_model_parts_with_thought_signatures() -> None:
    signature = b"sig-bytes"
    raw = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(name="inspect_project", args={}),
                thought_signature=signature,
            )
        ],
    )
    turn = _from_response(SimpleNamespace(candidates=[SimpleNamespace(content=raw)]))
    assert turn.tool_calls[0].name == "inspect_project"
    replayed = _to_content(
        LoopMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall("inspect_project")],
            raw=turn.raw,
        )
    )
    assert replayed.parts is not None
    assert replayed.parts[0].thought_signature == signature
    assert replayed.parts[0].function_call is not None
    assert replayed.parts[0].function_call.name == "inspect_project"
