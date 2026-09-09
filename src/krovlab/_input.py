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


def resolve_wrap_groups(
    value: object, n_edges: int, ring_sizes: list[int]
) -> list[tuple[int, ...]] | Failure:
    """Return wrap groups as consecutive caller-edge chains, or name why not.

    ``None`` or an empty list is no wrap. Each group is two or more
    consecutive edges of one ring. Groups must not overlap.
    """
    if value is None or value == []:
        return []
    if isinstance(value, bool) or not isinstance(value, list):
        return _failure(
            "degenerate",
            "wrap must be a list of groups of consecutive edge indices",
        )
    used: set[int] = set()
    groups: list[tuple[int, ...]] = []
    for raw in value:
        if not isinstance(raw, (list, tuple)) or isinstance(raw, (str, bytes)):
            return _failure(
                "degenerate",
                "wrap must be a list of groups of consecutive edge indices",
            )
        indices: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int):
                return _failure(
                    "degenerate",
                    "wrap groups name edges by integer index",
                )
            if item < 0 or item >= n_edges:
                return _failure(
                    "degenerate",
                    f"wrap edge {item} is not a footprint edge",
                )
            indices.append(item)
        chain = _consecutive_chain(indices, n_edges, ring_sizes)
        if chain is None:
            return _failure(
                "nonconsecutive_wrap",
                "a wrap group must be consecutive edges of one ring",
            )
        if any(edge in used for edge in chain):
            return _failure(
                "degenerate",
                "wrap groups must not share an edge",
            )
        used.update(chain)
        groups.append(chain)
    return groups


def _consecutive_chain(
    indices: list[int], n_edges: int, ring_sizes: list[int]
) -> tuple[int, ...] | None:
    """Order ``indices`` as one circular consecutive chain, or ``None``."""
    if len(indices) < 2 or len(set(indices)) != len(indices):
        return None
    members = set(indices)
    ring_of = _edge_rings(n_edges, ring_sizes)
    rings = {ring_of[i] for i in members}
    if len(rings) != 1:
        return None
    ring_id = next(iter(rings))
    origin = sum(ring_sizes[:ring_id])
    size = ring_sizes[ring_id]
    local = {i - origin for i in members}

    def pred(local_i: int) -> int:
        return (local_i - 1) % size

    starts = [i for i in local if pred(i) not in local]
    if len(local) == size:
        chain_local = list(range(size))
    elif len(starts) != 1:
        return None
    else:
        chain_local = [starts[0]]
        while True:
            nxt = (chain_local[-1] + 1) % size
            if nxt not in local:
                break
            chain_local.append(nxt)
            if len(chain_local) == len(local):
                break
        if len(chain_local) != len(local):
            return None
    return tuple(origin + i for i in chain_local)


def _edge_rings(n_edges: int, ring_sizes: list[int]) -> list[int]:
    rings: list[int] = []
    for ring_id, size in enumerate(ring_sizes):
        rings.extend([ring_id] * size)
    if len(rings) != n_edges:
        return [-1] * n_edges
    return rings


def resolve_gambrels(
    value: object, n_edges: int
) -> list[tuple[float, float, float] | None] | Failure:
    """Return one optional barn break per footprint edge, or name why not.

    ``None`` or omitting the argument is no gambrel. A list must have
    one entry per edge: ``None``, or ``(steep, shallow, break_height)``
    with break height in metres above that cell's eave.
    """
    if value is None:
        return [None] * n_edges
    if isinstance(value, bool) or not isinstance(value, list):
        return _failure(
            "degenerate",
            "gambrel must be a list with one entry per edge",
        )
    if len(value) != n_edges:
        return _failure(
            "degenerate",
            f"gambrel list has {len(value)} values but the footprint has "
            f"{n_edges} edges",
        )
    parsed: list[tuple[float, float, float] | None] = []
    for item in value:
        if item is None:
            parsed.append(None)
            continue
        gambrel = _as_gambrel(item)
        if not isinstance(gambrel, tuple):
            return gambrel
        parsed.append(gambrel)
    return parsed


def _as_gambrel(value: object) -> tuple[float, float, float] | Failure:
    if not isinstance(value, tuple) or len(value) != 3:
        return _failure(
            "degenerate",
            "a gambrel is a steep pitch, a shallow pitch, and a break height in metres",
        )
    steep = degrees_from_pitch(value[0])
    if not isinstance(steep, float):
        return steep
    shallow = degrees_from_pitch(value[1])
    if not isinstance(shallow, float):
        return shallow
    if isinstance(value[2], bool) or not isinstance(value[2], (int, float)):
        return _failure(
            "degenerate",
            "break height must be a finite number of metres above the eave",
        )
    break_height = float(value[2])
    if not math.isfinite(break_height) or break_height <= 0.0:
        return _failure(
            "degenerate",
            "break height must be a finite number of metres above the eave",
        )
    return (steep, shallow, break_height)


