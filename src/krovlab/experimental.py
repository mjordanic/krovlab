"""Experimental roof from a face graph, outside the skeleton core.

Call :func:`roof_from_face_graph` with one footprint and an optional
face graph — which walls share a face, including one face over several
walls. When the graph is omitted, the shipped checkpoint predicts which
faces share a boundary, then this module lifts that graph. It returns a
:class:`~krovlab.roof.Roof` or a :class:`~krovlab.roof.Failure`. It does
not take a pitch and it does not train. The skeleton entry point
:func:`krovlab.roof.roof` is unchanged. This module is not imported by
``import krovlab``. PyTorch loads only when a checkpoint predicts a graph.

One vertex height is fixed at :data:`FIXED_HEIGHT` so the flat roof is
not the minimiser, as in Ren et al. 2021 section 4.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from krovlab._input import check_footprint
from krovlab._offset import apply_overhang
from krovlab.roof import (
    Arc,
    ArcKind,
    Face,
    Failure,
    Node,
    Roof,
    _finish_roof,
    _node_distance,
    _oriented_ring,
    _signed_area,
)

type Vertex = tuple[float, float]
type FaceGraph = Sequence[Sequence[int]]

FIXED_HEIGHT = 1.0
"""Metres. One roof height is fixed so a flat roof is not the lift."""

DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parents[2] / "models" / "ren2021-face-adjacency.pt"
)
"""Shipped face-adjacency weights. Used when no face graph is supplied."""

_HEIGHT_TOL = 1e-9
_COLLINEAR_SIN = 1e-9
_MEET_THRESHOLD = 0.5


def roof_from_face_graph(
    footprint: list[Vertex],
    face_graph: FaceGraph | None = None,
    *,
    overhang: float = 0.0,
    eave_height: float = 0.0,
    checkpoint: Path | str | None = DEFAULT_CHECKPOINT,
) -> Roof | Failure:
    """Lift a face graph over one footprint into a roof.

    Parameters
    ----------
    footprint
        Plan vertices ``(x, y)`` in metres.
    face_graph
        Which walls share a face: a partition of wall indices. ``None``
        asks the checkpoint to predict the graph.
    overhang
        Eaves projection in metres, applied by offsetting the footprint
        first. Zero is the same as omitting the argument.
    eave_height
        Metres above datum, added to every node after the roof exists.
    checkpoint
        Weights that predict which faces share a boundary when
        ``face_graph`` is omitted. The shipped path is the default.
        ``None``, or a path that is not a file, is Failure
        ``no_face_graph``. Ignored when a face graph is supplied.

    Returns
    -------
    Roof
        Faces, arcs, nodes, quantities, and a validity result.
    Failure
        ``no_face_graph`` when neither a graph nor a checkpoint is
        available. ``unliftable`` when the graph cannot be lifted.
        Footprint refusals use the same kinds as :func:`krovlab.roof.roof`.
    """
    cleaned = check_footprint(footprint)
    if isinstance(cleaned, Failure):
        return cleaned
    if isinstance(overhang, bool) or not isinstance(overhang, (int, float)):
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )
    if not math.isfinite(overhang) or overhang < 0.0:
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )
    if isinstance(eave_height, bool) or not isinstance(eave_height, (int, float)):
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )
    if not math.isfinite(eave_height):
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )
    expanded = apply_overhang(cleaned, [], float(overhang))
    if isinstance(expanded, Failure):
        return expanded
    cleaned, _holes = expanded
    n = len(cleaned)
    if face_graph is None:
        predicted = _predict_face_graph(cleaned, checkpoint)
        if isinstance(predicted, Failure):
            return predicted
        face_graph = predicted
    faces = _faces_from_graph(face_graph, n)
    if isinstance(faces, Failure):
        return faces
    ring, edge_map = _oriented_ring(cleaned, clockwise=False)
    caller_to_ring = {caller: i for i, caller in enumerate(edge_map)}
    oriented = []
    for group in faces:
        oriented.append(sorted((caller_to_ring[w] for w in group), key=lambda w: w))
    lifted = _lift(ring, oriented, edge_map, cleaned, float(eave_height))
    return lifted


def _unliftable(reason: str) -> Failure:
    return Failure(kind="unliftable", reason=reason)


def _no_face_graph() -> Failure:
    return Failure(
        kind="no_face_graph",
        reason="the experimental method needs a face graph, or a checkpoint",
    )


def _predict_face_graph(
    vertices: list[Vertex], checkpoint: Path | str | None
) -> list[list[int]] | Failure:
    """Load the checkpoint, predict which faces meet, return a partition."""
    if checkpoint is None:
        return _no_face_graph()
    path = Path(checkpoint)
    if not path.is_file():
        return _no_face_graph()
    try:
        from krovlab.ren_gnn import (
            load_face_adjacency_net,
            pairwise_meet_probability,
        )
    except ImportError:
        return _no_face_graph()
    model = load_face_adjacency_net(path)
    probs = pairwise_meet_probability(vertices, model)
    return _face_graph_from_meet_probability(probs)


def _face_graph_from_meet_probability(
    probs: Sequence[Sequence[float]],
) -> list[list[int]]:
    """Partition walls: consecutive walls that do not meet are one face."""
    n = len(probs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        j = (i + 1) % n
        if i != j and probs[i][j] < _MEET_THRESHOLD:
            union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _faces_from_graph(face_graph: FaceGraph, n: int) -> list[list[int]] | Failure:
    """Return a partition of wall indices that covers ``0..n-1`` once."""
    if not face_graph:
        return _unliftable("a face graph needs at least one face")
    faces: list[list[int]] = []
    for row in face_graph:
        group = list(row)
        if not group:
            return _unliftable("a face must name at least one wall")
        faces.append(group)
    seen: set[int] = set()
    for group in faces:
        for wall in group:
            if wall < 0 or wall >= n:
                return _unliftable(f"wall {wall} is not on the footprint")
            if wall in seen:
                return _unliftable(f"wall {wall} is on more than one face")
            seen.add(wall)
    if len(seen) != n:
        missing = [i for i in range(n) if i not in seen]
        return _unliftable(
            "the face graph does not cover every wall: missing "
            + ", ".join(str(i) for i in missing)
        )
    return faces


def _lift(
    ring: list[Vertex],
    faces: list[list[int]],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
) -> Roof | Failure:
    if len(faces) == 1:
        return _lift_one_plane(ring, faces[0], edge_map, footprint, eave_height)
    return _lift_fan(ring, faces, edge_map, footprint, eave_height)


def _walls_collinear(ring: list[Vertex], walls: list[int]) -> bool:
    if len(walls) <= 1:
        return True
    n = len(ring)
    a = ring[walls[0]]
    b = ring[(walls[0] + 1) % n]
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-18:
        return False
    for wall in walls[1:]:
        p = ring[wall]
        q = ring[(wall + 1) % n]
        for pt in (p, q):
            cross = dx * (pt[1] - a[1]) - dy * (pt[0] - a[0])
            if abs(cross) / length > _COLLINEAR_SIN:
                return False
    return True


def _lift_one_plane(
    ring: list[Vertex],
    walls: list[int],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
) -> Roof | Failure:
    n = len(ring)
    eave_wall = walls[0]
    start, end = ring[eave_wall], ring[(eave_wall + 1) % n]
    distances = [_signed_left(pt, start, end) for pt in ring]
    max_dist = max(distances)
    if max_dist <= _HEIGHT_TOL:
        return _unliftable("the face graph lifts only to a flat roof")
    slope = FIXED_HEIGHT / max_dist
    nodes = tuple(
        Node(pt[0], pt[1], slope * dist)
        for pt, dist in zip(ring, distances, strict=True)
    )
    cycle = list(range(n))
    pitch = math.degrees(math.atan(slope))
    eave_walls = [
        w
        for w in walls
        if abs(nodes[w].height) <= _HEIGHT_TOL
        and abs(nodes[(w + 1) % n].height) <= _HEIGHT_TOL
    ]
    if not eave_walls:
        eave_walls = [eave_wall]
    face = _face_from_cycle(
        edge_map[eave_wall], pitch, cycle, nodes, eave_walls, edge_map
    )
    arcs = _outline_arcs(nodes, n, start, end)
    return _finish_roof(nodes, [face], arcs, footprint, [], eave_height)


def _face_from_cycle(
    edge_index: int,
    pitch: float,
    cycle: list[int],
    nodes: tuple[Node, ...],
    walls: list[int],
    edge_map: list[int],
) -> Face:
    plan_area = abs(_signed_area([(nodes[j].x, nodes[j].y) for j in cycle]))
    cos_pitch = math.cos(math.radians(pitch))
    sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
    eave_indices = tuple(edge_map[w] for w in walls)
    return Face(
        edge_index=edge_index,
        pitch=pitch,
        plan_area=plan_area,
        sloped_area=sloped_area,
        node_indices=tuple(cycle),
        eave_indices=eave_indices,
    )


def _outline_arcs(
    nodes: tuple[Node, ...], n: int, eave_a: Vertex, eave_b: Vertex
) -> list[Arc]:
    arcs: list[Arc] = []
    for i in range(n):
        j = (i + 1) % n
        a, b = nodes[i], nodes[j]
        on_eave = _on_line((a.x, a.y), eave_a, eave_b) and _on_line(
            (b.x, b.y), eave_a, eave_b
        )
        if on_eave and abs(a.height) <= _HEIGHT_TOL and abs(b.height) <= _HEIGHT_TOL:
            kind: ArcKind = "eave"
        else:
            kind = "verge"
        arcs.append(Arc(start=i, end=j, kind=kind, length=_node_distance(a, b)))
    return arcs


def _on_line(pt: Vertex, a: Vertex, b: Vertex) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-18:
        return math.hypot(pt[0] - a[0], pt[1] - a[1]) <= 1e-9
    cross = dx * (pt[1] - a[1]) - dy * (pt[0] - a[0])
    return abs(cross) / length <= 1e-6


def _lift_fan(
    ring: list[Vertex],
    faces: list[list[int]],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
) -> Roof | Failure:
    apex_xy = _kernel_point(ring)
    if apex_xy is None:
        return _unliftable("no interior point from which the faces can fan")
    n = len(ring)
    parsed: list[tuple[list[int], list[int]]] = []
    for group in faces:
        chain = _consecutive_chain(group, n)
        if chain is None:
            return _unliftable("a face's walls must be a consecutive run")
        parsed.append((group, chain))
    heights = [0.0] * n
    for group, chain in parsed:
        if len(chain) < 2 or _walls_collinear(ring, group):
            continue
        start_i = chain[0]
        end_i = (chain[-1] + 1) % n
        for mid in chain[1:]:
            lifted = _height_on_plane(ring[mid], ring[start_i], ring[end_i], apex_xy)
            if lifted is None:
                return _unliftable("a face over several walls could not be made planar")
            if lifted < -_HEIGHT_TOL:
                return _unliftable(
                    "a face over several walls lifts a corner below the eave"
                )
            heights[mid] = lifted
    nodes = (
        *tuple(Node(ring[i][0], ring[i][1], heights[i]) for i in range(n)),
        Node(apex_xy[0], apex_xy[1], FIXED_HEIGHT),
    )
    apex = n
    built_faces: list[Face] = []
    arcs: list[Arc] = []
    for _group, chain in parsed:
        end = (chain[-1] + 1) % n
        cycle = [*chain, end, apex]
        pitch = _pitch_from_nodes(nodes, cycle)
        eave_walls = [
            w
            for w in chain
            if abs(nodes[w].height) <= _HEIGHT_TOL
            and abs(nodes[(w + 1) % n].height) <= _HEIGHT_TOL
        ]
        if not eave_walls:
            eave_walls = [chain[0]]
        built_faces.append(
            _face_from_cycle(
                edge_map[chain[0]], pitch, cycle, nodes, eave_walls, edge_map
            )
        )
        for wall in chain:
            a_i, b_i = wall, (wall + 1) % n
            a, b = nodes[a_i], nodes[b_i]
            on_eave = abs(a.height) <= _HEIGHT_TOL and abs(b.height) <= _HEIGHT_TOL
            kind: ArcKind = "eave" if on_eave else "verge"
            arcs.append(Arc(start=a_i, end=b_i, kind=kind, length=_node_distance(a, b)))
    for i in range(n):
        radial: ArcKind = "hip" if _convex_at(ring, i) else "valley"
        arcs.append(
            Arc(
                start=i,
                end=apex,
                kind=radial,
                length=_node_distance(nodes[i], nodes[apex]),
            )
        )
    built = _finish_roof(nodes, built_faces, arcs, footprint, [], eave_height)
    planar_fail = [
        reason
        for reason in built.validity.reasons
        if reason.startswith("every face is planar")
    ]
    if planar_fail:
        return _unliftable("the face graph could not be lifted into planar faces")
    return built


def _height_on_plane(point: Vertex, a: Vertex, b: Vertex, apex: Vertex) -> float | None:
    """Height of ``point`` on the plane through ``a``, ``b`` at z=0 and apex."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], 0.0
    vx, vy, vz = apex[0] - a[0], apex[1] - a[1], FIXED_HEIGHT
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    if abs(nz) < 1e-18:
        return None
    return -(nx * (point[0] - a[0]) + ny * (point[1] - a[1])) / nz


