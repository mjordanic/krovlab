"""Felkel-Obdrzalek wavefront: edge and split events over circular LAVs.

Edge events shrink a wavefront edge to a point. Split events fire when a
reflex vertex reaches an opposite edge and the shrinking polygon divides
in two. Convex footprints only ever see edge events.

Tie-breaking (simultaneous and co-located events)
-------------------------------------------------
The event queue is a min-heap ordered by:

1. time (the offset of the three supporting lines divided by weight; this
   time *is* the node's height; there is no later lifting step)
2. kind rank: split events before edge events, so a reflex vertex
   hitting an opposite edge is processed before a vanishing edge at
   the same instant (parallel-arm collapses otherwise swallow the split).
   Delayed-edge activations rank after edge events, so a knee whose
   delay equals a collapse is a gablet (no remaining hip)
3. event point, plan x then y, so numbering of the ring cannot change
   which of two co-located events goes first
4. tracing vertex's birth coordinates, x then y
5. insertion sequence, so the heap never falls through to object identity

When an event point lies within ``COLLOCATION_M`` metres of an existing
skeleton node at the same height, that node is reused. A square's four
coincident edge events therefore share one apex rather than four
overlapping nodes. Symmetric footprints whose split events collide at one
point reuse that node the same way.

Adjacent parallel edges of differing weight
-------------------------------------------
Consecutive edges that share a supporting line (a collinear vertex) have
no unique weighted skeleton if their weights differ: the two offset
lines stay parallel and never meet. The public entry point refuses that
input rather than picking an arbitrary answer. Same-weight collinear
vertices are kept — they are one eave with an extra point. The vertex
moves along the inward normal (Biedl: the 180° bisector is
perpendicular to the wall) and may split against an opposite edge.

Holes
-----
Each hole is a second LAV, oriented clockwise so the roofed region stays
on the left. A reflex vertex hitting an edge of a *different* LAV merges
the two wavefronts (the mirror of a split). The pointer surgery is the
same as a split; only the cycle count goes 2→1 instead of 1→2.

Gables
------
``weight = 0`` is a vertical face: that edge does not move. Neighbouring
faces close over it. Leftover wavefront vertices then mean the roof
could not close (every edge gabled, or enough that nothing remains to
meet), so ``complete`` is false. The public layer omits the gabled face
and classifies the wall-meeting arcs as verges.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import pairwise

COLLOCATION_M = 1e-9
"""Plan/height tolerance in metres for merging co-located skeleton nodes."""

_EVENT_SPLIT = 0
_EVENT_EDGE = 1
_EVENT_ACTIVATE = 2
_ALONG_TOL = 1e-5
_DIST_TOL_M = 1e-4
_PARALLEL_DIST_M = 5e-3
"""Metres. Looser meet-test when a vertex's supports have just coincided."""
_REGION_TOL = 1e-12


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

    birth: float = 0.0
    """Time (height) at which this vertex was created."""

    valid: bool = True
    """False once this vertex has been consumed by an event."""

    prev: _Vertex = field(init=False, repr=False)
    next: _Vertex = field(init=False, repr=False)


@dataclass(frozen=True)
class RawEvent:
    """One processed wavefront event, before caller edge indices are mapped.

    ``edges`` are original-ring indices. For an edge event: left support,
    the vanishing edge, right support. For a split event: the reflex
    vertex's left support, its right support, and the opposite edge.
    ``vertices`` are skeleton-node indices involved: the sources that
    traced in, then the node created (or reused).
    """

    kind: str
    time: float
    edges: tuple[int, ...]
    vertices: tuple[int, ...]


@dataclass(frozen=True)
class RawSkeleton:
    """Straight skeleton as a graph, before roof quantities are attached.

    ``nodes`` are ``(x, y, height)``. ``arcs`` are
    ``(start, end, face_a, face_b)`` — each internal arc bounds two faces
    identified by original-edge index. Eaves are not included; the public
    layer adds them from the footprint. ``events`` is the sequence the
    wavefront actually processed, in order. ``complete`` is false when
    the wavefront stopped with leftover vertices.
    """

    nodes: tuple[tuple[float, float, float], ...]
    arcs: tuple[tuple[int, int, int, int], ...]
    events: tuple[RawEvent, ...]
    complete: bool = True
    activations: tuple[tuple[int, int, int], ...] = ()
    """Knee-eave endpoints: ``(edge_index, start_node, end_node)``.

    An edge with a delay that vanished before the delay expired is
    absent — the wall stayed vertical and there is no remaining hip.
    """


