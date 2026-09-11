"""Chat replies must be readable: no raw LaTeX in the box."""

from __future__ import annotations

from typing import Any

from web.agent.format import plain_reply
from web.agent.loop import ModelTurn
from web.agent.prompt import system_prompt
from web.app import create_app


def _rect() -> dict[str, str]:
    return {
        "example": "hip-rectangle",
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


def test_latex_formula_becomes_plain_words() -> None:
    raw = (
        "Covering materials are bought by **sloped area** "
        r"($\text{plan area} / \cos(\text{pitch})$), not by flat plan area."
    )
    out = plain_reply(raw)
    assert "$" not in out
    assert r"\text" not in out
    assert r"\cos" not in out
    assert "plan area / cos(pitch)" in out
    assert "**sloped area**" in out


def test_agent_reply_unwraps_latex_before_json() -> None:
    class LatexModel:
        def complete(self, *, system: str, messages: Any) -> ModelTurn:
            return ModelTurn(
                text=(
                    "bought by **sloped area** "
                    r"($\text{plan area} / \cos(\text{pitch})$)."
                )
            )

    response = create_app(model=LatexModel()).test_client().post(
        "/agent",
        json={
            "messages": [{"role": "user", "content": "what is sloped area?"}],
            "fields": _rect(),
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert "$" not in body["reply"]
    assert "plan area / cos(pitch)" in body["reply"]
    assert "**sloped area**" in body["reply"]


def test_system_prompt_forbids_latex_in_the_chat_box() -> None:
    text = system_prompt()
    assert "LaTeX" in text
    assert "plan area / cos(pitch)" in text