def _consecutive_chain(walls: list[int], n: int) -> list[int] | None:
    unique = sorted(set(walls))
    if not unique:
        return None
    if len(unique) == 1:
        return unique
    for start in unique:
        chain = [start]
        while len(chain) < len(unique):
            nxt = (chain[-1] + 1) % n
            if nxt not in unique:
                break
            chain.append(nxt)
        if len(chain) == len(unique):
            return chain
    return None


def _pitch_from_nodes(nodes: tuple[Node, ...], cycle: list[int]) -> float:
    pts = [(nodes[i].x, nodes[i].y, nodes[i].height) for i in cycle]
    origin = pts[0]
    normal = None
    for i in range(1, len(pts) - 1):
        normal = _plane_normal(origin, pts[i], pts[i + 1])
        if normal is not None:
            break
    if normal is None:
        return 0.0
    nx, ny, nz = normal
    length = math.hypot(nx, ny, nz)
    if length < 1e-18 or abs(nz) / length < 1e-18:
        return 90.0
    nz /= length
    pitch = math.degrees(math.acos(min(1.0, max(0.0, abs(nz)))))
    return pitch


def _plane_normal(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.hypot(nx, ny, nz)
    if length < 1e-18:
        return None
    return nx / length, ny / length, nz / length


def _convex_at(ring: list[Vertex], index: int) -> bool:
    n = len(ring)
    ax, ay = ring[(index - 1) % n]
    bx, by = ring[index]
    cx, cy = ring[(index + 1) % n]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0.0


def _kernel_point(ring: list[Vertex]) -> Vertex | None:
    """A point inside the polygon from which every wall is visible, if any."""
    n = len(ring)
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    best: Vertex | None = None
    best_clearance = -1.0
    grid = 16
    for i in range(grid):
        for j in range(grid):
            pt = (
                minx + (i + 0.5) / grid * (maxx - minx),
                miny + (j + 0.5) / grid * (maxy - miny),
            )
            if not _visible_from(pt, ring):
                continue
            clearance = min(
                _signed_left(pt, ring[k], ring[(k + 1) % n]) for k in range(n)
            )
            if clearance > best_clearance:
                best_clearance = clearance
                best = pt
    return best


def _visible_from(pt: Vertex, ring: list[Vertex]) -> bool:
    if not _in_ring(pt, ring):
        return False
    return all(_segment_in_ring(pt, vertex, ring) for vertex in ring)


def _in_ring(pt: Vertex, ring: list[Vertex]) -> bool:
    x, y = pt
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        crosses = yj != yi and ((yi > y) != (yj > y))
        if crosses and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segment_in_ring(a: Vertex, b: Vertex, ring: list[Vertex]) -> bool:
    for step in range(1, 8):
        t = step / 8
        pt = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if not _in_ring(pt, ring):
            return False
    return True


def _signed_left(pt: Vertex, a: Vertex, b: Vertex) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-18:
        return 0.0
    return (dx * (pt[1] - a[1]) - dy * (pt[0] - a[0])) / length