def skeleton(
    rings: list[list[tuple[float, float]]],
    weights: list[float],
    delays: list[float] | None = None,
) -> RawSkeleton:
    """Grow the straight skeleton of one or more oriented rings.

    The first ring is the outer footprint, counter-clockwise. Further
    rings are holes, clockwise, so the roofed region stays to the left
    of every edge. ``weights[i]`` is the plan speed of concatenated
    edge ``i``. Each ring is its own LAV; a reflex vertex hitting an
    edge of another LAV merges the two wavefronts — the same pointer
    surgery as a split, 2→1 cycles instead of 1→2.

    Event time equals height because the wavefront rises at unit rate
    as it moves in. ``delays[i]`` is an additive wait in metres (knee
    height) before edge ``i`` starts moving; omitted delays are zero.
    """
    pts: list[tuple[float, float]] = []
    next_idx: list[int] = []
    for ring in rings:
        origin = len(pts)
        m = len(ring)
        pts.extend(ring)
        next_idx.extend(origin + (j + 1) % m for j in range(m))
    n = len(pts)
    if delays is None:
        delays = [0.0] * n
    prev_of = [0] * n
    for i, nxt in enumerate(next_idx):
        prev_of[nxt] = i
    lines = [_supporting_line(pts[i], pts[next_idx[i]]) for i in range(n)]
    nodes: list[tuple[float, float, float]] = [(p[0], p[1], 0.0) for p in pts]
    arcs: list[tuple[int, int, int, int]] = []
    events: list[RawEvent] = []
    activations: list[tuple[int, int, int]] = []
    bisectors = _original_bisectors(prev_of, lines, weights)

    verts = [
        _Vertex(p[0], p[1], prev_of[i], i, i, birth=0.0) for i, p in enumerate(pts)
    ]
    for i, v in enumerate(verts):
        v.prev = verts[prev_of[i]]
        v.next = verts[next_idx[i]]

    heap: list[tuple[float, int, float, float, float, float, int, _Vertex, int]] = []
    seq = 0

    def push(
        kind_rank: int,
        t: float,
        px: float,
        py: float,
        vertex: _Vertex,
        edge_index: int,
    ) -> None:
        nonlocal seq
        seq += 1
        heappush(
            heap,
            (t, kind_rank, px, py, vertex.x, vertex.y, seq, vertex, edge_index),
        )

    def push_edge(vertex: _Vertex) -> None:
        event = _edge_event(vertex, lines, weights, delays)
        if event is None:
            return
        t, edge_index, px, py = event
        if t + 1e-12 < vertex.birth:
            return
        push(_EVENT_EDGE, t, px, py, vertex, edge_index)

    def push_splits(vertex: _Vertex) -> None:
        if not (
            _is_reflex(vertex, lines)
            or _is_straight_same_weight(vertex, lines, weights)
        ):
            return
        for opp in range(n):
            cand = _split_candidate(
                vertex, opp, lines, weights, delays, pts, next_idx, bisectors
            )
            if cand is None:
                continue
            t, px, py = cand
            push(_EVENT_SPLIT, t, px, py, vertex, opp)

    def push_all(vertex: _Vertex) -> None:
        push_edge(vertex)
        push_splits(vertex)

    def finish_if_small(vertex: _Vertex) -> bool:
        """Collapse a 1- or 2-vertex LAV. True if the vertex was consumed."""
        if not vertex.valid:
            return True
        if vertex.next is vertex:
            vertex.valid = False
            return True
        if vertex.next.next is vertex:
            other = vertex.next
            _add_arc(
                arcs,
                nodes,
                vertex.source_node,
                other.source_node,
                vertex.left_edge,
                vertex.right_edge,
            )
            vertex.valid = False
            other.valid = False
            return True
        return False

    def activate_edge(edge_i: int, t: float) -> None:
        """Record the knee-eave nodes when a delayed edge starts moving."""
        va: _Vertex | None = None
        for vertex in verts:
            if vertex.valid and vertex.right_edge == edge_i:
                va = vertex
                break
        if va is None or not va.next.valid:
            return
        vb = va.next
        ends: list[int] = []
        for vertex in (va, vb):
            pos = _position_at(vertex, t, lines, weights, delays)
            if pos is None:
                return
            node_idx = _find_or_add_node(nodes, pos[0], pos[1], t)
            _add_arc(
                arcs,
                nodes,
                vertex.source_node,
                node_idx,
                vertex.left_edge,
                vertex.right_edge,
            )
            vertex.source_node = node_idx
            vertex.x, vertex.y = pos
            vertex.birth = t
            ends.append(node_idx)
        activations.append((edge_i, ends[0], ends[1]))

    for v in verts:
        push_all(v)
    for i, delay in enumerate(delays):
        if delay > 0.0:
            host = next(v for v in verts if v.right_edge == i)
            push(_EVENT_ACTIVATE, delay, 0.0, 0.0, host, i)

    max_events = max(n * n * 8, 32)
    processed = 0
    seen: set[tuple[float, float, float, tuple[int, ...]]] = set()

    def already_seen(t_ev: float, px: float, py: float, *edge_ids: int) -> bool:
        key = (round(t_ev, 8), round(px, 8), round(py, 8), tuple(sorted(edge_ids)))
        if key in seen:
            return True
        seen.add(key)
        return False

    while heap:
        t, kind_rank, _px, _py, _vx, _vy, _, va, edge_index = heappop(heap)
        if kind_rank == _EVENT_ACTIVATE:
            activate_edge(edge_index, t)
            continue
        if not va.valid:
            continue
        processed += 1
        if processed > max_events:
            return RawSkeleton(
                nodes=tuple(nodes),
                arcs=tuple(arcs),
                events=tuple(events),
                complete=False,
                activations=tuple(activations),
            )

        if kind_rank == _EVENT_EDGE:
            vb = va.next
            if not vb.valid:
                continue
            event = _edge_event(va, lines, weights, delays)
            if event is None:
                continue
            t2, vanishing, px, py = event
            if abs(t2 - t) > 1e-9 or vanishing != edge_index:
                continue
            if not _vertices_meet(va, vb, px, py, t2, lines, weights, delays):
                continue
            if already_seen(t2, px, py, va.left_edge, va.right_edge, vb.right_edge):
                continue

            node_idx = _find_or_add_node(nodes, px, py, t2)
            events.append(
                RawEvent(
                    kind="edge",
                    time=t2,
                    edges=(va.left_edge, va.right_edge, vb.right_edge),
                    vertices=(va.source_node, vb.source_node, node_idx),
                )
            )
            _add_arc(arcs, nodes, va.source_node, node_idx, va.left_edge, va.right_edge)
            _add_arc(arcs, nodes, vb.source_node, node_idx, vb.left_edge, vb.right_edge)

            va.valid = False
            vb.valid = False

            nv = _Vertex(px, py, va.left_edge, vb.right_edge, node_idx, birth=t2)
            nv.prev = va.prev
            nv.next = vb.next
            nv.prev.next = nv
            nv.next.prev = nv
            verts.append(nv)

            if not finish_if_small(nv):
                push_edge(nv.prev)
                push_all(nv)
            continue

        cand = _split_candidate(
            va, edge_index, lines, weights, delays, pts, next_idx, bisectors
        )
        if cand is None:
            continue
        t2, px, py = cand
        if abs(t2 - t) > 1e-9:
            continue
        found = _find_opposite(edge_index, px, py, t2, verts, lines, weights, delays)
        if found is None:
            continue
        vo, vp = found
        if vo is va or vp is va:
            continue
        if already_seen(t2, px, py, va.left_edge, va.right_edge, edge_index):
            continue

        node_idx = _find_or_add_node(nodes, px, py, t2)
        events.append(
            RawEvent(
                kind="split",
                time=t2,
                edges=(va.left_edge, va.right_edge, edge_index),
                vertices=(va.source_node, vo.source_node, vp.source_node, node_idx),
            )
        )
        _add_arc(arcs, nodes, va.source_node, node_idx, va.left_edge, va.right_edge)

        v1 = _Vertex(px, py, va.left_edge, edge_index, node_idx, birth=t2)
        v2 = _Vertex(px, py, edge_index, va.right_edge, node_idx, birth=t2)

        v1.prev = va.prev
        v1.next = vp
        va.prev.next = v1
        vp.prev = v1

        v2.prev = vo
        v2.next = va.next
        va.next.prev = v2
        vo.next = v2

        va.valid = False
        verts.append(v1)
        verts.append(v2)

        if not finish_if_small(v1):
            push_edge(v1.prev)
            push_all(v1)
        if v2.valid and not finish_if_small(v2):
            push_edge(v2.prev)
            push_all(v2)

    drained = True
    while drained:
        drained = False
        for v in verts:
            if v.valid and finish_if_small(v):
                drained = True
                break

    leftover = any(v.valid for v in verts)
    has_gable = any(w <= 0.0 for w in weights)
    complete = not leftover if (len(rings) > 1 or has_gable) else True
    return RawSkeleton(
        nodes=tuple(nodes),
        arcs=tuple(arcs),
        events=tuple(events),
        complete=complete,
        activations=tuple(activations),
    )


