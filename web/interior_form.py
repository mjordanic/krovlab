"""Form rows for the experimental apexes and ridges."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from krovlab.experimental import Apex, Ridge, reflection_axes


@dataclass(frozen=True)
class InteriorRow:
    """One apex or ridge on the card, in metres from the middle."""

    kind: str
    index: int
    x: str
    y: str
    direction: str = "0"
    length: str = "2"
    selected: bool = False
    height: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}-{self.index}"

    @property
    def name(self) -> str:
        label = "Apex" if self.kind == "apex" else "Ridge"
        return f"{label} {self.index + 1}"


def default_rows() -> list[InteriorRow]:
    return [InteriorRow("apex", 0, "0", "0", selected=True)]


def rows_from_form(form: Mapping[str, str]) -> list[InteriorRow]:
    selected = form.get("selected_interior") or "apex-0"
    apexes = _indexed(form, "apex")
    ridges = _indexed(form, "ridge")
    if not apexes and not ridges:
        return default_rows()
    rows: list[InteriorRow] = []
    for index in apexes:
        rows.append(
            InteriorRow(
                "apex",
                index,
                _num(form, f"apex-{index}-x"),
                _num(form, f"apex-{index}-y"),
                selected=selected == f"apex-{index}",
                height=_height_field(form, f"apex-{index}-height"),
            )
        )
    for index in ridges:
        rows.append(
            InteriorRow(
                "ridge",
                index,
                _num(form, f"ridge-{index}-x"),
                _num(form, f"ridge-{index}-y"),
                direction=_num(form, f"ridge-{index}-direction"),
                length=_num(form, f"ridge-{index}-length", default="2"),
                selected=selected == f"ridge-{index}",
                height=_height_field(form, f"ridge-{index}-height"),
            )
        )
    if not any(row.selected for row in rows):
        rows[0] = InteriorRow(
            rows[0].kind,
            rows[0].index,
            rows[0].x,
            rows[0].y,
            rows[0].direction,
            rows[0].length,
            selected=True,
            height=rows[0].height,
        )
    return rows


def apply_interior_buttons(
    form: Mapping[str, str],
    rows: list[InteriorRow],
    ring: Sequence[tuple[float, float]],
) -> tuple[list[InteriorRow], str]:
    """Add, delete, center, or mirror. The second value is a sentence, or empty."""
    box = (form.get("roof_height") or "").strip()
    if form.get("add_apex"):
        return _select(_append_apex(rows, box), f"apex-{_next_index(rows, 'apex')}"), ""
    if form.get("add_ridge"):
        return _select(
            _append_ridge(rows, ring, box), f"ridge-{_next_index(rows, 'ridge')}"
        ), ""
    if form.get("delete_interior"):
        if len(rows) <= 1:
            return rows, "Add another apex or ridge before deleting this one."
        return _delete(rows), ""
    if form.get("place_at_center"):
        rows = [_centered(row) if row.selected else row for row in rows]
    return _with_symmetry(form, rows, ring)


def absolute_interiors(
    rows: Sequence[InteriorRow], middle: tuple[float, float]
) -> tuple[tuple[Apex, ...], tuple[Ridge, ...]]:
    mx, my = middle
    apexes = tuple(
        Apex(mx + float(row.x), my + float(row.y), height=_optional_height(row))
        for row in rows
        if row.kind == "apex"
    )
    ridges = []
    for row in rows:
        if row.kind != "ridge":
            continue
        direction = math.radians(float(row.direction) % 180.0)
        half = float(row.length) / 2.0
        cx, cy = mx + float(row.x), my + float(row.y)
        dx, dy = math.cos(direction) * half, math.sin(direction) * half
        ridges.append(
            Ridge(cx - dx, cy - dy, cx + dx, cy + dy, height=_optional_height(row))
        )
    return apexes, tuple(ridges)


def rows_from_used(
    apexes: Sequence[Apex],
    ridges: Sequence[Ridge],
    middle: tuple[float, float],
    selected: str,
) -> list[InteriorRow]:
    mx, my = middle
    rows: list[InteriorRow] = []
    for index, apex in enumerate(apexes):
        key = f"apex-{index}"
        rows.append(
            InteriorRow(
                "apex",
                index,
                _fmt(apex.x - mx),
                _fmt(apex.y - my),
                selected=key == selected,
                height="" if apex.height is None else _fmt(apex.height),
            )
        )
    for index, ridge in enumerate(ridges):
        cx = (ridge.x0 + ridge.x1) / 2.0
        cy = (ridge.y0 + ridge.y1) / 2.0
        length = math.hypot(ridge.x1 - ridge.x0, ridge.y1 - ridge.y0)
        angle = (
            math.degrees(math.atan2(ridge.y1 - ridge.y0, ridge.x1 - ridge.x0)) % 180.0
        )
        key = f"ridge-{index}"
        rows.append(
            InteriorRow(
                "ridge",
                index,
                _fmt(cx - mx),
                _fmt(cy - my),
                direction=_fmt(angle),
                length=_fmt(length),
                selected=key == selected,
                height="" if ridge.height is None else _fmt(ridge.height),
            )
        )
    if rows and not any(row.selected for row in rows):
        first = rows[0]
        rows[0] = InteriorRow(
            first.kind,
            first.index,
            first.x,
            first.y,
            first.direction,
            first.length,
            True,
            height=first.height,
        )
    return rows


def _append_apex(rows: list[InteriorRow], height: str) -> list[InteriorRow]:
    index = _next_index(rows, "apex")
    return [*rows, InteriorRow("apex", index, "1", "0", height=height)]


def _append_ridge(
    rows: list[InteriorRow], ring: Sequence[tuple[float, float]], height: str
) -> list[InteriorRow]:
    index = _next_index(rows, "ridge")
    direction = _longest_wall_direction(ring)
    return [
        *rows,
        InteriorRow(
            "ridge",
            index,
            "0",
            "0",
            direction=_fmt(direction),
            length="2",
            height=height,
        ),
    ]


def _delete(rows: list[InteriorRow]) -> list[InteriorRow]:
    if len(rows) <= 1:
        return rows
    kept = [row for row in rows if not row.selected]
    if not kept:
        return rows
    return _reindex(kept)


def _centered(row: InteriorRow) -> InteriorRow:
    return InteriorRow(
        row.kind,
        row.index,
        "0",
        "0",
        row.direction,
        row.length,
        True,
        height=row.height,
    )


def _with_symmetry(
    form: Mapping[str, str],
    rows: list[InteriorRow],
    ring: Sequence[tuple[float, float]],
) -> tuple[list[InteriorRow], str]:
    points = [(float(x), float(y)) for x, y in ring]
    axes = reflection_axes(points)
    if form.get("make_symmetric"):
        chosen = list(range(len(axes)))
    else:
        chosen = [
            index
            for index in range(len(axes))
            if form.get(f"hold-{index}") == "on"
            and form.get(f"was-hold-{index}") != "on"
        ]
    if not chosen:
        return rows, ""
    from krovlab._triangulate import point_inside

    extra = list(rows)
    missed = False
    for index in chosen:
        nx, ny, _c = axes[index]
        for row in list(extra):
            dx, dy = float(row.x), float(row.y)
            signed = nx * dx + ny * dy
            image = (dx - 2 * signed * nx, dy - 2 * signed * ny)
            if _has_image(extra, row.kind, image):
                continue
            kind_index = _next_index(extra, row.kind)
            extra.append(
                InteriorRow(
                    row.kind,
                    kind_index,
                    _fmt(image[0]),
                    _fmt(image[1]),
                    _mirrored_direction(row, nx, ny),
                    row.length,
                    height=row.height,
                )
            )
        if not _images_inside(extra, points, point_inside):
            missed = True
            extra = list(rows)
            break
    if missed:
        return rows, "The copies would not fit."
    return extra, ""


def _has_image(
    rows: Sequence[InteriorRow], kind: str, image: tuple[float, float]
) -> bool:
    return any(
        other.kind == kind
        and abs(float(other.x) - image[0]) < 1e-6
        and abs(float(other.y) - image[1]) < 1e-6
        for other in rows
    )


def _images_inside(
    rows: Sequence[InteriorRow],
    ring: list[tuple[float, float]],
    point_inside: Callable[[float, float, list[tuple[float, float]]], bool],
) -> bool:
    from krovlab.experimental import _clearance_midpoint

    middle = _clearance_midpoint(ring)
    if middle is None:
        return False
    mx, my = middle
    return all(
        point_inside(mx + float(row.x), my + float(row.y), ring) for row in rows
    )


def _mirrored_direction(row: InteriorRow, nx: float, ny: float) -> str:
    if row.kind != "ridge":
        return row.direction
    angle = math.radians(float(row.direction) % 180.0)
    vx, vy = math.cos(angle), math.sin(angle)
    signed = nx * vx + ny * vy
    rx, ry = vx - 2 * signed * nx, vy - 2 * signed * ny
    return _fmt(math.degrees(math.atan2(ry, rx)) % 180.0)


def _select(rows: list[InteriorRow], key: str) -> list[InteriorRow]:
    picked = [
        InteriorRow(
            row.kind,
            row.index,
            row.x,
            row.y,
            row.direction,
            row.length,
            row.key == key,
            height=row.height,
        )
        for row in rows
    ]
    if any(row.selected for row in picked):
        return picked
    return _select(rows, rows[-1].key)


def _reindex(rows: list[InteriorRow]) -> list[InteriorRow]:
    apex = ridge = 0
    out: list[InteriorRow] = []
    for row in rows:
        if row.kind == "apex":
            out.append(
                InteriorRow(
                    "apex",
                    apex,
                    row.x,
                    row.y,
                    selected=row.selected,
                    height=row.height,
                )
            )
            apex += 1
        else:
            out.append(
                InteriorRow(
                    "ridge",
                    ridge,
                    row.x,
                    row.y,
                    row.direction,
                    row.length,
                    row.selected,
                    height=row.height,
                )
            )
            ridge += 1
    if out and not any(row.selected for row in out):
        last = out[-1]
        out[-1] = InteriorRow(
            last.kind,
            last.index,
            last.x,
            last.y,
            last.direction,
            last.length,
            True,
            height=last.height,
        )
    return out


def _next_index(rows: Sequence[InteriorRow], kind: str) -> int:
    return sum(1 for row in rows if row.kind == kind)


def _indexed(form: Mapping[str, str], kind: str) -> list[int]:
    found: set[int] = set()
    prefix = f"{kind}-"
    for key in form:
        if not key.startswith(prefix):
            continue
        parts = key.split("-")
        if len(parts) < 3:
            continue
        try:
            found.add(int(parts[1]))
        except ValueError:
            continue
    return sorted(found)


def _optional_height(row: InteriorRow) -> float | None:
    if row.height.strip() == "":
        return None
    return float(row.height)


def _height_field(form: Mapping[str, str], name: str) -> str:
    raw = form.get(name)
    if raw is None or raw.strip() == "":
        return ""
    return _num(form, name)


def _num(form: Mapping[str, str], name: str, default: str = "0") -> str:
    raw = form.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        number = float(raw)
    except ValueError:
        return default
    if not math.isfinite(number):
        return default
    return _fmt(number)


def _fmt(number: float) -> str:
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _longest_wall_direction(ring: Sequence[tuple[float, float]]) -> float:
    best = 0.0
    best_length = -1.0
    count = len(ring)
    for index, (x, y) in enumerate(ring):
        nxt = ring[(index + 1) % count]
        dx, dy = nxt[0] - x, nxt[1] - y
        length = math.hypot(dx, dy)
        if length > best_length:
            best_length = length
            best = math.degrees(math.atan2(dy, dx)) % 180.0
    return best
