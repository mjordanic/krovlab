"""Experimental roof from a face graph, outside the skeleton core.

Call :func:`roof_from_face_graph` with one footprint and an optional
face graph — which walls share a face, including one face over several
walls. When the graph is omitted, the shipped checkpoint predicts which
faces share a boundary, then this module lifts that graph. It returns a
:class:`~krovlab.roof.Roof` or a :class:`~krovlab.roof.Failure`. It does
not take a pitch and it does not train. The skeleton entry point
:func:`krovlab.roof.roof` is unchanged. This module is not imported by
``import krovlab``. PyTorch loads only when a checkpoint predicts a graph.

The eaves stay at zero while the roof is lifted. ``roof_height`` is how
many metres the roof rises above them. Omitting it uses the distance from
an interior point to the nearest wall.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from krovlab._input import check_footprint
from krovlab._offset import apply_overhang
from krovlab._skeleton import skeleton as _straight_skeleton
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


@dataclass(frozen=True)
class PlacedRoof(Roof):
    """A fan roof that records the offset, in metres, that was actually used."""

    used_dx: float = 0.0
    used_dy: float = 0.0


@dataclass(frozen=True)
class Placement:
    """Metres from the clearance midpoint, in the footprint's axes.

    ``(0, 0)`` is that midpoint. Omitted placement is the same as this.
    """

    dx: float = 0.0
    dy: float = 0.0

    def added(self, dx: float, dy: float) -> Placement:
        """Shift this offset by another pair of metres."""
        return Placement(dx=self.dx + dx, dy=self.dy + dy)


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
    roof_height: float | None = None,
    checkpoint: Path | str | None = DEFAULT_CHECKPOINT,
    placement: Placement | None = None,
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
    roof_height
        Metres the roof rises above the eaves. ``None`` uses the distance
        from an interior point to the nearest wall, the rise of a 45° hip
        on that span. On a 10 × 6 m rectangle that distance is 3 m.
    checkpoint
        Weights that predict which faces share a boundary when
        ``face_graph`` is omitted. The shipped path is the default.
        ``None``, or a path that is not a file, is Failure
        ``no_face_graph``. Ignored when a face graph is supplied.
    placement
        Offset in metres from the midpoint of the maximum-clearance set.
        Omitted, the apex is that midpoint. A single plane has no interior
        to move, so the offset is ignored there.

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
    if roof_height is not None and (
        isinstance(roof_height, bool) or not isinstance(roof_height, (int, float))
    ):
        return Failure(
            kind="degenerate",
            reason="roof height must be a finite number of metres above the eaves",
        )
    if roof_height is not None and (
        not math.isfinite(roof_height) or roof_height <= 0.0
    ):
        return Failure(
            kind="degenerate",
            reason="roof height must be a finite number of metres above the eaves",
        )
    offset = _placement_offset(placement)
    if isinstance(offset, Failure):
        return offset
    expanded = apply_overhang(cleaned, [], float(overhang))
    if isinstance(expanded, Failure):
        return expanded
    cleaned, _holes = expanded
    rise = (
        float(roof_height)
        if roof_height is not None
        else _default_roof_height(cleaned)
    )
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
    lifted = _lift(
        ring, oriented, edge_map, cleaned, float(eave_height), rise, offset
    )
    return lifted


def moved_toward_wall(
    footprint: Sequence[Vertex],
    wall_number: int,
    placement: Placement | None = None,
    metres: float = 1.0,
) -> Placement | Failure:
    """Add ``metres`` toward wall ``wall_number`` (page numbering, from 1).

    The step is perpendicular to that wall, from the current interior
    toward the wall, so the distance to it decreases.
    """
    current = placement if placement is not None else Placement()
    if (
        isinstance(wall_number, bool)
        or not isinstance(wall_number, int)
        or wall_number < 1
        or wall_number > len(footprint)
    ):
        return Failure(
            kind="degenerate",
            reason=(
                "wall number must be one of the walls on the page, starting at Wall 1"
            ),
        )
    if (
        isinstance(metres, bool)
        or not isinstance(metres, (int, float))
        or not math.isfinite(metres)
    ):
        return Failure(
            kind="degenerate",
            reason="a move toward a wall must be a finite number of metres",
        )
    index = wall_number - 1
    start = footprint[index]
    end = footprint[(index + 1) % len(footprint)]
    edge_x = end[0] - start[0]
    edge_y = end[1] - start[1]
    length = math.hypot(edge_x, edge_y)
    if length < 1e-18:
        return Failure(
            kind="degenerate",
            reason="a move toward a wall needs a wall with length",
        )
    midpoint = _clearance_midpoint(list(footprint))
    if midpoint is None:
        return Failure(
            kind="unliftable",
            reason="no interior point from which the faces can fan",
        )
    interior = (midpoint[0] + current.dx, midpoint[1] + current.dy)
    signed = (
        edge_x * (interior[1] - start[1]) - edge_y * (interior[0] - start[0])
    ) / length
    left_x = -edge_y / length
    left_y = edge_x / length
    if signed >= 0.0:
        step_x, step_y = -left_x, -left_y
    else:
        step_x, step_y = left_x, left_y
    return current.added(step_x * float(metres), step_y * float(metres))


def _placement_offset(placement: Placement | None) -> Vertex | Failure:
    if placement is None:
        return (0.0, 0.0)
    dx, dy = placement.dx, placement.dy
    if (
        isinstance(dx, bool)
        or isinstance(dy, bool)
        or not isinstance(dx, (int, float))
        or not isinstance(dy, (int, float))
        or not math.isfinite(dx)
        or not math.isfinite(dy)
    ):
        return Failure(
            kind="degenerate",
            reason="placement offset must be finite metres from the clearance midpoint",
        )
    return (float(dx), float(dy))


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
    roof_height: float,
    offset: Vertex,
) -> Roof | Failure:
    if len(faces) == 1:
        return _lift_one_plane(
            ring, faces[0], edge_map, footprint, eave_height, roof_height
        )
    return _lift_fan(
        ring, faces, edge_map, footprint, eave_height, roof_height, offset
    )


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
    roof_height: float,
) -> Roof | Failure:
    n = len(ring)
    eave_wall = walls[0]
    start, end = ring[eave_wall], ring[(eave_wall + 1) % n]
    distances = [_signed_left(pt, start, end) for pt in ring]
    max_dist = max(distances)
    if max_dist <= _HEIGHT_TOL:
        return _unliftable("the face graph lifts only to a flat roof")
    slope = roof_height / max_dist
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
    roof_height: float,
    offset: Vertex,
) -> Roof | Failure:
    midpoint = _clearance_midpoint(ring)
    if midpoint is None:
        return _unliftable("no interior point from which the faces can fan")
    target = (midpoint[0] + offset[0], midpoint[1] + offset[1])
    return _pull_back(midpoint, target, lambda apex_xy: _lift_fan_at(
        ring, faces, edge_map, footprint, eave_height, roof_height, apex_xy
    ))


def _lifts(result: Roof | Failure) -> bool:
    return isinstance(result, Roof) and result.validity.is_terrain


def _remember(result: Roof | Failure, midpoint: Vertex) -> Roof | Failure:
    if not isinstance(result, Roof):
        return result
    apex = result.nodes[-1]
    return PlacedRoof(
        nodes=result.nodes,
        faces=result.faces,
        arcs=result.arcs,
        ridge_height=result.ridge_height,
        total_sloped_area=result.total_sloped_area,
        validity=result.validity,
        used_dx=apex.x - midpoint[0],
        used_dy=apex.y - midpoint[1],
    )


def _pull_back(
    midpoint: Vertex,
    target: Vertex,
    build: Callable[[Vertex], Roof | Failure],
) -> Roof | Failure:
    """Last place on the segment from the midpoint to ``target`` that lifts."""
    placed = build(target)
    if _lifts(placed):
        return _remember(placed, midpoint)
    origin = build(midpoint)
    if not _lifts(origin):
        return _remember(origin, midpoint)
    low = 0.0
    high = 1.0
    best: Roof | Failure = origin
    for _ in range(40):
        t = (low + high) / 2.0
        point = (
            midpoint[0] + t * (target[0] - midpoint[0]),
            midpoint[1] + t * (target[1] - midpoint[1]),
        )
        trial = build(point)
        if _lifts(trial):
            low = t
            best = trial
        else:
            high = t
    return _remember(best, midpoint)


def _lift_fan_at(
    ring: list[Vertex],
    faces: list[list[int]],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
    roof_height: float,
    apex_xy: Vertex,
) -> Roof | Failure:
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
            lifted = _height_on_plane(
                ring[mid], ring[start_i], ring[end_i], apex_xy, roof_height
            )
            if lifted is None:
                return _unliftable("a face over several walls could not be made planar")
            if lifted < -_HEIGHT_TOL:
                return _unliftable(
                    "a face over several walls lifts a corner below the eave"
                )
            heights[mid] = lifted
    nodes = (
        *tuple(Node(ring[i][0], ring[i][1], heights[i]) for i in range(n)),
        Node(apex_xy[0], apex_xy[1], roof_height),
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


def _height_on_plane(
    point: Vertex, a: Vertex, b: Vertex, apex: Vertex, roof_height: float
) -> float | None:
    """Height of ``point`` on the plane through ``a``, ``b`` at z=0 and apex."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], 0.0
    vx, vy, vz = apex[0] - a[0], apex[1] - a[1], roof_height
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


