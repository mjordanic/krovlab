"""Triangulate a footprint with interior points and required edges.

Boundary edges and caller edges (ridges) are constraints. No edge joins
two boundary corners unless it is already a wall. Returns oriented
triangles, or None when the segments cross or leave the footprint.
"""

from __future__ import annotations

import itertools
import math

type Vertex = tuple[float, float]
type Triangle = tuple[int, int, int]


def triangulate(
    ring: list[Vertex],
    interior: list[Vertex],
    constrained: list[tuple[int, int]],
) -> list[Triangle] | None:
    """Triangles over ``ring`` plus ``interior``. Indices are into that sequence."""
    n = len(ring)
    if n < 3 or not interior:
        return None
    points = [*ring, *interior]
    inserted: list[Triangle] = [(i, (i + 1) % n, n) for i in range(n)]
    for index in range(n + 1, len(points)):
        step = _insert(points, inserted, index)
        if step is None:
            return None
        inserted = step
    required = list(constrained)
    for index in range(n):
        required.append((index, (index + 1) % n))
    required = _split_through_points(points, required, n)
    inserted = _split_edges_through_vertices(points, inserted)
    for _ in range(4):
        missing = [
            edge for edge in required if not _has_edge(inserted, edge[0], edge[1])
        ]
        if not missing:
            break
        for edge in missing:
            step = _enforce(inserted, points, edge[0], edge[1])
            if step is None:
                return None
            inserted = _split_edges_through_vertices(points, step)
    if any(not _has_edge(inserted, edge[0], edge[1]) for edge in required):
        return None
    kept = [tri for tri in inserted if _positive_area(points, tri) > 1e-12]
    return kept or None


def _split_edges_through_vertices(
    points: list[Vertex], triangles: list[Triangle]
) -> list[Triangle]:
    """An edge that runs through another vertex is two edges."""
    guard = 0
    while guard < len(points) * len(points):
        guard += 1
        split_at: tuple[int, int, int] | None = None
        seen: set[tuple[int, int]] = set()
        for tri in triangles:
            for start, end in _edges(tri):
                key = (start, end) if start < end else (end, start)
                if key in seen:
                    continue
                seen.add(key)
                for index in range(len(points)):
                    if index in (start, end):
                        continue
                    if _on_segment(points, index, start, end):
                        split_at = (start, end, index)
                        break
                if split_at is not None:
                    break
            if split_at is not None:
                break
        if split_at is None:
            return triangles
        start, end, index = split_at
        nxt: list[Triangle] = []
        for tri in triangles:
            if start in tri and end in tri and index not in tri:
                third = next(vertex for vertex in tri if vertex not in (start, end))
                nxt.append(_orient(points, (start, index, third)))
                nxt.append(_orient(points, (index, end, third)))
            elif not (start in tri and end in tri and index in tri):
                nxt.append(tri)
        triangles = nxt
    return triangles


def _split_through_points(
    points: list[Vertex], edges: list[tuple[int, int]], boundary: int
) -> list[tuple[int, int]]:
    """Break a constraint that runs through an existing point into the pieces."""
    split: list[tuple[int, int]] = []
    for start, end in edges:
        between = [
            index
            for index in range(boundary, len(points))
            if index not in (start, end) and _on_segment(points, index, start, end)
        ]
        between.sort(key=lambda index: _along(points, start, index))
        chain = [start, *between, end]
        split.extend(itertools.pairwise(chain))
    return split


def _on_segment(points: list[Vertex], index: int, start: int, end: int) -> bool:
    ax, ay = points[start]
    bx, by = points[end]
    px, py = points[index]
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > 1e-8:
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    length = (bx - ax) ** 2 + (by - ay) ** 2
    return 1e-8 < dot < length - 1e-8


def _along(points: list[Vertex], start: int, index: int) -> float:
    ax, ay = points[start]
    px, py = points[index]
    return (px - ax) ** 2 + (py - ay) ** 2


def _insert(
    points: list[Vertex], triangles: list[Triangle], index: int
) -> list[Triangle] | None:
    px, py = points[index]
    hit = next(
        (tri for tri in triangles if _in_triangle(points, tri, px, py)),
        None,
    )
    if hit is None:
        return None
    rest = [tri for tri in triangles if tri != hit]
    a, b, c = hit
    return [
        *rest,
        _orient(points, (a, b, index)),
        _orient(points, (b, c, index)),
        _orient(points, (c, a, index)),
    ]


