"""Mutations the help agent may make: the same knobs as the form."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from krovlab import Failure
from krovlab._input import check_footprint, degrees_from_pitch
from krovlab.experimental import reflection_axes

DEFAULT_PITCH = 45.0
DEFAULT_PITCH_DELTA = 5.0
DEFAULT_KNEE_M = 3.0
DEFAULT_GAMBREL_STEEP = 60.0
DEFAULT_GAMBREL_SHALLOW = 30.0
DEFAULT_GAMBREL_BREAK_M = 1.0

WALL_TYPES = frozenset({"hip", "gable", "knee", "gambrel"})


@dataclass(frozen=True)
class ToolResult:
    """A tool's reply: form patches plus a sentence the model can quote."""

    ok: bool
    fields: dict[str, str] = field(default_factory=dict)
    note: str = ""


def inspect_project(form: dict[str, str]) -> dict[str, Any]:
    """Snapshot of cells and walls, numbered as on the page (Wall 1…)."""
    cells: list[dict[str, Any]] = []
    for cell_no in range(1, 33):
        parsed = _cell(form, cell_no)
        if parsed is None:
            break
        cells.append(parsed)
    return {
        "method": _method(form),
        "roof_height_m": form.get("roof_height") or "",
        "cells": cells,
    }


def _method(form: dict[str, str]) -> str:
    if form.get("method") == "experimental":
        return "experimental"
    return "skeleton"


def set_wall(
    form: dict[str, str],
    *,
    cell: int = 1,
    wall: int,
    type: str | None = None,
    pitch: str | float | None = None,
    pitch_delta: float | None = None,
    knee_height: float | None = None,
    gambrel_shallow: str | float | None = None,
    gambrel_break: float | None = None,
) -> ToolResult:
    """Patch one wall's type and pitches. ``wall`` is the page's 1-based number."""
    if _method(form) == "experimental":
        return ToolResult(
            ok=False,
            note=(
                "pitch, gable, knee, and gambrel are not inputs of the "
                "linked roof. Select Standard skeleton when each wall has a "
                "pitch. On the linked roof, choose which wall drains to "
                "which apex or ridge."
            ),
        )
    snapshot = _cell(form, cell)
    if snapshot is None:
        return ToolResult(ok=False, note=f"there is no Cell {cell} on the form")
    walls: list[dict[str, Any]] = snapshot["walls"]
    if wall < 1 or wall > len(walls):
        n = len(walls)
        return ToolResult(
            ok=False,
            note=f"Cell {cell} has walls 1-{n}; there is no Wall {wall}",
        )
    current = walls[wall - 1]
    prefix = _prefix(cell)
    index = wall - 1
    kind = (type or str(current["type"])).strip().lower()
    if kind not in WALL_TYPES:
        return ToolResult(
            ok=False,
            note="wall type must be hip, gable, knee, or gambrel",
        )
    patches: dict[str, str] = {f"{prefix}type-{index}": kind}

    if kind == "gable":
        if pitch_delta is not None:
            return ToolResult(
                ok=False,
                note="a gable is vertical (pitch 90), not an increase",
            )
        patches[f"{prefix}pitch-{index}"] = "90"
        return ToolResult(
            ok=True,
            fields=patches,
            note=(
                f"Cell {cell} Wall {wall} is now a gable (no face). Click Update roof."
            ),
        )

    degrees = _resolve_pitch(
        current_pitch=str(current.get("pitch") or DEFAULT_PITCH),
        pitch=pitch,
        pitch_delta=pitch_delta,
        kind=kind,
    )
    if isinstance(degrees, str):
        return ToolResult(ok=False, note=degrees)
    patches[f"{prefix}pitch-{index}"] = _fmt_degrees(degrees)

    if kind == "knee":
        height = DEFAULT_KNEE_M if knee_height is None else float(knee_height)
        if height <= 0:
            return ToolResult(
                ok=False,
                note="knee height must be metres above the eave, > 0",
            )
        knee = _fmt_metres(height)
        patches[f"{prefix}knee-{index}"] = knee
        pitch_s = patches[f"{prefix}pitch-{index}"]
        return ToolResult(
            ok=True,
            fields=patches,
            note=(
                f"Cell {cell} Wall {wall} is a knee: {knee} m "
                f"then pitch {pitch_s} degrees. Click Update roof."
            ),
        )

    if kind == "gambrel":
        shallow_raw = gambrel_shallow
        if shallow_raw is None:
            shallow_raw = str(current.get("shallow") or DEFAULT_GAMBREL_SHALLOW)
        shallow = degrees_from_pitch(shallow_raw)
        if isinstance(shallow, Failure):
            return ToolResult(ok=False, note=shallow.reason)
        break_h = current.get("break")
        if gambrel_break is not None:
            break_h = gambrel_break
        elif break_h in (None, "", "0"):
            break_h = DEFAULT_GAMBREL_BREAK_M
        try:
            break_val = float(break_h)
        except (TypeError, ValueError):
            return ToolResult(
                ok=False,
                note="break height must be metres above the eave",
            )
        if break_val <= 0:
            return ToolResult(
                ok=False,
                note="a gambrel needs a break height greater than zero",
            )
        converting = (
            type == "gambrel"
            and pitch is None
            and pitch_delta is None
            and degrees == _degrees_or_default(str(current.get("pitch") or ""))
        )
        if converting:
            steep = DEFAULT_GAMBREL_STEEP
            patches[f"{prefix}pitch-{index}"] = _fmt_degrees(steep)
        patches[f"{prefix}gambrel-shallow-{index}"] = _fmt_degrees(shallow)
        patches[f"{prefix}gambrel-break-{index}"] = _fmt_metres(break_val)
        steep_s = patches[f"{prefix}pitch-{index}"]
        shallow_s = patches[f"{prefix}gambrel-shallow-{index}"]
        break_s = patches[f"{prefix}gambrel-break-{index}"]
        return ToolResult(
            ok=True,
            fields=patches,
            note=(
                f"Cell {cell} Wall {wall} is a gambrel: {steep_s} then "
                f"{shallow_s} degrees at {break_s} m. Click Update roof."
            ),
        )

    return ToolResult(
        ok=True,
        fields=patches,
        note=(
            f"Cell {cell} Wall {wall} pitch is {patches[f'{prefix}pitch-{index}']}°. "
            "Click Update roof to see the new plan and 3D."
        ),
    )