def _clearance_midpoint(ring: list[Vertex]) -> Vertex | None:
    """Midpoint of the points farthest from the nearest wall.

    Equal-speed straight skeleton: height is distance to the boundary.
    The maximum-clearance set is the skeleton at that greatest height,
    a point or a segment. A rectangle's segment is centered here.
    """
    oriented, _edge_map = _oriented_ring(list(ring), clockwise=False)
    raw = _straight_skeleton([oriented], [1.0] * len(oriented))
    if not raw.complete or not raw.nodes:
        return None
    max_height = max(node[2] for node in raw.nodes)
    segments: list[tuple[Vertex, Vertex]] = []
    for start, end, _face_a, _face_b in raw.arcs:
        a = raw.nodes[start]
        b = raw.nodes[end]
        if abs(a[2] - max_height) > 1e-6 or abs(b[2] - max_height) > 1e-6:
            continue
        if math.hypot(a[0] - b[0], a[1] - b[1]) <= 1e-6:
            continue
        segments.append(((a[0], a[1]), (b[0], b[1])))
    if segments:
        moment_x = 0.0
        moment_y = 0.0
        length = 0.0
        for left, right in segments:
            span = math.hypot(right[0] - left[0], right[1] - left[1])
            moment_x += 0.5 * (left[0] + right[0]) * span
            moment_y += 0.5 * (left[1] + right[1]) * span
            length += span
        return (moment_x / length, moment_y / length)
    tops = [node for node in raw.nodes if abs(node[2] - max_height) <= 1e-6]
    if not tops:
        return None
    count = float(len(tops))
    return (
        sum(node[0] for node in tops) / count,
        sum(node[1] for node in tops) / count,
    )