def _supporting_line(a: tuple[float, float], b: tuple[float, float]) -> _Line:
    """Inward-oriented supporting line of edge ``a -> b`` on a CCW ring."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    nx = -dy / length
    ny = dx / length
    return _Line(nx=nx, ny=ny, c=nx * a[0] + ny * a[1])


def _is_reflex(vertex: _Vertex, lines: list[_Line]) -> bool:
    """True when the vertex's supporting lines form a reflex wavefront corner."""
    left, right = lines[vertex.left_edge], lines[vertex.right_edge]
    return left.nx * right.ny - left.ny * right.nx < -_REGION_TOL


def _supports_coincide(a: _Line, b: _Line) -> bool:
    """True if two supporting lines are the same oriented line."""
    if a.nx * b.nx + a.ny * b.ny < 0.999:
        return False
    return abs(a.c - b.c) <= 1e-9


def _is_straight_same_weight(
    vertex: _Vertex, lines: list[_Line], weights: list[float]
) -> bool:
    """True when the vertex sits on a same-weight collinear eave (180°)."""
    left, right = vertex.left_edge, vertex.right_edge
    if not _supports_coincide(lines[left], lines[right]):
        return False
    if abs(weights[left] - weights[right]) > 1e-9:
        return False
    return weights[left] > 0.0


