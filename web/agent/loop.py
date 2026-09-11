"""Model-agnostic tool loop. Gemini is an adapter behind HelpModel."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from web.agent.format import plain_reply
from web.agent.prompt import system_prompt
from web.agent.tools import ToolResult, inspect_project, set_cell, set_wall

MAX_TOOL_ROUNDS = 6
MAX_MESSAGES = 16
MAX_MESSAGE_CHARS = 4000
MAX_DESCRIBE_CHARS = 8000


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class ModelTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


@dataclass
class LoopMessage:
    role: str
    content: str
    name: str = ""
    id: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


@dataclass
class AgentReply:
    reply: str
    fields: dict[str, str]


class HelpModel(Protocol):
    def complete(
        self, *, system: str, messages: Sequence[LoopMessage]
    ) -> ModelTurn: ...


def run_turn(
    model: HelpModel,
    *,
    form: dict[str, str],
    messages: Sequence[dict[str, Any]],
    describe: str = "",
    selected: dict[str, Any] | None = None,
) -> AgentReply:
    """Run tools against a copy of the form; return patches for the page."""
    working = dict(form)
    patches: dict[str, str] = {}
    history = _seed_history(working, messages, describe, selected)
    for _ in range(MAX_TOOL_ROUNDS):
        turn = model.complete(system=system_prompt(), messages=history)
        if not turn.tool_calls:
            text = turn.text.strip()
            if patches and "Update roof" not in text:
                text = f"{text} Click Update roof to see the new plan and 3D.".strip()
            return AgentReply(reply=plain_reply(text) or "Done.", fields=patches)
        history.append(
            LoopMessage(
                role="assistant",
                content=turn.text,
                tool_calls=turn.tool_calls,
                raw=turn.raw,
            )
        )
        for call in turn.tool_calls:
            result = dispatch(call.name, call.args, working)
            if result.ok and result.fields:
                working = apply_patches(working, result.fields)
                patches.update(result.fields)
            history.append(
                LoopMessage(
                    role="tool",
                    content=result.note,
                    name=call.name,
                    id=call.id,
                )
            )
    return AgentReply(
        reply=plain_reply(
            "I could not finish that change. Try naming a Wall N and one knob."
        ),
        fields=patches,
    )


def dispatch(name: str, args: dict[str, Any], form: dict[str, str]) -> ToolResult:
    try:
        if name == "inspect_project":
            snapshot = inspect_project(form)
            return ToolResult(ok=True, note=json.dumps(snapshot, default=str))
        if name == "set_wall":
            kwargs = _wall_kwargs(args)
            if "wall" not in kwargs:
                return ToolResult(
                    ok=False,
                    note="set_wall needs a wall number (Wall 1 on the page)",
                )
            return set_wall(form, **kwargs)
        if name == "set_cell":
            return set_cell(form, **_cell_kwargs(args))
    except (TypeError, ValueError) as exc:
        return ToolResult(ok=False, note=str(exc))
    return ToolResult(ok=False, note=f"unknown tool {name}")


def apply_patches(form: dict[str, str], patches: dict[str, str]) -> dict[str, str]:
    out = dict(form)
    for key, value in patches.items():
        if value == "":
            out.pop(key, None)
        else:
            out[key] = value
    return out


def _seed_history(
    form: dict[str, str],
    messages: Sequence[dict[str, Any]],
    describe: str,
    selected: dict[str, Any] | None,
) -> list[LoopMessage]:
    snapshot = inspect_project(form)
    context = {
        "form": snapshot,
        "takeoff": describe[:MAX_DESCRIBE_CHARS],
        "selected": selected or {},
    }
    history = [
        LoopMessage(
            role="user",
            content=(
                "Current project snapshot (form knobs and the takeoff already "
                "on the page). Takeoff is stale after you patch the form.\n"
                + json.dumps(context, default=str)
            ),
        )
    ]
    kept = [
        item
        for item in messages
        if isinstance(item, dict)
        and item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
    ][-MAX_MESSAGES:]
    for item in kept:
        role = str(item["role"])
        history.append(
            LoopMessage(role=role, content=str(item["content"])[:MAX_MESSAGE_CHARS])
        )
    return history


def _wall_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cell = _as_int(args.get("cell"), default=1)
    wall = _as_int(args.get("wall"), default=None)
    if cell is not None:
        out["cell"] = cell
    if wall is not None:
        out["wall"] = wall
    if args.get("type"):
        out["type"] = str(args["type"])
    if args.get("pitch") not in (None, ""):
        out["pitch"] = args["pitch"]
    if args.get("pitch_delta") not in (None, ""):
        out["pitch_delta"] = float(args["pitch_delta"])
    if args.get("knee_height") not in (None, ""):
        out["knee_height"] = float(args["knee_height"])
    if args.get("gambrel_shallow") not in (None, ""):
        out["gambrel_shallow"] = args["gambrel_shallow"]
    if args.get("gambrel_break") not in (None, ""):
        out["gambrel_break"] = float(args["gambrel_break"])
    return out


def _cell_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cell = _as_int(args.get("cell"), default=1)
    if cell is not None:
        out["cell"] = cell
    if args.get("overhang") not in (None, ""):
        out["overhang"] = float(args["overhang"])
    if args.get("eave_height") not in (None, ""):
        out["eave_height"] = float(args["eave_height"])
    return out


def _as_int(value: Any, *, default: int | None) -> int | None:
    if value in (None, ""):
        return default
    return int(value)
