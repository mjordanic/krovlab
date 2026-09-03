"""Felkel-Obdrzalek wavefront: edge events over a circular LAV.

Only edge events are handled (convex footprints). Split events are out of
scope here.

Tie-breaking (simultaneous and co-located events)
-------------------------------------------------
The event queue is a min-heap ordered by:

1. time (the offset of the three supporting lines divided by weight; this
   time *is* the node's height; there is no later lifting step)
2. vanishing original-edge index, lower first
3. insertion sequence, so the heap never falls through to object identity

When an event point lies within ``COLLOCATION_M`` metres of an existing
skeleton node at the same height, that node is reused. A square's four
coincident edge events therefore share one apex rather than four
overlapping nodes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from heapq import heappop, heappush

COLLOCATION_M = 1e-9
"""Plan/height tolerance in metres for merging co-located skeleton nodes."""


@dataclass
class _Line:
    """Infinite supporting line of a footprint edge, in Hessian form."""

    nx: float
    """X of the unit inward normal (interior to the left of a CCW edge)."""

    ny: float
    """Y of the unit inward normal."""

    c: float
    """Offset of the original line: ``n · x = c`` for every point on it."""


@dataclass
class _Vertex:
    """One vertex of the shrinking wavefront (the LAV)."""

    x: float
    y: float
    left_edge: int
    """Index of the original edge whose supporting line is on the left."""

    right_edge: int
    """Index of the original edge whose supporting line is on the right."""

    source_node: int
    """Skeleton node this vertex is tracing an arc from."""

    valid: bool = True
    """False once this vertex has been consumed by an edge event."""

    prev: _Vertex = field(init=False, repr=False)
    next: _Vertex = field(init=False, repr=False)


@dataclass(frozen=True)
class RawSkeleton:
    """Straight skeleton as a graph, before roof quantities are attached.

    ``nodes`` are ``(x, y, height)``. ``arcs`` are
    ``(start, end, face_a, face_b)`` — each internal arc bounds two faces
    identified by original-edge index. Eaves are not included; the public
    layer adds them from the footprint.
    """

    nodes: tuple[tuple[float, float, float], ...]
    arcs: tuple[tuple[int, int, int, int], ...]


def skeleton(ring: list[tuple[float, float]], weights: list[float]) -> RawSkeleton:
    """Grow the straight skeleton of a counter-clockwise convex ring.

    ``weights[i]`` is the plan speed of edge ``i``. Event time equals
    height because the wavefront rises at unit rate as it moves in.
    """
    n = len(ring)
    lines = [_supporting_line(ring[i], ring[(i + 1) % n]) for i in range(n)]
    nodes: list[tuple[float, float, float]] = [(p[0], p[1], 0.0) for p in ring]
    arcs: list[tuple[int, int, int, int]] = []

    verts = [_Vertex(p[0], p[1], (i - 1) % n, i, i) for i, p in enumerate(ring)]
    for i, v in enumerate(verts):
        v.prev = verts[(i - 1) % n]
        v.next = verts[(i + 1) % n]

    heap: list[tuple[float, int, int, _Vertex]] = []
    seq = 0

    def push(vertex: _Vertex) -> None:
        nonlocal seq
        event = _edge_event(vertex, lines, weights)
        if event is None:
            return
        t, edge_index, _px, _py = event
        seq += 1
        heappush(heap, (t, edge_index, seq, vertex))

    for v in verts:
        push(v)

    while heap:
        t, _edge_index, _, va = heappop(heap)
        if not va.valid:
            continue
        vb = va.next
        if not vb.valid:
            continue
        event = _edge_event(va, lines, weights)
        if event is None:
            continue
        t2, edge_index, px, py = event
        # Stale heap entry: this vertex's next neighbour changed since push.
        if abs(t2 - t) > 1e-9 or edge_index != _edge_index:
            continue

        node_idx = _find_or_add_node(nodes, px, py, t2)
        _add_arc(arcs, nodes, va.source_node, node_idx, va.left_edge, va.right_edge)
        _add_arc(arcs, nodes, vb.source_node, node_idx, vb.left_edge, vb.right_edge)

        va.valid = False
        vb.valid = False

        nv = _Vertex(px, py, va.left_edge, vb.right_edge, node_idx)
        nv.prev = va.prev
        nv.next = vb.next
        nv.prev.next = nv
        nv.next.prev = nv

        if nv.next is nv:
            break
        # Two vertices left: they either coincide (triangle apex — the
        # remaining hip is the arc between their sources) or sit at the
        # two ends of a ridge (rectangle).
        if nv.next.next is nv:
            other = nv.next
            _add_arc(
                arcs,
                nodes,
                nv.source_node,
                other.source_node,
                nv.left_edge,
                nv.right_edge,
            )
            nv.valid = False
            other.valid = False
            break

        push(nv.prev)
        push(nv)

    return RawSkeleton(nodes=tuple(nodes), arcs=tuple(arcs))


def _supporting_line(a: tuple[float, float], b: tuple[float, float]) -> _Line:
    """Inward-oriented supporting line of edge ``a -> b`` on a CCW ring."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    nx = -dy / length
    ny = dx / length
    return _Line(nx=nx, ny=ny, c=nx * a[0] + ny * a[1])


