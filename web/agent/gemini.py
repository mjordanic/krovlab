"""Gemini 3.6 Flash adapter. Owner-pays; key never leaves the server."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from web.agent.loop import LoopMessage, ModelTurn, ToolCall

MODEL_ID = "gemini-3.6-flash"
MAX_OUTPUT_TOKENS = 1024

_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="inspect_project",
        description=(
            "Read the current cells and walls from the form after patches "
            "in this turn. Prefer the snapshot already in the conversation "
            "for the first look."
        ),
        parameters_json_schema={"type": "object", "properties": {}},
    ),
    types.FunctionDeclaration(
        name="set_wall",
        description=(
            "Change one wall's type and/or pitch. wall is the 1-based number "
            "printed on the page (Wall 1). Increase/decrease uses pitch_delta."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "cell": {
                    "type": "integer",
                    "description": "1-based cell number (Cell 1). Default 1.",
                },
                "wall": {
                    "type": "integer",
                    "description": "1-based wall number (Wall 1). Required.",
                },
                "type": {
                    "type": "string",
                    "enum": ["hip", "gable", "knee", "gambrel"],
                },
                "pitch": {
                    "type": "string",
                    "description": "Absolute pitch (degrees, 4:12, or 100%).",
                },
                "pitch_delta": {
                    "type": "number",
                    "description": (
                        "Degrees to add (negative to decrease). "
                        "Use 5 if they said increase with no number."
                    ),
                },
                "knee_height": {
                    "type": "number",
                    "description": (
                        "Metres of vertical wall before the slope. "
                        "Default 3 if making a knee."
                    ),
                },
                "gambrel_shallow": {"type": "string"},
                "gambrel_break": {
                    "type": "number",
                    "description": "Break height in metres above the eave.",
                },
            },
            "required": ["wall"],
        },
    ),
    types.FunctionDeclaration(
        name="set_cell",
        description="Set overhang (metres past the walls) or eave height on one cell.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "cell": {
                    "type": "integer",
                    "description": "1-based cell number. Default 1.",
                },
                "overhang": {
                    "type": "number",
                    "description": "Metres past the walls. 0 turns overhang off.",
                },
                "eave_height": {
                    "type": "number",
                    "description": "Metres above datum. 0 is the eave plane at datum.",
                },
            },
        },
    ),
]


class GeminiModel:
    def __init__(self, api_key: str, *, model: str = MODEL_ID) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._tools = [types.Tool(function_declarations=_FUNCTION_DECLARATIONS)]

    def complete(self, *, system: str, messages: Sequence[LoopMessage]) -> ModelTurn:
        contents = [_to_content(item) for item in messages]
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=self._tools,  # type: ignore[arg-type]
                temperature=0.2,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MINIMAL
                ),
            ),
        )
        return _from_response(response)


def _to_content(message: LoopMessage) -> types.Content:
    if message.role == "assistant" and isinstance(message.raw, types.Content):
        return message.raw
    if message.role == "tool":
        return types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name=message.name or "tool",
                    response={"result": message.content},
                )
            ],
        )
    if message.role == "assistant" and message.tool_calls:
        parts = [
            types.Part.from_function_call(name=call.name, args=call.args)
            for call in message.tool_calls
        ]
        if message.content:
            parts.insert(0, types.Part.from_text(text=message.content))
        return types.Content(role="model", parts=parts)
    role = "model" if message.role == "assistant" else "user"
    return types.Content(
        role=role,
        parts=[types.Part.from_text(text=message.content or " ")],
    )


def _from_response(response: Any) -> ModelTurn:
    candidates = getattr(response, "candidates", None) or []
    content = getattr(candidates[0], "content", None) if candidates else None
    parts = getattr(content, "parts", None) or []
    calls: list[ToolCall] = []
    texts: list[str] = []
    for part in parts:
        fn = getattr(part, "function_call", None)
        if fn is not None:
            calls.append(
                ToolCall(
                    name=str(fn.name),
                    args=dict(fn.args or {}),
                    id=str(getattr(fn, "id", "") or ""),
                )
            )
            continue
        if getattr(part, "thought", None):
            continue
        text = getattr(part, "text", None)
        if text:
            texts.append(str(text))
    return ModelTurn(text="".join(texts), tool_calls=calls, raw=content)