def _default_roof_height(ring: list[Vertex]) -> float:
    """Rise of a 45° hip: distance from the clearance midpoint to the nearest wall."""
    apex = _clearance_midpoint(ring)
    if apex is None:
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        return 0.5 * min(max(xs) - min(xs), max(ys) - min(ys))
    return _distance_to_boundary(apex, ring)


def _distance_to_boundary(pt: Vertex, ring: list[Vertex]) -> float:
    n = len(ring)
    return min(
        _segment_distance(pt, ring[i], ring[(i + 1) % n]) for i in range(n)
    )


def _segment_distance(pt: Vertex, a: Vertex, b: Vertex) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-18:
        return math.hypot(pt[0] - a[0], pt[1] - a[1])
    t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    return math.hypot(pt[0] - (a[0] + t * dx), pt[1] - (a[1] + t * dy))


def reflection_axes(ring: Sequence[Vertex]) -> list[tuple[float, float, float]]:
    """Lines ``nx x + ny y = c`` that reflect ``ring`` onto itself.

    ``(nx, ny)`` is a unit normal. A rectangle has one axis through each
    pair of opposite sides. An L has none.
    """
    points = [(float(x), float(y)) for x, y in ring]
    count = len(points)
    if count < 3:
        return []
    cx = sum(point[0] for point in points) / count
    cy = sum(point[1] for point in points) / count
    directions: list[tuple[float, float]] = []
    for x, y in points:
        directions.append((x - cx, y - cy))
    for index, (x, y) in enumerate(points):
        other = points[(index + 1) % count]
        directions.append(((x + other[0]) / 2 - cx, (y + other[1]) / 2 - cy))
    axes: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for dx, dy in directions:
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue
        nx, ny = -dy / length, dx / length
        c = nx * cx + ny * cy
        if nx < -1e-9 or (abs(nx) <= 1e-9 and ny < 0):
            nx, ny, c = -nx, -ny, -c
        if abs(nx) < 1e-9:
            nx = 0.0
        if abs(ny) < 1e-9:
            ny = 0.0
        key = (round(nx, 6), round(ny, 6), round(c, 6))
        if key in seen:
            continue
        seen.add(key)
        if _reflects_onto_itself(points, nx, ny, c):
            axes.append((nx, ny, c))
    return axes


def _reflects_onto_itself(
    points: list[Vertex], nx: float, ny: float, c: float
) -> bool:
    for x, y in points:
        distance = nx * x + ny * y - c
        image = (x - 2 * distance * nx, y - 2 * distance * ny)
        if not any(
            math.hypot(image[0] - other[0], image[1] - other[1]) < 1e-6
            for other in points
        ):
            return False
    return True


def _signed_left(pt: Vertex, a: Vertex, b: Vertex) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-18:
        return 0.0
    return (dx * (pt[1] - a[1]) - dy * (pt[0] - a[0])) / length