def _edge_offset(i: int, t: float, weights: list[float], delays: list[float]) -> float:
    """Inward offset of edge ``i`` at time ``t`` after its delay."""
    return weights[i] * max(0.0, t - delays[i])


def _edge_speed(i: int, t: float, weights: list[float], delays: list[float]) -> float:
    """Instantaneous plan speed of edge ``i`` at time ``t``."""
    return 0.0 if t < delays[i] else weights[i]


def _vertex_velocity(
    left: int,
    right: int,
    lines: list[_Line],
    weights: list[float],
    delays: list[float] | None = None,
    t: float = 0.0,
) -> tuple[float, float] | None:
    """Plan velocity of the wavefront vertex between edges ``left`` and ``right``.

    Distinct supports: the unique solution of ``n · v = w``. Identical
    supports of equal weight: the inward normal times weight — the 180°
    bisector is perpendicular to the wall.
    """
    w_left = weights[left] if delays is None else _edge_speed(left, t, weights, delays)
    w_right = (
        weights[right] if delays is None else _edge_speed(right, t, weights, delays)
    )
    vel = _solve2(
        lines[left].nx,
        lines[left].ny,
        w_left,
        lines[right].nx,
        lines[right].ny,
        w_right,
    )
    if vel is not None:
        return vel
    if not _supports_coincide(lines[left], lines[right]):
        return None
    if abs(w_left - w_right) > 1e-9:
        return None
    return (lines[left].nx * w_left, lines[left].ny * w_left)