def set_cell(
    form: dict[str, str],
    *,
    cell: int = 1,
    overhang: float | None = None,
    eave_height: float | None = None,
    roof_height: float | None = None,
    center: bool = False,
    style: str | None = None,
    snap: str | bool | None = None,
    hold: int | None = None,
    symmetric: bool = False,
    placement: str | None = None,
) -> ToolResult:
    """Patch overhang, eave height, roof height, or experimental placement."""
    snapshot = _cell(form, cell)
    if snapshot is None:
        return ToolResult(ok=False, note=f"there is no Cell {cell} on the form")
    placed = _placement_patch(
        form,
        center=center,
        style=style,
        snap=snap,
        hold=hold,
        symmetric=symmetric,
        placement=placement,
    )
    if placed is not None and not placed.ok:
        return placed
    if (
        overhang is None
        and eave_height is None
        and roof_height is None
        and placed is None
    ):
        return ToolResult(
            ok=False,
            note="set overhang metres, eave_height metres, or roof_height metres",
        )
    if roof_height is not None and _method(form) != "experimental":
        return ToolResult(
            ok=False,
            note=(
                "roof height is only on the linked roof. "
                "On the skeleton, pitch sets how steep the roof is. "
                "On the linked roof the box fills a new or blank row."
            ),
        )
    if roof_height is not None and roof_height <= 0:
        return ToolResult(
            ok=False,
            note="roof height must be metres above the eaves, greater than zero",
        )
    prefix = _prefix(cell)
    patches: dict[str, str] = {}
    bits: list[str] = []
    if placed is not None:
        patches.update(placed.fields)
        bits.append(placed.note)
    if overhang is not None:
        if overhang < 0:
            return ToolResult(
                ok=False,
                note="overhang is metres past the walls, zero or positive",
            )
        patches[f"{prefix}overhang"] = _fmt_metres(overhang)
        if overhang == 0:
            patches[f"{prefix}use_overhang"] = ""
            bits.append("overhang off")
        else:
            patches[f"{prefix}use_overhang"] = "on"
            bits.append(f"overhang {patches[f'{prefix}overhang']} m")
    if eave_height is not None:
        patches[f"{prefix}eave_height"] = _fmt_metres(eave_height)
        if eave_height == 0:
            patches[f"{prefix}use_eave_height"] = ""
            bits.append("eave height at datum")
        else:
            patches[f"{prefix}use_eave_height"] = "on"
            bits.append(f"eave height {patches[f'{prefix}eave_height']} m")
    if roof_height is not None:
        patches["roof_height"] = _fmt_metres(roof_height)
        bits.append(f"roof height {patches['roof_height']} m above the eaves")
    if not bits:
        return placed if placed is not None else ToolResult(ok=False, note="")
    return ToolResult(
        ok=True,
        fields=patches,
        note=f"Cell {cell}: {', '.join(bits)}. Click Update roof.",
    )


