"""Mitered polygon offset applied before the skeleton runs.

The roof of a footprint with overhang is the roof of a larger footprint.
The outer ring expands, holes shrink, and the wavefront never hears the
word overhang.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from krovlab._input import check_footprint, check_holes

if TYPE_CHECKING:
    from krovlab.roof import Failure

_PARALLEL_DEN = 1e-18
"""Dimensionless. Below this, consecutive offset lines are treated as parallel."""


def apply_overhang(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    overhang: float,
) -> (
    tuple[list[tuple[float, float]], list[list[tuple[float, float]]]] | Failure
):
    """Expand ``outer`` and shrink each hole by ``overhang`` metres.

    The result is re-validated with the same boundary checks as raw input,
    so a collapse is a named ``Failure`` rather than a new mechanism.
    """
    from krovlab.roof import Failure

    if overhang == 0.0:
        return outer, holes
    grown = _offset_ring(outer, overhang)
    checked_outer = check_footprint(grown)
    if isinstance(checked_outer, Failure):
        return Failure(
            kind=checked_outer.kind,
            reason=(
                f"overhang of {overhang} m collapsed the footprint: "
                f"{checked_outer.reason}"
            ),
        )
    if _offset_folded(outer, grown, overhang):
        return Failure(
            kind="degenerate",
            reason=(
                f"overhang of {overhang} m collapsed the footprint: "
                "the offset folded through itself"
            ),
        )
    shrunk: list[list[tuple[float, float]]] = []
    for i, hole in enumerate(holes):
        inset = _offset_ring(hole, -overhang)
        if _offset_folded(hole, inset, overhang):
            return Failure(
                kind="degenerate",
                reason=(
                    f"overhang of {overhang} m closed hole {i}: "
                    "the inset folded through itself"
                ),
            )
        shrunk.append(inset)
    checked_holes = check_holes(shrunk, checked_outer)
    if isinstance(checked_holes, Failure):
        return Failure(
            kind=checked_holes.kind,
            reason=(
                f"overhang of {overhang} m closed a hole or made it unusable: "
                f"{checked_holes.reason}"
            ),
        )
    return checked_outer, checked_holes


def _offset_folded(
    original: list[tuple[float, float]],
    offset: list[tuple[float, float]],
    distance: float,
) -> bool:
    """True when some offset vertex is closer to the original than ``|distance|``.

    A valid parallel curve stays exactly ``|distance|`` from the source. Past
    the inradius the miter vertices punch through and land nearer another edge.
    ``check_footprint`` already names a self-intersecting offset; this catches
    the remaining case — a ring that inverted through zero but stayed simple.
    """
    target = abs(distance)
    return any(_distance_to_ring(x, y, original) + 1e-9 < target for x, y in offset)


def _distance_to_ring(
    x: float, y: float, ring: list[tuple[float, float]]
) -> float:
    """Minimum distance from a point to any edge of ``ring``."""
    best = float("inf")
    n = len(ring)
    for i in range(n):
        best = min(best, _point_segment_distance((x, y), ring[i], ring[(i + 1) % n]))
    return best


def _point_segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-24:
        return math.hypot(apx, apy)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    return math.hypot(apx - t * abx, apy - t * aby)


def _offset_ring(
    ring: list[tuple[float, float]], distance: float
) -> list[tuple[float, float]]:
    """Miter-offset a ring. Positive ``distance`` expands the filled region."""
    n = len(ring)
    ccw = _signed_area(ring) > 0.0
    offset: list[tuple[float, float]] = []
    for i in range(n):
        a = ring[(i - 1) % n]
        b = ring[i]
        c = ring[(i + 1) % n]
        offset.append(_miter_vertex(a, b, c, distance, ccw))
    return offset


def _miter_vertex(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    distance: float,
    ccw: bool,
) -> tuple[float, float]:
    """Offset vertex ``b`` by intersecting the offset of ``ab`` and ``bc``.

    Uses ``b + d (n1 + n2) / (1 + n1·n2)`` so shared coordinates on
    axis-aligned edges stay bit-identical rather than drifting through
    a parametric line intersection.
    """
    n1 = _outward_normal(a, b, ccw)
    n2 = _outward_normal(b, c, ccw)
    denom = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
    if abs(denom) < _PARALLEL_DEN:
        return (b[0] + distance * n1[0], b[1] + distance * n1[1])
    return (
        b[0] + distance * (n1[0] + n2[0]) / denom,
        b[1] + distance * (n1[1] + n2[1]) / denom,
    )


def _outward_normal(
    a: tuple[float, float], b: tuple[float, float], ccw: bool
) -> tuple[float, float]:
    """Unit normal pointing out of the filled region of an edge ``a → b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    # Right-hand normal. For a CCW ring the interior is on the left, so
    # outward is right. Clockwise rings flip.
    rx, ry = dy / length, -dx / length
    if ccw:
        return rx, ry
    return -rx, -ry


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area. Positive means counter-clockwise."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return 0.5 * total
