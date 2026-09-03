"""Public roof value and the single library entry point.

Call :func:`roof` with a footprint and a pitch. Everything behind that
call — the wavefront, the event queue, the conversion of pitch to weight —
is internal. The returned :class:`Roof` is data: faces, arcs, nodes and
quantities. It has no rendering concepts and no weight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from krovlab._skeleton import skeleton as _skeleton

ArcKind = Literal["ridge", "hip", "eave"]


@dataclass(frozen=True)
class Failure:
    """Why a roof could not be produced.

    Exceptions are reserved for programmer error. Unroofable input comes
    back as a value so a caller processing many footprints can keep going.
    """

    reason: str
    """Human-readable explanation, suitable to show the architect."""


@dataclass(frozen=True)
class Node:
    """A vertex of the roof, in metres.

    Footprint corners have ``height == 0``. Skeleton nodes (ridge ends,
    the apex of a hip roof) carry the height at which the wavefront
    created them — that time *is* the height; nothing is lifted afterwards.
    """

    x: float
    """Plan x, metres."""

    y: float
    """Plan y, metres."""

    height: float
    """Height above the eave plane, metres."""


@dataclass(frozen=True)
class Face:
    """One planar piece of the roof, rising from a single footprint edge."""

    edge_index: int
    """Index of the caller's footprint edge this face rises from.

    Edge ``i`` runs from ``footprint[i]`` to ``footprint[(i + 1) % n]``,
    even if the ring was reversed internally to make it counter-clockwise.
    """

    pitch: float
    """Angle from horizontal, in degrees."""

    plan_area: float
    """Area of the face projected onto the horizontal, square metres."""

    sloped_area: float
    """True surface area (``plan_area / cos(pitch)``), square metres.

    This is what covering material is bought by.
    """

    node_indices: tuple[int, ...]
    """``Roof.nodes`` indices walking the face boundary, eave first."""


@dataclass(frozen=True)
class Arc:
    """A named edge of the roof: an eave, a hip, or a ridge."""

    start: int
    """Index into ``Roof.nodes``."""

    end: int
    """Index into ``Roof.nodes``."""

    kind: ArcKind
    """``"eave"``, ``"hip"`` (rising from a convex corner) or ``"ridge"``
    (horizontal, both ends above the eave)."""

    length: float
    """True 3D length in metres — the figure that is priced per metre."""


@dataclass(frozen=True)
class Roof:
    """A roof as data: faces, arcs, nodes and the quantities they imply."""

    nodes: tuple[Node, ...]
    """Every vertex, including the original footprint corners at height 0."""

    faces: tuple[Face, ...]
    """One face per footprint edge, in the caller's edge order after mapping."""

    arcs: tuple[Arc, ...]
    """Eaves, hips and ridges, each with a 3D length."""

    ridge_height: float
    """Highest node on the roof, metres above the eave plane."""

    total_sloped_area: float
    """Sum of every face's sloped area — the covering-cost driver."""


def roof(footprint: list[tuple[float, float]], pitch: float) -> Roof | Failure:
    """Build a roof over a convex footprint at one uniform pitch.

    Parameters
    ----------
    footprint
        Plan vertices ``(x, y)`` in metres, not closed (do not repeat the
        first point at the end). Either winding is accepted.
    pitch
        Angle of every face from horizontal, in degrees. Must satisfy
        ``0 < pitch <= 90``. Ninety degrees is the vertical-face (gable)
        bound; a fully 90° roof is degenerate.

    Returns
    -------
    Roof
        Faces, arcs, nodes and quantities.
    Failure
        If ``pitch`` is outside ``0 < pitch <= 90``.

    Examples
    --------
    >>> from krovlab import Roof, roof
    >>> result = roof([(0, 0), (10, 0), (10, 10), (0, 10)], 45)
    >>> isinstance(result, Roof)
    True
    >>> round(result.ridge_height, 6)
    5.0
    """
    if not (0.0 < pitch <= 90.0):
        return Failure("pitch must satisfy 0 < pitch <= 90")
    ring, edge_map = _ccw_ring(footprint)
    # Weight is the wavefront's plan speed. cot(pitch) so a steeper face
    # moves inward more slowly. Converted here and nowhere else.
    weight = _pitch_to_weight(pitch)
    raw = _skeleton(ring, [weight] * len(ring))
    return _roof_from_skeleton(ring, pitch, raw.nodes, raw.arcs, edge_map)