_STYLE_WORDS = {
    "apex": "apex",
    "pyramid": "apex",
    "pyramide": "apex",
    "ridge": "ridge",
}
_PLACEMENT_WORDS = {
    "center": "center",
    "place at the center": "center",
    "apex": "apex",
    "pyramid": "apex",
    "pyramide": "apex",
    "ridge": "ridge",
    "make it symmetric": "symmetric",
    "symmetric": "symmetric",
    "snap on": "snap-on",
    "snap off": "snap-off",
}
_UNCHANGED = "The fields stay as they are."
_NO_INTERIOR = "There is nothing to place on a single plane or a Failure. " + _UNCHANGED
_NO_SYMMETRY = "This footprint has no such reflection. The roof stays. " + _UNCHANGED
_UNKNOWN_PLACEMENT = "That placement is not on the form. " + _UNCHANGED


def _placement_patch(
    form: dict[str, str],
    *,
    center: bool,
    style: str | None,
    snap: str | bool | None,
    hold: int | None,
    symmetric: bool,
    placement: str | None,
) -> ToolResult | None:
    sentence = (placement or "").strip().lower()
    if sentence:
        known = _PLACEMENT_WORDS.get(sentence)
        if known is None:
            return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
        if known == "center":
            center = True
        elif known == "symmetric":
            symmetric = True
        elif known == "snap-on":
            snap = "on"
        elif known == "snap-off":
            snap = "off"
        else:
            style = known
    asked = (
        center
        or style not in (None, "")
        or snap is not None
        or hold is not None
        or symmetric
    )
    if not asked:
        return None
    if _method(form) != "experimental":
        return ToolResult(
            ok=False,
            note=(
                "The apex, the ridge, the offset, snap, and symmetry are on "
                "the linked roof. " + _UNCHANGED
            ),
        )
    ring = _ring(form, "outer")
    if len(ring) < 3:
        return ToolResult(ok=False, note=_NO_INTERIOR)
    if isinstance(check_footprint(ring), Failure):
        return ToolResult(ok=False, note=_NO_INTERIOR)
    axes = reflection_axes(ring)
    style_word = (style or "").strip().lower()
    if style_word:
        mapped = _STYLE_WORDS.get(style_word)
        if mapped is None:
            return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
        style_word = mapped
    if symmetric and not axes:
        return ToolResult(ok=False, note=_NO_SYMMETRY)
    if hold is not None and (hold < 0 or hold >= len(axes)):
        return ToolResult(ok=False, note=_NO_SYMMETRY)
    snap_value = _snap_word(snap)
    if snap is not None and snap_value is None:
        return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
    patches: dict[str, str] = {}
    dx, dy = _form_offset(form)
    if center:
        dx, dy = 0.0, 0.0
        patches["apex-0-x"] = "0"
        patches["apex-0-y"] = "0"
    if style_word == "ridge" and "ridge-0-x" not in form:
        patches["ridge-0-x"] = "0"
        patches["ridge-0-y"] = "0"
        patches["ridge-0-direction"] = "0"
        patches["ridge-0-length"] = "2"
        box = (form.get("roof_height") or "").strip()
        if box:
            patches["ridge-0-height"] = box
        patches["selected_interior"] = "ridge-0"
    elif style_word == "apex":
        patches["selected_interior"] = "apex-0"
        patches.setdefault("apex-0-x", _fmt_metres(dx))
        patches.setdefault("apex-0-y", _fmt_metres(dy))
    if snap_value is not None:
        patches["snap"] = snap_value
    if symmetric:
        patches["make_symmetric"] = "1"
        for index in range(len(axes)):
            patches[f"hold-{index}"] = "on"
    elif hold is not None:
        patches[f"hold-{hold}"] = "on"
    if not patches:
        return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
    return ToolResult(ok=True, fields=patches, note="placement updated")


