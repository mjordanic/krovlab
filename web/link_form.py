"""Form fields for which wall and which corner use which apex or ridge."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from krovlab.experimental import Apex, Ridge
from krovlab.links import LinkPlan, Target, allowed_corner_targets, links_from_skeleton
from krovlab.roof import Failure
from web.interior_form import InteriorRow, absolute_interiors, rows_from_used


@dataclass(frozen=True)
class LinkChoice:
    value: str
    label: str
    selected: bool


@dataclass(frozen=True)
class WallLinkView:
    index: int
    options: tuple[LinkChoice, ...]


@dataclass(frozen=True)
class CornerLinkView:
    index: int
    options: tuple[LinkChoice, ...]


@dataclass(frozen=True)
class JoinLinkView:
    index: int
    left: tuple[LinkChoice, ...]
    right: tuple[LinkChoice, ...]


@dataclass(frozen=True)
class LinkViews:
    walls: tuple[WallLinkView, ...]
    corners: tuple[CornerLinkView, ...]
    joins: tuple[JoinLinkView, ...]


def skeleton_rows(
    ring: Sequence[tuple[float, float]], middle: tuple[float, float]
) -> tuple[list[InteriorRow], LinkPlan] | Failure:
    plan = links_from_skeleton([(float(x), float(y)) for x, y in ring])
    if isinstance(plan, Failure):
        return plan
    selected = "ridge-0" if plan.ridges else "apex-0"
    rows = rows_from_used(plan.apexes, plan.ridges, middle, selected)
    apexes, ridges = absolute_interiors(rows, middle)
    corners = tuple(
        _same_physical_end(plan.ridges, ridges, corner) for corner in plan.corners
    )
    joins = tuple(
        (_keep_end(plan.ridges, ridges, left), _keep_end(plan.ridges, ridges, right))
        for left, right in plan.joins
    )
    return rows, LinkPlan(apexes, ridges, plan.walls, corners, joins)


def read_links(
    form: Mapping[str, str],
    wall_count: int,
    *,
    apexes: Sequence[Apex],
    ridges: Sequence[Ridge],
) -> tuple[
    tuple[Target | None, ...],
    tuple[Target | None, ...],
    tuple[tuple[Target, Target], ...],
]:
    walls = tuple(
        _wall_target(form.get(f"wall-{index}-target")) for index in range(wall_count)
    )
    corners: list[Target | None] = []
    for index in range(wall_count):
        choice = _point_target(form.get(f"corner-{index}-target"))
        if choice is not None and choice.kind == "none":
            corners.append(choice)
            continue
        allowed = allowed_corner_targets(
            walls[(index - 1) % wall_count], walls[index]
        )
        corners.append(choice if choice in allowed else None)
    joins: list[tuple[Target, Target]] = []
    index = 0
    while f"join-{index}-a" in form or f"join-{index}-b" in form:
        left = _point_target(form.get(f"join-{index}-a"))
        right = _point_target(form.get(f"join-{index}-b"))
        if (
            left is not None
            and right is not None
            and left.kind != "none"
            and right.kind != "none"
            and _known(left, apexes, ridges)
            and _known(right, apexes, ridges)
            and not _spans_one_ridge(left, right)
        ):
            joins.append((left, right))
        index += 1
    return walls, tuple(corners), tuple(joins)


def shift_deleted(
    walls: Sequence[Target | None],
    corners: Sequence[Target | None],
    joins: Sequence[tuple[Target, Target]],
    kind: str,
    index: int,
) -> tuple[
    tuple[Target | None, ...],
    tuple[Target | None, ...],
    tuple[tuple[Target, Target], ...],
]:
    """Drop links to a deleted apex or ridge and close the gap in the indices."""

    def move(target: Target | None) -> Target | None:
        if target is None or target.kind == "none":
            return target
        if target.kind != kind:
            return target
        if target.index == index:
            return None
        if target.index > index:
            return Target(target.kind, target.index - 1, target.end)
        return target

    kept_joins = []
    for left, right in joins:
        shifted = (move(left), move(right))
        if shifted[0] is None or shifted[1] is None:
            continue
        kept_joins.append((shifted[0], shifted[1]))
    return (
        tuple(move(wall) for wall in walls),
        tuple(move(corner) for corner in corners),
        tuple(kept_joins),
    )


def views_for(
    ring: Sequence[tuple[float, float]],
    walls: Sequence[Target | None],
    corners: Sequence[Target | None],
    joins: Sequence[tuple[Target, Target]],
    rows: Sequence[InteriorRow],
) -> LinkViews:
    names = _names(rows)
    end_names = _end_names(rows)
    wall_views = tuple(
        WallLinkView(index, _wall_options(names, wall))
        for index, wall in enumerate(walls)
    )
    corner_views = []
    count = len(walls)
    for index, corner in enumerate(corners):
        allowed = allowed_corner_targets(
            walls[(index - 1) % count] if count else None,
            walls[index] if count else None,
        )
        corner_views.append(
            CornerLinkView(
                index,
                _corner_options(
                    end_names,
                    allowed,
                    corner,
                    open_label=_corner_blank_label(walls, index, ring),
                    offer_none=_offer_none(ring, walls, index),
                ),
            )
        )
    point_options = _point_options(end_names)
    join_views = [
        JoinLinkView(
            index,
            _with_selected(
                _without_own_other_end(point_options, right), _format_point(left)
            ),
            _with_selected(
                _without_own_other_end(point_options, left), _format_point(right)
            ),
        )
        for index, (left, right) in enumerate(joins)
    ]
    blank = _with_selected(point_options, "")
    join_views.append(JoinLinkView(len(join_views), blank, blank))
    return LinkViews(wall_views, tuple(corner_views), tuple(join_views))


def _keep_end(
    original: Sequence[Ridge], rebuilt: Sequence[Ridge], target: Target
) -> Target:
    moved = _same_physical_end(original, rebuilt, target)
    if moved is None:
        return target
    return moved


def _same_physical_end(
    original: Sequence[Ridge], rebuilt: Sequence[Ridge], target: Target | None
) -> Target | None:
    """Keep a link on the same end after the form folds a ridge into [0, 180)."""
    if (
        target is None
        or target.kind != "ridge"
        or target.end not in (0, 1)
        or target.index >= len(original)
        or target.index >= len(rebuilt)
    ):
        return target
    old = original[target.index]
    point = (old.x0, old.y0) if target.end == 0 else (old.x1, old.y1)
    new = rebuilt[target.index]
    start = math.hypot(point[0] - new.x0, point[1] - new.y0)
    end = math.hypot(point[0] - new.x1, point[1] - new.y1)
    return Target("ridge", target.index, 0 if start <= end else 1)


def _wall_target(raw: str | None) -> Target | None:
    if raw is None or raw.strip() == "":
        return None
    text = raw.strip()
    if text.startswith("apex-"):
        return Target("apex", int(text.removeprefix("apex-")))
    if text.startswith("ridge-"):
        return Target("ridge", int(text.removeprefix("ridge-")))
    return None


def _point_target(raw: str | None) -> Target | None:
    if raw is None or raw.strip() == "":
        return None
    text = raw.strip()
    if text == "none":
        return Target("none")
    if text.startswith("apex-"):
        return Target("apex", int(text.removeprefix("apex-")))
    if "-end-" not in text or not text.startswith("ridge-"):
        return None
    ridge, end = text.removeprefix("ridge-").split("-end-")
    return Target("ridge", int(ridge), int(end))


def _known(target: Target, apexes: Sequence[Apex], ridges: Sequence[Ridge]) -> bool:
    if target.kind == "apex":
        return 0 <= target.index < len(apexes)
    if target.kind == "ridge":
        return 0 <= target.index < len(ridges) and target.end in (0, 1)
    return False


def _names(rows: Sequence[InteriorRow]) -> dict[str, str]:
    return {row.key: row.name for row in rows}


def _end_names(rows: Sequence[InteriorRow]) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        if row.kind == "apex":
            names[row.key] = row.name
        else:
            names[f"{row.key}-end-0"] = f"{row.name} start"
            names[f"{row.key}-end-1"] = f"{row.name} end"
    return names


def _wall_options(
    names: dict[str, str], selected: Target | None
) -> tuple[LinkChoice, ...]:
    current = "" if selected is None else _format_wall(selected)
    options = [LinkChoice("", "Open", current == "")]
    for key, label in names.items():
        options.append(LinkChoice(key, label, key == current))
    return tuple(options)


def _corner_options(
    names: dict[str, str],
    allowed: tuple[Target, ...],
    selected: Target | None,
    *,
    open_label: str,
    offer_none: bool,
) -> tuple[LinkChoice, ...]:
    current = "" if selected is None else _format_point(selected)
    options = [LinkChoice("", open_label, current == "")]
    if offer_none:
        options.append(LinkChoice("none", "No line", current == "none"))
    for target in allowed:
        value = _format_point(target)
        label = names.get(value, value)
        options.append(LinkChoice(value, label, value == current))
    return tuple(options)


def _spans_one_ridge(left: Target, right: Target) -> bool:
    return (
        left.kind == "ridge"
        and right.kind == "ridge"
        and left.index == right.index
        and left.end in (0, 1)
        and right.end in (0, 1)
        and left.end != right.end
    )


def _without_own_other_end(
    options: tuple[LinkChoice, ...], other: Target
) -> tuple[LinkChoice, ...]:
    if other.kind != "ridge" or other.end not in (0, 1):
        return options
    banned = f"ridge-{other.index}-end-{1 - other.end}"
    return tuple(option for option in options if option.value != banned)


def _point_options(names: dict[str, str]) -> tuple[LinkChoice, ...]:
    return tuple(LinkChoice(value, label, False) for value, label in names.items())


def _with_selected(
    options: tuple[LinkChoice, ...], selected: str
) -> tuple[LinkChoice, ...]:
    blank = (LinkChoice("", "Open", selected == ""),)
    rest = tuple(
        LinkChoice(option.value, option.label, option.value == selected)
        for option in options
    )
    return blank + rest


def _format_wall(target: Target) -> str:
    return f"{target.kind}-{target.index}"


def _format_point(target: Target | None) -> str:
    if target is None:
        return ""
    if target.kind == "none":
        return "none"
    if target.kind == "apex":
        return f"apex-{target.index}"
    return f"ridge-{target.index}-end-{target.end}"


def _corner_blank_label(
    walls: Sequence[Target | None], index: int, ring: Sequence[tuple[float, float]]
) -> str:
    del ring
    count = len(walls)
    if count == 0:
        return "Open"
    left = walls[(index - 1) % count]
    right = walls[index]
    if left is not None and right is not None and _same(left, right):
        return "Automatic"
    return "Open"


def _offer_none(
    ring: Sequence[tuple[float, float]], walls: Sequence[Target | None], index: int
) -> bool:
    count = len(walls)
    if count == 0 or index >= len(ring):
        return False
    left = walls[(index - 1) % count]
    right = walls[index]
    return (
        left is not None
        and right is not None
        and _same(left, right)
        and _collinear(ring, index)
    )


def _same(left: Target, right: Target) -> bool:
    return left.kind == right.kind and left.index == right.index


def _collinear(ring: Sequence[tuple[float, float]], index: int) -> bool:
    count = len(ring)
    ax, ay = ring[(index - 1) % count]
    bx, by = ring[index]
    cx, cy = ring[(index + 1) % count]
    cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    scale = math.hypot(bx - ax, by - ay) * math.hypot(cx - bx, cy - by)
    return abs(cross) <= 1e-6 * max(scale, 1.0)
