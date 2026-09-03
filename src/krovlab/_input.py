"""Input-boundary conversion and validation for :func:`krovlab.roof.roof`.

Pitch spellings become degrees here. Degenerate and self-intersecting
footprints are named here. The skeleton never sees a raw trade convention
or a ring that cannot be roofed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from krovlab.roof import Failure, FailureKind

# A single pitch as the architect writes it: degrees, rise:run, or percent.
type Pitch = float | str | tuple[float, float]


def _failure(kind: FailureKind, reason: str) -> Failure:
    from krovlab.roof import Failure

    return Failure(kind=kind, reason=reason)


def resolve_pitches(pitch: object, n_edges: int) -> float | Failure:
    """Return one uniform pitch in degrees, or name why the list cannot be used.

    A list must have one value per footprint edge. Mixed spellings of the
    same slope are fine. Differing slopes are ``unsupported`` until the
    per-edge-pitch ticket.
    """
    if isinstance(pitch, list):
        if len(pitch) != n_edges:
            return _failure(
                "pitch_count",
                f"pitch list has {len(pitch)} values but the footprint has "
                f"{n_edges} edges",
            )
        parsed: list[float] = []
        for value in pitch:
            degrees = degrees_from_pitch(value)
            if not isinstance(degrees, float):
                return degrees
            parsed.append(degrees)
        first = parsed[0]
        if any(abs(p - first) > 1e-9 for p in parsed[1:]):
            return _failure(
                "unsupported",
                "per-edge pitch is not yet supported; every edge must have "
                "the same pitch",
            )
        return first
    return degrees_from_pitch(pitch)


def degrees_from_pitch(value: object) -> float | Failure:
    """Convert one pitch spelling to degrees, or name why it cannot be read.

    Accepted spellings:

    * a number — already degrees
    * a ``(rise, run)`` pair — ``atan(rise / run)``
    * ``"4:12"`` — the same ratio as a string
    * ``"100%"`` — ``atan(percent / 100)`` (so 100% is 45°)
    """
    if isinstance(value, bool):
        return _failure(
            "invalid_pitch",
            f"pitch {value!r} is not degrees, a rise:run ratio, or a percentage",
        )
    if isinstance(value, (int, float)):
        return _in_range(float(value), value)
    if isinstance(value, tuple) and len(value) == 2:
        return _from_ratio(value[0], value[1], value)
    if isinstance(value, str):
        return _from_string(value)
    return _failure(
        "invalid_pitch",
        f"pitch {value!r} is not degrees, a rise:run ratio, or a percentage",
    )


def _in_range(degrees: float, original: object) -> float | Failure:
    if not math.isfinite(degrees):
        return _failure("invalid_pitch", f"pitch {original!r} is not a finite angle")
    if not (0.0 < degrees <= 90.0):
        return _failure("invalid_pitch", "pitch must satisfy 0 < pitch <= 90")
    return degrees


def _as_finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _from_ratio(rise: object, run: object, original: object) -> float | Failure:
    rise_f = _as_finite_number(rise)
    run_f = _as_finite_number(run)
    if rise_f is None or run_f is None:
        return _failure(
            "invalid_pitch",
            f"pitch {original!r} is not a numeric rise:run ratio",
        )
    if run_f == 0.0:
        return _in_range(90.0 if rise_f > 0.0 else 0.0, original)
    return _in_range(math.degrees(math.atan(rise_f / run_f)), original)


def _from_string(text: str) -> float | Failure:
    stripped = text.strip()
    if stripped.endswith("%"):
        try:
            percent = float(stripped[:-1].strip())
        except ValueError:
            return _failure(
                "invalid_pitch",
                f"pitch {text!r} is not a numeric percentage",
            )
        return _in_range(math.degrees(math.atan(percent / 100.0)), text)
    if ":" in stripped:
        parts = stripped.split(":")
        if len(parts) != 2:
            return _failure("invalid_pitch", f"pitch {text!r} is not a rise:run ratio")
        return _from_ratio(parts[0], parts[1], text)
    try:
        return _in_range(float(stripped), text)
    except ValueError:
        return _failure(
            "invalid_pitch",
            f"pitch {text!r} is not degrees, a rise:run ratio, or a percentage",
        )


_VERTEX_M = 1e-9
"""Metres. Consecutive vertices closer than this are the same point."""

_ORIENT_M2 = 1e-12
"""Square metres. Orientation below this is treated as collinear."""


def check_footprint(footprint: object) -> list[tuple[float, float]] | Failure:
    """Return a closed-ring-stripped copy, or a named reason the ring is unroofable.

    A trailing vertex that repeats the first is a closed-ring spelling and
    is dropped. Any other coincident consecutive pair is degenerate. A
    bowtie or other crossing is ``self_intersection``.
    """
    return _closed_simple_ring(footprint, "footprint")


def check_holes(
    holes: object, outer: list[tuple[float, float]]
) -> Failure | None:
    """Name a hole that touches, crosses, or is otherwise unusable.

    A geometrically valid interior hole is ``unsupported`` until the holes
    ticket roofs it. ``None`` or an empty list means no holes.
    """
    if holes is None:
        return None
    if isinstance(holes, (str, bytes)):
        return _failure("degenerate", "holes must be a list of rings")
    if not isinstance(holes, Iterable):
        return _failure("degenerate", "holes must be a list of rings")
    rings_in = list(holes)
    if not rings_in:
        return None
    for i, hole in enumerate(rings_in):
        ring = _closed_simple_ring(hole, f"hole {i}")
        if not isinstance(ring, list):
            return ring
        if _rings_touch_or_cross(outer, ring):
            return _failure(
                "hole_intersects",
                f"hole {i} touches or crosses the outer ring",
            )
        if not _ring_inside(ring, outer):
            return _failure(
                "degenerate",
                f"hole {i} is not inside the footprint",
            )
    return _failure("unsupported", "holes are not yet supported")


def _closed_simple_ring(
    value: object, name: str
) -> list[tuple[float, float]] | Failure:
    """Parse a ring the way :func:`check_footprint` does, with ``name`` in messages."""
    ring = _as_ring(value, name)
    if not isinstance(ring, list):
        return ring
    if len(ring) >= 2 and _same_point(ring[0], ring[-1]):
        ring = ring[:-1]
    if len(ring) < 3:
        return _failure(
            "degenerate",
            f"{name} must have at least three distinct vertices and enclose area",
        )
    for i, point in enumerate(ring):
        if _same_point(point, ring[(i + 1) % len(ring)]):
            return _failure(
                "degenerate",
                f"{name} has coincident consecutive vertices at index {i}",
            )
    if _self_intersects(ring):
        return _failure("self_intersection", f"{name} is self-intersecting")
    if abs(_signed_area(ring)) <= _ORIENT_M2:
        return _failure(
            "degenerate",
            f"{name} is degenerate: a point, a line, or otherwise no area",
        )
    return ring


def _rings_touch_or_cross(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> bool:
    """True if any edge of ``a`` shares a point with any edge of ``b``."""
    n, m = len(a), len(b)
    for i in range(n):
        p, q = a[i], a[(i + 1) % n]
        for j in range(m):
            r, s = b[j], b[(j + 1) % m]
            if _segments_intersect(p, q, r, s):
                return True
    return False


def _ring_inside(
    inner: list[tuple[float, float]], outer: list[tuple[float, float]]
) -> bool:
    """True if every vertex of ``inner`` is strictly inside ``outer``."""
    return all(_point_in_ring(x, y, outer) == "in" for x, y in inner)


def _point_in_ring(
    x: float, y: float, ring: list[tuple[float, float]]
) -> str:
    """``"in"``, ``"on"``, or ``"out"`` for a closed ring."""
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        if math.hypot(x - ax, y - ay) <= _VERTEX_M:
            return "on"
        if abs(_orient((ax, ay), (bx, by), (x, y))) <= _ORIENT_M2 and _on_segment(
            (ax, ay), (bx, by), (x, y)
        ):
            return "on"
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_at = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_at:
                inside = not inside
        j = i
    return "in" if inside else "out"


def _as_ring(value: object, name: str) -> list[tuple[float, float]] | Failure:
    if value is None or isinstance(value, (str, bytes)):
        return _failure("degenerate", f"{name} must be a list of (x, y) metre pairs")
    if not isinstance(value, Iterable):
        return _failure("degenerate", f"{name} must be a list of (x, y) metre pairs")
    points = list(value)
    ring: list[tuple[float, float]] = []
    for i, point in enumerate(points):
        try:
            x, y = point
            xf, yf = float(x), float(y)
        except (TypeError, ValueError):
            return _failure(
                "degenerate",
                f"{name} vertex {i} is not an (x, y) metre pair",
            )
        if not (math.isfinite(xf) and math.isfinite(yf)):
            return _failure(
                "degenerate",
                f"{name} vertex {i} is not a finite point",
            )
        ring.append((xf, yf))
    return ring


def _same_point(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= _VERTEX_M


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area. Positive means counter-clockwise."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return 0.5 * total


def _self_intersects(ring: list[tuple[float, float]]) -> bool:
    """True when two non-adjacent edges cross or overlap."""
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) % n <= 1 or (i == 0 and j == n - 1):
                continue
            c, d = ring[j], ring[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _orient(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    """True if segments ab and cd share a point other than a clean endpoint miss."""
    o1 = _orient(a, b, c)
    o2 = _orient(a, b, d)
    o3 = _orient(c, d, a)
    o4 = _orient(c, d, b)
    proper = (
        (o1 > _ORIENT_M2 and o2 < -_ORIENT_M2)
        or (o1 < -_ORIENT_M2 and o2 > _ORIENT_M2)
    ) and (
        (o3 > _ORIENT_M2 and o4 < -_ORIENT_M2)
        or (o3 < -_ORIENT_M2 and o4 > _ORIENT_M2)
    )
    if proper:
        return True
    return (
        (abs(o1) <= _ORIENT_M2 and _on_segment(a, b, c))
        or (abs(o2) <= _ORIENT_M2 and _on_segment(a, b, d))
        or (abs(o3) <= _ORIENT_M2 and _on_segment(c, d, a))
        or (abs(o4) <= _ORIENT_M2 and _on_segment(c, d, b))
    )


def _on_segment(
    a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]
) -> bool:
    """True if ``p`` lies on segment ``ab``, including the ends."""
    return (
        min(a[0], b[0]) - _VERTEX_M <= p[0] <= max(a[0], b[0]) + _VERTEX_M
        and min(a[1], b[1]) - _VERTEX_M <= p[1] <= max(a[1], b[1]) + _VERTEX_M
    )
