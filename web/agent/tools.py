"""Mutations the help agent may make: the same knobs as the form."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from krovlab import Failure
from krovlab._input import degrees_from_pitch
from krovlab.experimental import (
    PlacedRoof,
    Placement,
    moved_toward_wall,
    reflection_axes,
    roof_from_face_graph,
)

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
                "experimental graph network. Select Standard skeleton when "
                "each wall has a pitch. Roof height is metres above the eaves."
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
                f"Cell {cell} Wall {wall} is now a gable (no face). "
                "Click Update roof."
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
    move_x: float | None = None,
    move_y: float | None = None,
    toward_wall: int | None = None,
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
        move_x=move_x,
        move_y=move_y,
        toward_wall=toward_wall,
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
                "roof height is only on the experimental graph network. "
                "On the skeleton, pitch sets how steep the roof is."
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
_NO_INTERIOR = (
    "There is nothing to place on a single plane or a Failure. " + _UNCHANGED
)
_NO_RIDGE = "This footprint has no ridge. The apex stays. " + _UNCHANGED
_NO_SYMMETRY = (
    "This footprint has no such reflection. The roof stays. " + _UNCHANGED
)
_UNKNOWN_PLACEMENT = "That placement is not on the form. " + _UNCHANGED


def _placement_patch(
    form: dict[str, str],
    *,
    center: bool,
    move_x: float | None,
    move_y: float | None,
    toward_wall: int | None,
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
        or move_x is not None
        or move_y is not None
        or toward_wall is not None
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
                "the experimental graph network. " + _UNCHANGED
            ),
        )
    ring = _ring(form, "outer")
    if len(ring) < 3:
        return ToolResult(ok=False, note=_NO_INTERIOR)
    try:
        graph = _face_graph(form)
    except ValueError:
        return ToolResult(ok=False, note=_NO_INTERIOR)
    built = roof_from_face_graph(ring, graph, placement=Placement())
    if isinstance(built, Failure) or len(built.faces) <= 1:
        return ToolResult(ok=False, note=_NO_INTERIOR)
    axes = reflection_axes(ring)
    style_word = (style or "").strip().lower()
    if style_word:
        mapped = _STYLE_WORDS.get(style_word)
        if mapped is None:
            return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
        style_word = mapped
    offers_ridge = isinstance(built, PlacedRoof) and built.offers_ridge
    if style_word == "ridge" and not offers_ridge:
        return ToolResult(ok=False, note=_NO_RIDGE)
    if symmetric and not axes:
        return ToolResult(ok=False, note=_NO_SYMMETRY)
    if hold is not None and (hold < 0 or hold >= len(axes)):
        return ToolResult(ok=False, note=_NO_SYMMETRY)
    snap_value = _snap_word(snap)
    if snap is not None and snap_value is None:
        return ToolResult(ok=False, note=_UNKNOWN_PLACEMENT)
    dx, dy = _form_offset(form)
    if center:
        dx, dy = 0.0, 0.0
    if move_x is not None or move_y is not None:
        dx += 0.0 if move_x is None else float(move_x)
        dy += 0.0 if move_y is None else float(move_y)
    if toward_wall is not None:
        moved = moved_toward_wall(ring, int(toward_wall), Placement(dx, dy))
        if isinstance(moved, Failure):
            return ToolResult(ok=False, note=f"{moved.reason} {_UNCHANGED}")
        dx, dy = moved.dx, moved.dy
    held: set[int] = set()
    if symmetric:
        held = set(range(len(axes)))
    elif hold is not None:
        held.add(hold)
    if held:
        dx, dy = _project_holds(dx, dy, axes, held)
    patches: dict[str, str] = {
        "offset_x": _fmt_metres(dx),
        "offset_y": _fmt_metres(dy),
    }
    if style_word:
        patches["style"] = style_word
    if snap_value is not None:
        patches["snap"] = snap_value
    at_center = abs(dx) <= 1e-9 and abs(dy) <= 1e-9
    for index, (nx, ny, _c) in enumerate(axes):
        if at_center or index in held:
            patches[f"hold-{index}"] = "on"
        elif abs(nx * dx + ny * dy) > 1e-6:
            patches[f"hold-{index}"] = "off"
    return ToolResult(ok=True, fields=patches, note="placement updated")


def _project_holds(
    dx: float,
    dy: float,
    axes: list[tuple[float, float, float]],
    held: set[int],
) -> tuple[float, float]:
    for index in sorted(held):
        nx, ny, _c = axes[index]
        signed = nx * dx + ny * dy
        dx -= nx * signed
        dy -= ny * signed
    return dx, dy


def _form_offset(form: dict[str, str]) -> tuple[float, float]:
    return _optional_float(form.get("offset_x")), _optional_float(form.get("offset_y"))


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


def _face_graph(form: dict[str, str]) -> list[list[int]] | None:
    groups: list[list[int]] = []
    index = 0
    while f"face-{index}" in form:
        text = form[f"face-{index}"].strip()
        if text:
            groups.append(
                [int(part.strip()) for part in text.split(",") if part.strip()]
            )
        index += 1
    if groups:
        return groups
    from web.examples import load_experimental_examples

    slug = form.get("example") or ""
    example = load_experimental_examples().get(slug)
    if example is None or example.face_graph is None:
        return None
    return [list(group) for group in example.face_graph]


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
                    "shallow": form.get(f"{prefix}gambrel-shallow-{index}")
                    or "",
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