def _original_bisectors(
    prev_of: list[int], lines: list[_Line], weights: list[float]
) -> list[tuple[float, float]]:
    """Unit direction each original vertex moves as the wavefront advances."""
    n = len(prev_of)
    out: list[tuple[float, float]] = []
    for i in range(n):
        vel = _vertex_velocity(prev_of[i], i, lines, weights)
        if vel is None:
            out.append((0.0, 0.0))
            continue
        length = math.hypot(vel[0], vel[1])
        out.append((vel[0] / length, vel[1] / length) if length > 1e-18 else (0.0, 0.0))
    return out


def _in_felkel_region(
    px: float,
    py: float,
    edge_i: int,
    pts: list[tuple[float, float]],
    next_idx: list[int],
    bisectors: list[tuple[float, float]],
) -> bool:
    """True if ``(px, py)`` lies in the opposite edge's influence region.

    The region is bounded by the original edge (interior to its left) and
    the bisectors of its two endpoints. This is the Felkel-Obdrzalek test
    that rejects a bisector hitting the supporting line *behind* the edge
    or in a neighbour's region.
    """
    a = pts[edge_i]
    b = pts[next_idx[edge_i]]
    ex, ey = b[0] - a[0], b[1] - a[1]
    if ex * (py - a[1]) - ey * (px - a[0]) <= _REGION_TOL:
        return False
    ldx, ldy = bisectors[edge_i]
    if ldx * (py - a[1]) - ldy * (px - a[0]) >= _REGION_TOL:
        return False
    rdx, rdy = bisectors[next_idx[edge_i]]
    return rdx * (py - b[1]) - rdy * (px - b[0]) > -_REGION_TOL


def _split_candidate(
    vertex: _Vertex,
    opp: int,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
    pts: list[tuple[float, float]],
    next_idx: list[int],
    bisectors: list[tuple[float, float]],
) -> tuple[float, float, float] | None:
    """Time and point at which ``vertex`` hits original edge ``opp``, if ever."""
    if opp == vertex.left_edge or opp == vertex.right_edge:
        return None
    if _supports_coincide(lines[vertex.left_edge], lines[vertex.right_edge]):
        hit = _straight_hit_opposite(vertex, opp, lines, weights, delays)
        if hit is None:
            return None
        t, px, py = hit
    else:
        solved = _offset_meet(
            vertex.left_edge,
            vertex.right_edge,
            opp,
            lines,
            weights,
            delays,
        )
        if solved is None:
            return None
        px, py, t = solved
    if t < vertex.birth - 1e-12:
        return None
    if t < 0.0:
        t = 0.0
    if not _in_felkel_region(px, py, opp, pts, next_idx, bisectors):
        return None
    return t, px, py