def resolve_knee_heights(value: object, n_edges: int) -> list[float] | Failure:
    """Return one knee height in metres per footprint edge, or name why not.

    A scalar is repeated for every edge. ``None`` or omitting the
    argument is zero on every edge. A list must have one value per edge.
    """
    if value is None:
        return [0.0] * n_edges
    if isinstance(value, bool) or not isinstance(value, (int, float, list)):
        return _failure(
            "degenerate",
            "knee height must be a finite number of metres, zero or positive",
        )
    if isinstance(value, list):
        if len(value) != n_edges:
            return _failure(
                "degenerate",
                f"knee height list has {len(value)} values but the footprint "
                f"has {n_edges} edges",
            )
        parsed: list[float] = []
        for item in value:
            height = _as_knee_height(item)
            if not isinstance(height, float):
                return height
            parsed.append(height)
        return parsed
    height = _as_knee_height(value)
    if not isinstance(height, float):
        return height
    return [height] * n_edges


def _as_knee_height(value: object) -> float | Failure:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _failure(
            "degenerate",
            "knee height must be a finite number of metres, zero or positive",
        )
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        return _failure(
            "degenerate",
            "knee height must be a finite number of metres, zero or positive",
        )
    return parsed


def resolve_pitches(pitch: object, n_edges: int) -> list[float] | Failure:
    """Return one pitch in degrees per footprint edge, or name why not.

    A scalar is repeated for every edge. A list must have one value per
    edge; mixed spellings are converted independently.
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
        return parsed
    degrees = degrees_from_pitch(pitch)
    if not isinstance(degrees, float):
        return degrees
    return [degrees] * n_edges


def check_adjacent_parallel_pitches(
    ring: list[tuple[float, float]], pitches: list[float]
) -> Failure | None:
    """Refuse adjacent collinear edges that would move at different speeds.

    Consecutive parallel edges share a supporting line. Differing weights
    then have no intersection for t > 0, so there is no unique skeleton.
    Same-pitch collinear vertices are the extra-eave-point case and pass.
    """
    n = len(ring)
    for i in range(n):
        ax, ay = ring[(i - 1) % n]
        bx, by = ring[i]
        cx, cy = ring[(i + 1) % n]
        dx1, dy1 = bx - ax, by - ay
        dx2, dy2 = cx - bx, cy - by
        len1 = math.hypot(dx1, dy1)
        len2 = math.hypot(dx2, dy2)
        if len1 < 1e-18 or len2 < 1e-18:
            continue
        sin_turn = (dx1 * dy2 - dy1 * dx2) / (len1 * len2)
        if abs(sin_turn) > 1e-9:
            continue
        left, right = (i - 1) % n, i
        if abs(pitches[left] - pitches[right]) <= 1e-9:
            continue
        return _failure(
            "unsupported",
            "adjacent parallel edges of differing pitch have no unique "
            "straight skeleton; give those edges the same pitch or remove "
            "the collinear vertex",
        )
    return None


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
) -> list[list[tuple[float, float]]] | Failure:
    """Return cleaned interior rings, or name why a hole is unusable.

    ``None`` or an empty list means no holes. A hole that touches or
    crosses the outer ring, or another hole, is ``hole_intersects``.
    Either winding is accepted; the caller orients rings for the wavefront.
    """
    if holes is None:
        return []
    if isinstance(holes, (str, bytes)):
        return _failure("degenerate", "holes must be a list of rings")
    if not isinstance(holes, Iterable):
        return _failure("degenerate", "holes must be a list of rings")
    rings_in = list(holes)
    if not rings_in:
        return []
    cleaned: list[list[tuple[float, float]]] = []
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
        for j, other in enumerate(cleaned):
            if _rings_touch_or_cross(other, ring):
                return _failure(
                    "hole_intersects",
                    f"hole {i} touches or crosses hole {j}",
                )
            if _ring_inside(ring, other) or _ring_inside(other, ring):
                return _failure(
                    "degenerate",
                    f"hole {i} overlaps hole {j}",
                )
        cleaned.append(ring)
    return cleaned


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


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> str:
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
        (o1 > _ORIENT_M2 and o2 < -_ORIENT_M2) or (o1 < -_ORIENT_M2 and o2 > _ORIENT_M2)
    ) and (
        (o3 > _ORIENT_M2 and o4 < -_ORIENT_M2) or (o3 < -_ORIENT_M2 and o4 > _ORIENT_M2)
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