def _pitch_to_weight(pitch: float) -> float:
    """Return ``cot(pitch)``, the multiplicative wavefront speed.

    ``pitch == 90`` is the vertical-face case: the edge does not move
    (weight 0). ``tan(90°)`` is undefined, so that bound is special-cased.
    """
    if pitch >= 90.0:
        return 0.0
    return 1.0 / math.tan(math.radians(pitch))


def _ccw_ring(
    footprint: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], list[int]]:
    """Return a counter-clockwise ring and a map back to the caller's edges.

    The skeleton always walks CCW (interior on the left). If the input is
    clockwise we reverse it, but ``edge_map[i]`` still names the caller's
    original edge so ``Face.edge_index`` matches the list they passed in.
    """
    pts = list(footprint)
    n = len(pts)
    edge_map = list(range(n))
    if _signed_area(pts) < 0.0:
        pts = [pts[0], *reversed(pts[1:])]
        edge_map = [(n - 1 - i) % n for i in range(n)]
    return pts, edge_map


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area. Positive means counter-clockwise."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return 0.5 * total


def _roof_from_skeleton(
    ring: list[tuple[float, float]],
    pitch: float,
    raw_nodes: tuple[tuple[float, float, float], ...],
    raw_arcs: tuple[tuple[int, int, int, int], ...],
    edge_map: list[int],
) -> Roof:
    """Assemble a :class:`Roof` from the raw skeleton graph."""
    nodes = tuple(Node(x, y, h) for x, y, h in raw_nodes)
    n = len(ring)
    # Per-face adjacency of node indices, used to walk each face cycle.
    adj: list[dict[int, list[int]]] = [{} for _ in range(n)]

    def _link(face: int, a: int, b: int) -> None:
        adj[face].setdefault(a, []).append(b)
        adj[face].setdefault(b, []).append(a)

    arcs: list[Arc] = []
    for i in range(n):
        a, b = i, (i + 1) % n
        _link(i, a, b)
        arcs.append(
            Arc(start=a, end=b, kind="eave", length=_node_distance(nodes[a], nodes[b]))
        )

    height_tol = 1e-9
    for a, b, face_a, face_b in raw_arcs:
        _link(face_a, a, b)
        _link(face_b, a, b)
        h1 = nodes[a].height
        h2 = nodes[b].height
        # A ridge is horizontal and above the eave. Anything that still
        # climbs — typically from a corner — is a hip on a convex roof.
        if min(h1, h2) > height_tol and abs(h1 - h2) <= height_tol:
            kind: ArcKind = "ridge"
        else:
            kind = "hip"
        arcs.append(
            Arc(start=a, end=b, kind=kind, length=_node_distance(nodes[a], nodes[b]))
        )

    cos_pitch = math.cos(math.radians(pitch))
    faces: list[Face] = []
    for i in range(n):
        cycle = _walk_cycle(adj[i], i, (i + 1) % n)
        plan_area = abs(_signed_area([(nodes[j].x, nodes[j].y) for j in cycle]))
        sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
        faces.append(
            Face(
                edge_index=edge_map[i],
                pitch=pitch,
                plan_area=plan_area,
                sloped_area=sloped_area,
                node_indices=tuple(cycle),
            )
        )

    return Roof(
        nodes=nodes,
        faces=tuple(faces),
        arcs=tuple(arcs),
        ridge_height=max(node.height for node in nodes),
        total_sloped_area=sum(face.sloped_area for face in faces),
    )


def _walk_cycle(adj: dict[int, list[int]], start: int, second: int) -> list[int]:
    """Walk the face polygon starting along the eave ``start -> second``."""
    cycle = [start]
    prev, cur = start, second
    seen = {start}
    while cur != start:
        cycle.append(cur)
        if cur in seen:
            break
        seen.add(cur)
        nxts = [n for n in adj.get(cur, []) if n != prev]
        if not nxts:
            break
        prev, cur = cur, nxts[0]
    return cycle


def _node_distance(a: Node, b: Node) -> float:
    """3D Euclidean distance between two nodes, in metres."""
    return math.hypot(a.x - b.x, a.y - b.y, a.height - b.height)