def _in_triangle(points: list[Vertex], tri: Triangle, x: float, y: float) -> bool:
    ax, ay = points[tri[0]]
    bx, by = points[tri[1]]
    cx, cy = points[tri[2]]
    o1 = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    o2 = (cx - bx) * (y - by) - (cy - by) * (x - bx)
    o3 = (ax - cx) * (y - cy) - (ay - cy) * (x - cx)
    return (o1 >= -1e-9 and o2 >= -1e-9 and o3 >= -1e-9) or (
        o1 <= 1e-9 and o2 <= 1e-9 and o3 <= 1e-9
    )


def _enforce(
    triangles: list[Triangle], points: list[Vertex], start: int, end: int
) -> list[Triangle] | None:
    if start == end:
        return None
    for _ in range(len(triangles) * len(triangles) + 8):
        if _has_edge(triangles, start, end):
            return triangles
        crossed = _crossing_edge(triangles, points, start, end)
        if crossed is None:
            return None
        flipped = _flip(triangles, points, crossed[0], crossed[1])
        if flipped is None:
            return None
        triangles = flipped
    return None


def _flip(
    triangles: list[Triangle], points: list[Vertex], a: int, b: int
) -> list[Triangle] | None:
    sharing = [tri for tri in triangles if a in tri and b in tri]
    if len(sharing) != 2:
        return None
    left = next(v for v in sharing[0] if v != a and v != b)
    right = next(v for v in sharing[1] if v != a and v != b)
    if left == right:
        return None
    if (
        _orient_value(points, left, a, right) == 0
        or _orient_value(points, left, b, right) == 0
    ):
        return None
    rest = [tri for tri in triangles if tri not in sharing]
    rest.append(_orient(points, (left, right, a)))
    rest.append(_orient(points, (left, b, right)))
    return rest


def _crossing_edge(
    triangles: list[Triangle], points: list[Vertex], start: int, end: int
) -> tuple[int, int] | None:
    for tri in triangles:
        for a, b in _edges(tri):
            if len({a, b, start, end}) < 4:
                continue
            if _proper_cross(points, start, end, a, b):
                return a, b
    return None


def _has_edge(triangles: list[Triangle], a: int, b: int) -> bool:
    return any(a in tri and b in tri for tri in triangles)


def _edges(tri: Triangle) -> list[tuple[int, int]]:
    a, b, c = tri
    return [(a, b), (b, c), (c, a)]


def _orient(points: list[Vertex], tri: Triangle) -> Triangle:
    a, b, c = tri
    if _orient_value(points, a, b, c) < 0:
        return a, c, b
    return tri


def _orient_value(points: list[Vertex], i: int, j: int, k: int) -> float:
    ax, ay = points[i]
    bx, by = points[j]
    cx, cy = points[k]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _positive_area(points: list[Vertex], tri: Triangle) -> float:
    return abs(_orient_value(points, tri[0], tri[1], tri[2])) / 2


def _proper_cross(points: list[Vertex], a: int, b: int, c: int, d: int) -> bool:
    o1 = _orient_value(points, a, b, c)
    o2 = _orient_value(points, a, b, d)
    o3 = _orient_value(points, c, d, a)
    o4 = _orient_value(points, c, d, b)
    return o1 * o2 < -1e-12 and o3 * o4 < -1e-12


def _inside(x: float, y: float, ring: list[Vertex]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 0.0) + xi):
            inside = not inside
        j = i
    return inside


def point_inside(x: float, y: float, ring: list[Vertex]) -> bool:
    """True when ``(x, y)`` is strictly inside ``ring``."""
    if _on_boundary(x, y, ring):
        return False
    return _inside(x, y, ring)


def _on_boundary(x: float, y: float, ring: list[Vertex]) -> bool:
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length < 1e-18:
            continue
        cross = abs(dx * (y - ay) - dy * (x - ax)) / length
        if cross > 1e-8:
            continue
        dot = (x - ax) * dx + (y - ay) * dy
        if -1e-8 <= dot <= length * length + 1e-8:
            return True
    return False


def segments_cross(a: Vertex, b: Vertex, c: Vertex, d: Vertex) -> bool:
    """True when the open segments intersect."""

    def orient(p: Vertex, q: Vertex, r: Vertex) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return (
        orient(a, b, c) * orient(a, b, d) < -1e-12
        and orient(c, d, a) * orient(c, d, b) < -1e-12
    )