def _straight_hit_opposite(
    vertex: _Vertex,
    opp: int,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[float, float, float] | None:
    """When a same-weight collinear vertex's normal-ray meets opposite ``opp``."""
    if (
        delays[opp] == 0.0
        and delays[vertex.left_edge] == 0.0
        and delays[vertex.right_edge] == 0.0
    ):
        vel = _vertex_velocity(vertex.left_edge, vertex.right_edge, lines, weights)
        if vel is None:
            return None
        opp_line = lines[opp]
        w_opp = weights[opp]
        denom = opp_line.nx * vel[0] + opp_line.ny * vel[1] - w_opp
        if abs(denom) < 1e-18:
            return None
        p0x, p0y = vertex.x, vertex.y
        rhs = (
            opp_line.c
            - (opp_line.nx * p0x + opp_line.ny * p0y)
            + (opp_line.nx * vel[0] + opp_line.ny * vel[1]) * vertex.birth
        )
        t = rhs / denom
        px = p0x + vel[0] * (t - vertex.birth)
        py = p0y + vel[1] * (t - vertex.birth)
        return t, px, py
    vel = _vertex_velocity(
        vertex.left_edge, vertex.right_edge, lines, weights, delays, vertex.birth
    )
    if vel is None:
        return None
    opp_line = lines[opp]
    w_opp = _edge_speed(opp, vertex.birth, weights, delays)
    denom = opp_line.nx * vel[0] + opp_line.ny * vel[1] - w_opp
    if abs(denom) < 1e-18:
        return None
    p0x, p0y = vertex.x, vertex.y
    rhs = (
        opp_line.c
        + _edge_offset(opp, vertex.birth, weights, delays)
        - (opp_line.nx * p0x + opp_line.ny * p0y)
    )
    t = vertex.birth + rhs / denom
    px = p0x + vel[0] * (t - vertex.birth)
    py = p0y + vel[1] * (t - vertex.birth)
    return t, px, py


def _intersect_offsets(
    l1: _Line, o1: float, l2: _Line, o2: float
) -> tuple[float, float] | None:
    """Intersection of two supporting lines after inward offsets ``o1``, ``o2``."""
    return _solve2(
        l1.nx,
        l1.ny,
        l1.c + o1,
        l2.nx,
        l2.ny,
        l2.c + o2,
    )


def _solve2(
    a11: float, a12: float, b1: float, a21: float, a22: float, b2: float
) -> tuple[float, float] | None:
    """Solve a 2x2 linear system. ``None`` if singular."""
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-18:
        return None
    return (a22 * b1 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def _position_at(
    vertex: _Vertex,
    t: float,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[float, float] | None:
    """Plan position of a wavefront vertex at time ``t`` along its bisector."""
    left, right = vertex.left_edge, vertex.right_edge
    if delays[left] == 0.0 and delays[right] == 0.0:
        pos = _intersect_offsets(
            lines[left],
            weights[left] * t,
            lines[right],
            weights[right] * t,
        )
    else:
        pos = _intersect_offsets(
            lines[left],
            _edge_offset(left, t, weights, delays),
            lines[right],
            _edge_offset(right, t, weights, delays),
        )
    if pos is not None:
        return pos
    if delays[left] == 0.0 and delays[right] == 0.0:
        vel = _vertex_velocity(left, right, lines, weights)
    else:
        vel = _vertex_velocity(left, right, lines, weights, delays, t)
    if vel is not None and _supports_coincide(
        lines[vertex.left_edge], lines[vertex.right_edge]
    ):
        dt = t - vertex.birth
        return (vertex.x + vel[0] * dt, vertex.y + vel[1] * dt)
    # Opposite parallel supports coincide at one instant: the vertex sits
    # on that collapsed line. Unique motion is undefined, so keep the
    # birth point.
    if _offsets_coincide(
        vertex.left_edge, vertex.right_edge, t, lines, weights, delays
    ):
        return (vertex.x, vertex.y)
    return None


def _offsets_coincide(
    i: int,
    j: int,
    t: float,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> bool:
    """True if original edges ``i`` and ``j`` have met as a single offset line."""
    a, b = lines[i], lines[j]
    dot = a.nx * b.nx + a.ny * b.ny
    if delays[i] == 0.0 and delays[j] == 0.0:
        off_i = weights[i] * t
        off_j = weights[j] * t
    else:
        off_i = _edge_offset(i, t, weights, delays)
        off_j = _edge_offset(j, t, weights, delays)
    if dot < -0.999:
        gap = abs(a.c + b.c)
        return abs(gap - (off_i + off_j)) <= 1e-9
    if dot > 0.999:
        # Same-direction parallels: the faster edge catches the slower.
        return abs((a.c + off_i) - (b.c + off_j)) <= 1e-9
    return False


def _vertices_meet(
    va: _Vertex,
    vb: _Vertex,
    px: float,
    py: float,
    t: float,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> bool:
    """True if both wavefront vertices are at the edge-event point at time ``t``."""
    pa = _position_at(va, t, lines, weights, delays)
    pb = _position_at(vb, t, lines, weights, delays)
    if pa is None or pb is None:
        return False
    tol = _DIST_TOL_M
    if _offsets_coincide(
        va.left_edge, va.right_edge, t, lines, weights, delays
    ) or _offsets_coincide(vb.left_edge, vb.right_edge, t, lines, weights, delays):
        tol = _PARALLEL_DIST_M
    return (
        math.hypot(pa[0] - px, pa[1] - py) < tol
        and math.hypot(pb[0] - px, pb[1] - py) < tol
    )


def _on_offset_segment(
    px: float,
    py: float,
    t: float,
    va: _Vertex,
    vb: _Vertex,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> bool:
    """True if ``(px, py)`` lies on the wavefront edge ``va → vb`` at time ``t``.

    Interior hits are splits. A hit at a convex endpoint is a vertex
    event still processed as a split (the reflex merges into that
    corner). A hit at a reflex endpoint is rejected: two reflexes
    meeting is handled by their own events, and treating it as a split
    loops.
    """
    a = _position_at(va, t, lines, weights, delays)
    b = _position_at(vb, t, lines, weights, delays)
    if a is None or b is None:
        return False
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-24:
        return False
    along = (apx * abx + apy * aby) / ab2
    dist = abs(apx * aby - apy * abx) / math.sqrt(ab2)
    if dist >= _DIST_TOL_M:
        return False
    if _ALONG_TOL < along < 1.0 - _ALONG_TOL:
        return True
    if -_ALONG_TOL <= along <= _ALONG_TOL:
        return not _is_reflex(va, lines)
    if 1.0 - _ALONG_TOL <= along <= 1.0 + _ALONG_TOL:
        return not _is_reflex(vb, lines)
    return False


def _find_opposite(
    opp: int,
    px: float,
    py: float,
    t: float,
    verts: list[_Vertex],
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[_Vertex, _Vertex] | None:
    """Current LAV endpoints of original edge ``opp`` that contain the point."""
    for vertex in verts:
        if not vertex.valid or vertex.right_edge != opp:
            continue
        other = vertex.next
        if not other.valid:
            continue
        if _on_offset_segment(px, py, t, vertex, other, lines, weights, delays):
            return vertex, other
    return None


def _edge_event(
    va: _Vertex,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[float, int, float, float] | None:
    """Time and point at which the wavefront edge between ``va`` and its next vanishes.

    Returns ``(time, vanishing_edge_index, x, y)``, or ``None`` if the
    three supporting lines never meet in the future.
    """
    vb = va.next
    i = va.right_edge
    solved = _offset_meet(
        va.left_edge,
        i,
        vb.right_edge,
        lines,
        weights,
        delays,
    )
    if solved is None:
        hit = _trajectories_meet(va, vb, lines, weights, delays)
        if hit is None:
            return None
        px, py, t = hit
    else:
        px, py, t = solved
    if t < -1e-12:
        return None
    if t < 0.0:
        t = 0.0
    return t, i, px, py


def _trajectories_meet(
    va: _Vertex,
    vb: _Vertex,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[float, float, float] | None:
    """When two adjacent wavefront vertices coincide, from linear motions."""
    involved = (va.left_edge, va.right_edge, vb.left_edge, vb.right_edge)
    if all(delays[i] == 0.0 for i in involved):
        return _trajectories_meet_constant(va, vb, lines, weights)
    t_start = max(va.birth, vb.birth, 0.0)
    cuts = {t_start}
    for i in involved:
        if delays[i] > t_start:
            cuts.add(delays[i])
    ordered = sorted(cuts)
    bounds = [*ordered, float("inf")]
    for t0, t1 in pairwise(bounds):
        pa = _position_at(va, t0, lines, weights, delays)
        pb = _position_at(vb, t0, lines, weights, delays)
        vel_a = _vertex_velocity(
            va.left_edge, va.right_edge, lines, weights, delays, t0
        )
        vel_b = _vertex_velocity(
            vb.left_edge, vb.right_edge, lines, weights, delays, t0
        )
        if pa is None or pb is None or vel_a is None or vel_b is None:
            continue
        dx = vel_a[0] - vel_b[0]
        dy = vel_a[1] - vel_b[1]
        rx = pb[0] - pa[0]
        ry = pb[1] - pa[1]
        if abs(dx) < 1e-18 and abs(dy) < 1e-18:
            continue
        if abs(dx) >= abs(dy):
            t_rel = rx / dx
            if abs(dy) > 1e-12 and abs(dy * t_rel - ry) > 1e-6:
                continue
        else:
            t_rel = ry / dy
            if abs(dx) > 1e-12 and abs(dx * t_rel - rx) > 1e-6:
                continue
        t = t0 + t_rel
        if t + 1e-12 < t0:
            continue
        if math.isfinite(t1) and t > t1 + 1e-12:
            continue
        px = pa[0] + vel_a[0] * t_rel
        py = pa[1] + vel_a[1] * t_rel
        return px, py, t
    return None


def _trajectories_meet_constant(
    va: _Vertex, vb: _Vertex, lines: list[_Line], weights: list[float]
) -> tuple[float, float, float] | None:
    """Original constant-velocity meet, used when every delay is zero."""
    vel_a = _vertex_velocity(va.left_edge, va.right_edge, lines, weights)
    vel_b = _vertex_velocity(vb.left_edge, vb.right_edge, lines, weights)
    if vel_a is None or vel_b is None:
        return None
    dx = vel_a[0] - vel_b[0]
    dy = vel_a[1] - vel_b[1]
    rx = (vb.x - vel_b[0] * vb.birth) - (va.x - vel_a[0] * va.birth)
    ry = (vb.y - vel_b[1] * vb.birth) - (va.y - vel_a[1] * va.birth)
    if abs(dx) < 1e-18 and abs(dy) < 1e-18:
        return None
    if abs(dx) >= abs(dy):
        t = rx / dx
        if abs(dy) > 1e-12 and abs(dy * t - ry) > 1e-6:
            return None
    else:
        t = ry / dy
        if abs(dx) > 1e-12 and abs(dx * t - rx) > 1e-6:
            return None
    px = va.x + vel_a[0] * (t - va.birth)
    py = va.y + vel_a[1] * (t - va.birth)
    return px, py, t


def _offset_meet(
    i1: int,
    i2: int,
    i3: int,
    lines: list[_Line],
    weights: list[float],
    delays: list[float],
) -> tuple[float, float, float] | None:
    """Intersection of three inward-offset supporting lines.

    Each line moves inward at its weight after its delay, so the point
    ``p`` at time ``t`` satisfies ``n_i · p = c_i + w_i max(0, t - a_i)``.
    The resulting ``t`` is height. Piecewise over the three delays.
    """
    if delays[i1] == 0.0 and delays[i2] == 0.0 and delays[i3] == 0.0:
        l1, l2, l3 = lines[i1], lines[i2], lines[i3]
        return _solve3(
            l1.nx,
            l1.ny,
            -weights[i1],
            l1.c,
            l2.nx,
            l2.ny,
            -weights[i2],
            l2.c,
            l3.nx,
            l3.ny,
            -weights[i3],
            l3.c,
        )
    cuts = {0.0}
    for i in (i1, i2, i3):
        if delays[i] > 0.0:
            cuts.add(delays[i])
    ordered = sorted(cuts)
    best: tuple[float, float, float] | None = None
    for k, t0 in enumerate(ordered):
        t1 = ordered[k + 1] if k + 1 < len(ordered) else float("inf")
        w_eff: list[float] = []
        c_eff: list[float] = []
        ls: list[_Line] = []
        for i in (i1, i2, i3):
            ls.append(lines[i])
            if delays[i] <= t0:
                w_eff.append(weights[i])
                c_eff.append(lines[i].c - weights[i] * delays[i])
            else:
                w_eff.append(0.0)
                c_eff.append(lines[i].c)
        solved = _solve3(
            ls[0].nx,
            ls[0].ny,
            -w_eff[0],
            c_eff[0],
            ls[1].nx,
            ls[1].ny,
            -w_eff[1],
            c_eff[1],
            ls[2].nx,
            ls[2].ny,
            -w_eff[2],
            c_eff[2],
        )
        if solved is None:
            continue
        px, py, t = solved
        if t + 1e-12 < t0:
            continue
        if math.isfinite(t1) and t > t1 + 1e-12:
            continue
        if t < -1e-12:
            continue
        if t < 0.0:
            t = 0.0
        if best is None or t < best[2]:
            best = (px, py, t)
    return best


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