def _form_offset(form: dict[str, str]) -> tuple[float, float]:
    raw_x = form.get("apex-0-x", form.get("offset_x"))
    raw_y = form.get("apex-0-y", form.get("offset_y"))
    return _optional_float(raw_x), _optional_float(raw_y)


def _optional_float(raw: str | None) -> float:
    if raw is None or raw.strip() == "":
        return 0.0
    try:
        number = float(raw)
    except ValueError:
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def _snap_word(snap: str | bool | None) -> str | None:
    if snap is None:
        return None
    if snap in (True, "on", "true", "1", 1):
        return "on"
    if snap in (False, "off", "false", "0", 0):
        return "off"
    return None


def _prefix(cell_number: int) -> str:
    index = cell_number - 1
    return "" if index == 0 else f"cell-{index}-"


def _cell(form: dict[str, str], cell_number: int) -> dict[str, Any] | None:
    prefix = _prefix(cell_number)
    if f"{prefix}outer-x-0" not in form:
        return None
    outer = _ring(form, f"{prefix}outer")
    use_hole = form.get(f"{prefix}use_hole") in {"on", "true", "1"}
    hole = _ring(form, f"{prefix}hole") if use_hole else []
    walls: list[dict[str, Any]] = []
    rings = [outer, hole] if hole else [outer]
    offset = 0
    for ring in rings:
        count = len(ring)
        for i, start in enumerate(ring):
            end = ring[(i + 1) % count]
            index = offset + i
            kind = form.get(f"{prefix}type-{index}") or "hip"
            raw_pitch = form.get(f"{prefix}pitch-{index}")
            walls.append(
                {
                    "wall": index + 1,
                    "from": [start[0], start[1]],
                    "to": [end[0], end[1]],
                    "type": kind,
                    "pitch": raw_pitch or "45",
                    "knee": form.get(f"{prefix}knee-{index}") or "0",
                    "shallow": form.get(f"{prefix}gambrel-shallow-{index}") or "",
                    "break": form.get(f"{prefix}gambrel-break-{index}") or "0",
                }
            )
        offset += count
    if not walls:
        return None
    return {
        "cell": cell_number,
        "overhang_m": form.get(f"{prefix}overhang") or "0",
        "use_overhang": form.get(f"{prefix}use_overhang") in {"on", "true", "1"},
        "eave_height_m": form.get(f"{prefix}eave_height") or "0",
        "use_eave_height": form.get(f"{prefix}use_eave_height") in {"on", "true", "1"},
        "walls": walls,
    }


def _ring(form: dict[str, str], prefix: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    i = 0
    while True:
        raw_x = form.get(f"{prefix}-x-{i}")
        raw_y = form.get(f"{prefix}-y-{i}")
        if raw_x is None or raw_y is None:
            break
        try:
            points.append((float(raw_x), float(raw_y)))
        except (TypeError, ValueError):
            break
        i += 1
    return points


def _resolve_pitch(
    *,
    current_pitch: str,
    pitch: str | float | None,
    pitch_delta: float | None,
    kind: str,
) -> float | str:
    if pitch is not None and pitch_delta is not None:
        return "give either pitch or pitch_delta, not both"
    if pitch is not None:
        parsed = degrees_from_pitch(pitch)
        if isinstance(parsed, Failure):
            return parsed.reason
        if parsed >= 90:
            return (
                "pitch 90 is a gable; set type to gable instead of "
                "increasing into a vertical wall"
            )
        return parsed
    current = degrees_from_pitch(current_pitch)
    if isinstance(current, Failure):
        current = DEFAULT_PITCH
    if current >= 90:
        current = DEFAULT_PITCH
    if pitch_delta is not None:
        nxt = current + float(pitch_delta)
        if not (0.0 < nxt < 90.0):
            return (
                "that pitch would leave (0, 90); a vertical wall is a gable, "
                "not an increase"
            )
        return nxt
    if kind in {"hip", "knee"}:
        return current if current < 90 else DEFAULT_PITCH
    return current if current < 90 else DEFAULT_GAMBREL_STEEP


def _degrees_or_default(raw: str) -> float:
    parsed = degrees_from_pitch(raw) if raw else DEFAULT_PITCH
    if isinstance(parsed, Failure):
        return DEFAULT_PITCH
    return parsed


def _fmt_degrees(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    return f"{value:.4g}"


def _fmt_metres(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    return f"{value:.4g}"