def _edge_event(
    va: _Vertex, lines: list[_Line], weights: list[float]
) -> tuple[float, int, float, float] | None:
    """Time and point at which the wavefront edge between ``va`` and its next vanishes.

    Returns ``(time, vanishing_edge_index, x, y)``, or ``None`` if the
    three supporting lines never meet in the future.
    """
    vb = va.next
    i = va.right_edge
    solved = _offset_meet(
        lines[va.left_edge],
        weights[va.left_edge],
        lines[i],
        weights[i],
        lines[vb.right_edge],
        weights[vb.right_edge],
    )
    if solved is None:
        return None
    px, py, t = solved
    if t < -1e-12:
        return None
    if t < 0.0:
        t = 0.0
    return t, i, px, py


def _offset_meet(
    l1: _Line,
    w1: float,
    l2: _Line,
    w2: float,
    l3: _Line,
    w3: float,
) -> tuple[float, float, float] | None:
    """Intersection of three inward-offset supporting lines.

    Each line moves inward at its weight, so the point ``p`` at time ``t``
    satisfies ``n_i · p - w_i t = c_i``. The resulting ``t`` is height.
    """
    return _solve3(
        l1.nx,
        l1.ny,
        -w1,
        l1.c,
        l2.nx,
        l2.ny,
        -w2,
        l2.c,
        l3.nx,
        l3.ny,
        -w3,
        l3.c,
    )


def _solve3(
    a11: float,
    a12: float,
    a13: float,
    b1: float,
    a21: float,
    a22: float,
    a23: float,
    b2: float,
    a31: float,
    a32: float,
    a33: float,
    b3: float,
) -> tuple[float, float, float] | None:
    """Solve a 3x3 linear system by Cramer's rule. ``None`` if singular."""
    det = (
        a11 * (a22 * a33 - a23 * a32)
        - a12 * (a21 * a33 - a23 * a31)
        + a13 * (a21 * a32 - a22 * a31)
    )
    if abs(det) < 1e-18:
        return None
    dx = (
        b1 * (a22 * a33 - a23 * a32)
        - a12 * (b2 * a33 - a23 * b3)
        + a13 * (b2 * a32 - a22 * b3)
    )
    dy = (
        a11 * (b2 * a33 - a23 * b3)
        - b1 * (a21 * a33 - a23 * a31)
        + a13 * (a21 * b3 - b2 * a31)
    )
    dt = (
        a11 * (a22 * b3 - b2 * a32)
        - a12 * (a21 * b3 - b2 * a31)
        + b1 * (a21 * a32 - a22 * a31)
    )
    return dx / det, dy / det, dt / det


def _find_or_add_node(
    nodes: list[tuple[float, float, float]], x: float, y: float, height: float
) -> int:
    """Return the index of a co-located node, or append and return the new index."""
    for i, (nx, ny, _h) in enumerate(nodes):
        if (
            math.hypot(nx - x, ny - y) < COLLOCATION_M
            and abs(_h - height) < COLLOCATION_M
        ):
            return i
    nodes.append((x, y, height))
    return len(nodes) - 1


def _add_arc(
    arcs: list[tuple[int, int, int, int]],
    nodes: list[tuple[float, float, float]],
    a: int,
    b: int,
    face_a: int,
    face_b: int,
) -> None:
    """Append a skeleton arc unless it is zero-length (a merged apex)."""
    if a == b:
        return
    ax, ay, az = nodes[a]
    bx, by, bz = nodes[b]
    if math.hypot(ax - bx, ay - by, az - bz) < COLLOCATION_M:
        return
    arcs.append((a, b, face_a, face_b))
