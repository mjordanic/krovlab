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
from krovlab._triangulate import (
    _edges,
    _flip,
    point_inside,
    segments_cross,
    triangulate,
)
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
    style: str = "apex"
    offers_ridge: bool = False
    ridge_hx: float = 0.0
    ridge_hy: float = 0.0


@dataclass(frozen=True)
class Placement:
    """Metres from the clearance midpoint, in the footprint's axes.

    ``(0, 0)`` is that midpoint. Omitted placement is the same as this.
    ``style`` is ``"apex"`` or ``"ridge"``. Ridge is used only when the
    footprint's maximum-clearance set is one segment and no face spans
    several walls; otherwise the apex is built.
    """

    dx: float = 0.0
    dy: float = 0.0
    style: str = "apex"


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
        on that span. On a 10 by 6 m rectangle that distance is 3 m.
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
    style = "apex"
    if placement is not None and placement.style == "ridge":
        style = "ridge"
    expanded = apply_overhang(cleaned, [], float(overhang))
    if isinstance(expanded, Failure):
        return expanded
    cleaned, _holes = expanded
    rise = (
        float(roof_height) if roof_height is not None else _default_roof_height(cleaned)
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
        ring,
        oriented,
        edge_map,
        cleaned,
        float(eave_height),
        rise,
        offset,
        style,
    )
    return lifted


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
    style: str = "apex",
) -> Roof | Failure:
    if len(faces) == 1:
        return _lift_one_plane(
            ring, faces[0], edge_map, footprint, eave_height, roof_height
        )
    offered = _simple_ridge(ring, faces)
    if style == "ridge" and offered is not None:
        return _lift_ridge(
            ring,
            faces,
            edge_map,
            footprint,
            eave_height,
            roof_height,
            offset,
            offered,
        )
    return _lift_fan(
        ring,
        faces,
        edge_map,
        footprint,
        eave_height,
        roof_height,
        offset,
        offered is not None,
        offered,
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
    offers_ridge: bool = False,
    ridge: tuple[Vertex, Vertex, dict[int, int]] | None = None,
) -> Roof | Failure:
    midpoint = _clearance_midpoint(ring)
    if midpoint is None:
        return _unliftable("no interior point from which the faces can fan")
    target = (midpoint[0] + offset[0], midpoint[1] + offset[1])
    half = _ridge_half(ridge)
    return _pull_back(
        midpoint,
        target,
        lambda apex_xy: _lift_fan_at(
            ring, faces, edge_map, footprint, eave_height, roof_height, apex_xy
        ),
        offers_ridge=offers_ridge,
        ridge_half=half,
    )


def _lifts(result: Roof | Failure) -> bool:
    return isinstance(result, Roof) and result.validity.is_terrain


def _remember(
    result: Roof | Failure,
    midpoint: Vertex,
    *,
    offers_ridge: bool = False,
    ridge_half: Vertex = (0.0, 0.0),
) -> Roof | Failure:
    if not isinstance(result, Roof):
        return result
    placed = _interior_xy(result)
    style = "ridge" if any(arc.kind == "ridge" for arc in result.arcs) else "apex"
    return PlacedRoof(
        nodes=result.nodes,
        faces=result.faces,
        arcs=result.arcs,
        ridge_height=result.ridge_height,
        total_sloped_area=result.total_sloped_area,
        validity=result.validity,
        used_dx=placed[0] - midpoint[0],
        used_dy=placed[1] - midpoint[1],
        style=style,
        offers_ridge=offers_ridge,
        ridge_hx=ridge_half[0],
        ridge_hy=ridge_half[1],
    )


def _interior_xy(result: Roof) -> Vertex:
    ridges = [arc for arc in result.arcs if arc.kind == "ridge"]
    if len(ridges) == 1:
        start = result.nodes[ridges[0].start]
        end = result.nodes[ridges[0].end]
        return ((start.x + end.x) / 2.0, (start.y + end.y) / 2.0)
    apex = result.nodes[-1]
    return (apex.x, apex.y)


def _pull_back(
    midpoint: Vertex,
    target: Vertex,
    build: Callable[[Vertex], Roof | Failure],
    *,
    offers_ridge: bool = False,
    ridge_half: Vertex = (0.0, 0.0),
) -> Roof | Failure:
    """Last place on the segment from the midpoint to ``target`` that lifts."""

    def remember(result: Roof | Failure) -> Roof | Failure:
        return _remember(
            result,
            midpoint,
            offers_ridge=offers_ridge,
            ridge_half=ridge_half,
        )

    placed = build(target)
    if _lifts(placed):
        return remember(placed)
    origin = build(midpoint)
    if not _lifts(origin):
        return remember(origin)
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
    return remember(best)


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


def _ridge_half(
    ridge: tuple[Vertex, Vertex, dict[int, int]] | None,
) -> Vertex:
    if ridge is None:
        return (0.0, 0.0)
    start, end, _links = ridge
    return ((end[0] - start[0]) / 2.0, (end[1] - start[1]) / 2.0)


def _simple_ridge(
    ring: list[Vertex], faces: list[list[int]]
) -> tuple[Vertex, Vertex, dict[int, int]] | None:
    """One clearance segment, and every interior skeleton node on it.

    An L has that segment plus lower interior nodes, so it is not offered.
    A face over several walls is not offered either.
    """
    if any(len(group) != 1 for group in faces):
        return None
    n = len(ring)
    raw = _straight_skeleton([ring], [1.0] * n)
    if not raw.complete or not raw.nodes:
        return None
    max_height = max(node[2] for node in raw.nodes)
    if max_height <= 1e-6:
        return None
    interior = [i for i, node in enumerate(raw.nodes) if node[2] > 1e-6]
    segments: list[tuple[int, int]] = []
    for start, end, _face_a, _face_b in raw.arcs:
        if start < n or end < n:
            continue
        a = raw.nodes[start]
        b = raw.nodes[end]
        if abs(a[2] - max_height) > 1e-6 or abs(b[2] - max_height) > 1e-6:
            continue
        if math.hypot(a[0] - b[0], a[1] - b[1]) <= 1e-6:
            continue
        segments.append((start, end))
    if len(segments) != 1:
        return None
    first, second = segments[0]
    if set(interior) != {first, second}:
        return None
    links: dict[int, int] = {}
    for start, end, _face_a, _face_b in raw.arcs:
        boundary: int | None
        inner: int | None
        if start < n <= end:
            boundary, inner = start, end
        elif end < n <= start:
            boundary, inner = end, start
        else:
            continue
        if inner not in (first, second):
            return None
        links[boundary] = 0 if inner == first else 1
    if set(links) != set(range(n)):
        return None
    start_xy = (raw.nodes[first][0], raw.nodes[first][1])
    end_xy = (raw.nodes[second][0], raw.nodes[second][1])
    if (end_xy[0], end_xy[1]) < (start_xy[0], start_xy[1]):
        start_xy, end_xy = end_xy, start_xy
        links = {corner: 1 - which for corner, which in links.items()}
    return start_xy, end_xy, links


def _lift_ridge(
    ring: list[Vertex],
    faces: list[list[int]],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
    roof_height: float,
    offset: Vertex,
    ridge: tuple[Vertex, Vertex, dict[int, int]],
) -> Roof | Failure:
    midpoint = _clearance_midpoint(ring)
    if midpoint is None:
        return _unliftable("no interior point from which the faces can fan")
    target = (midpoint[0] + offset[0], midpoint[1] + offset[1])
    half = _ridge_half(ridge)
    return _pull_back(
        midpoint,
        target,
        lambda apex_xy: _lift_ridge_at(
            ring,
            faces,
            edge_map,
            footprint,
            eave_height,
            roof_height,
            ridge,
            midpoint,
            apex_xy,
        ),
        offers_ridge=True,
        ridge_half=half,
    )


def _lift_ridge_at(
    ring: list[Vertex],
    faces: list[list[int]],
    edge_map: list[int],
    footprint: list[Vertex],
    eave_height: float,
    roof_height: float,
    ridge: tuple[Vertex, Vertex, dict[int, int]],
    midpoint: Vertex,
    apex_xy: Vertex,
) -> Roof | Failure:
    start, end, links = ridge
    shift = (apex_xy[0] - midpoint[0], apex_xy[1] - midpoint[1])
    a_xy = (start[0] + shift[0], start[1] + shift[1])
    b_xy = (end[0] + shift[0], end[1] + shift[1])
    n = len(ring)
    nodes = (
        *tuple(Node(ring[i][0], ring[i][1], 0.0) for i in range(n)),
        Node(a_xy[0], a_xy[1], roof_height),
        Node(b_xy[0], b_xy[1], roof_height),
    )
    start_i = n
    end_i = n + 1

    def ridge_end(corner: int) -> int:
        return start_i if links[corner] == 0 else end_i

    built_faces: list[Face] = []
    arcs: list[Arc] = []
    for group in faces:
        wall = group[0]
        nxt = (wall + 1) % n
        left = ridge_end(wall)
        right = ridge_end(nxt)
        cycle = [wall, nxt, left] if left == right else [wall, nxt, right, left]
        pitch = _pitch_from_nodes(nodes, cycle)
        built_faces.append(
            _face_from_cycle(edge_map[wall], pitch, cycle, nodes, [wall], edge_map)
        )
        a, b = nodes[wall], nodes[nxt]
        arcs.append(Arc(start=wall, end=nxt, kind="eave", length=_node_distance(a, b)))
    seen: set[tuple[int, int]] = set()
    for corner in range(n):
        inner = ridge_end(corner)
        pair = (corner, inner)
        if pair in seen:
            continue
        seen.add(pair)
        kind: ArcKind = "hip" if _convex_at(ring, corner) else "valley"
        arcs.append(
            Arc(
                start=corner,
                end=inner,
                kind=kind,
                length=_node_distance(nodes[corner], nodes[inner]),
            )
        )
    arcs.append(
        Arc(
            start=start_i,
            end=end_i,
            kind="ridge",
            length=_node_distance(nodes[start_i], nodes[end_i]),
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
    return min(_segment_distance(pt, ring[i], ring[(i + 1) % n]) for i in range(n))


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


def _reflects_onto_itself(points: list[Vertex], nx: float, ny: float, c: float) -> bool:
    for x, y in points:
        distance = nx * x + ny * y - c
        image = (x - 2 * distance * nx, y - 2 * distance * ny)
        if not any(
            math.hypot(image[0] - other[0], image[1] - other[1]) < 1e-6
            for other in points
        ):
            return False
    return True


@dataclass(frozen=True)
class Apex:
    """One interior point, in footprint metres. ``height`` is above the eaves."""

    x: float
    y: float
    height: float | None = None


@dataclass(frozen=True)
class Ridge:
    """One level interior segment, in footprint metres.

    ``height`` is above the eaves. Both ends share it. ``None`` uses the
    roof height passed to :func:`roof_from_interiors`.
    """

    x0: float
    y0: float
    x1: float
    y1: float
    height: float | None = None


@dataclass(frozen=True)
class InteriorRoof(Roof):
    """A roof whose interior is the apexes and ridges that were actually used."""

    apexes: tuple[Apex, ...] = ()
    ridges: tuple[Ridge, ...] = ()


def roof_from_interiors(
    footprint: list[Vertex],
    apexes: Sequence[Apex] | None = None,
    ridges: Sequence[Ridge] | None = None,
    *,
    overhang: float = 0.0,
    eave_height: float = 0.0,
    roof_height: float | None = None,
    previous_apexes: Sequence[Apex] | None = None,
    previous_ridges: Sequence[Ridge] | None = None,
) -> InteriorRoof | Failure:
    """Roof a footprint from apexes and ridges the visitor placed.

    Omitting both is one apex at the clearance midpoint. A placement that
    does not return a roof is pulled back along the line from the previous
    interior (or that single apex) toward the request. The result records
    the positions actually used.
    """
    ring = check_footprint(footprint)
    if isinstance(ring, Failure):
        return ring
    if overhang:
        expanded = apply_overhang(ring, [], overhang)
        if isinstance(expanded, Failure):
            return expanded
        ring = expanded[0]
    placed_apexes = () if apexes is None else tuple(apexes)
    placed_ridges = () if ridges is None else tuple(ridges)
    height = roof_height
    if height is None:
        middle = _clearance_midpoint(ring)
        if middle is None:
            return _unliftable("no interior point from which the faces can fan")
        height = _distance_to_nearest_wall(ring, middle)
    if (
        isinstance(height, bool)
        or not isinstance(height, (int, float))
        or not math.isfinite(height)
        or height <= 0
    ):
        return Failure(
            kind="degenerate",
            reason="roof height must be metres above the eaves, greater than zero",
        )
    if apexes is None and ridges is None:
        placed_apexes = (_default_apex(ring, float(height)),)
    anchor_apexes = placed_apexes if previous_apexes is None else tuple(previous_apexes)
    anchor_ridges = placed_ridges if previous_ridges is None else tuple(previous_ridges)
    if previous_apexes is None and previous_ridges is None:
        anchor_apexes = (_default_apex(ring, float(height)),)
        anchor_ridges = ()
    return _pull_interiors(
        ring,
        list(footprint),
        float(height),
        eave_height,
        anchor_apexes,
        anchor_ridges,
        placed_apexes,
        placed_ridges,
    )


def _pull_interiors(
    ring: list[Vertex],
    footprint: list[Vertex],
    roof_height: float,
    eave_height: float,
    anchor_apexes: tuple[Apex, ...],
    anchor_ridges: tuple[Ridge, ...],
    placed_apexes: tuple[Apex, ...],
    placed_ridges: tuple[Ridge, ...],
) -> InteriorRoof | Failure:
    def at(t: float) -> tuple[tuple[Apex, ...], tuple[Ridge, ...]]:
        return (
            tuple(
                Apex(
                    (1 - t) * a.x + t * b.x,
                    (1 - t) * a.y + t * b.y,
                    height=_blend_height(a.height, b.height, t, roof_height),
                )
                for a, b in zip(anchor_apexes, placed_apexes, strict=True)
            )
            if len(anchor_apexes) == len(placed_apexes)
            else placed_apexes,
            tuple(
                Ridge(
                    (1 - t) * a.x0 + t * b.x0,
                    (1 - t) * a.y0 + t * b.y0,
                    (1 - t) * a.x1 + t * b.x1,
                    (1 - t) * a.y1 + t * b.y1,
                    height=_blend_height(a.height, b.height, t, roof_height),
                )
                for a, b in zip(anchor_ridges, placed_ridges, strict=True)
            )
            if len(anchor_ridges) == len(placed_ridges)
            else placed_ridges,
        )

    def build(t: float) -> InteriorRoof | Failure:
        apex_at, ridge_at = at(t)
        return _build_interiors(
            ring, footprint, roof_height, eave_height, apex_at, ridge_at
        )

    direct = build(1.0)
    if isinstance(direct, InteriorRoof) and direct.validity.is_terrain:
        return direct
    if len(anchor_apexes) != len(placed_apexes) or len(anchor_ridges) != len(
        placed_ridges
    ):
        return (
            direct
            if isinstance(direct, Failure)
            else _unliftable("the interior could not be cut into triangles")
        )
    low, high = 0.0, 1.0
    best: InteriorRoof | None = None
    origin = build(0.0)
    if isinstance(origin, InteriorRoof) and origin.validity.is_terrain:
        best = origin
    for _ in range(24):
        mid = (low + high) / 2
        trial = build(mid)
        if isinstance(trial, InteriorRoof) and trial.validity.is_terrain:
            low = mid
            best = trial
        else:
            high = mid
    if best is None:
        return (
            direct
            if isinstance(direct, Failure)
            else _unliftable("the interior could not be cut into triangles")
        )
    return best


def _build_interiors(
    ring: list[Vertex],
    footprint: list[Vertex],
    roof_height: float,
    eave_height: float,
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
) -> InteriorRoof | Failure:
    n = len(ring)
    apex_points = [(apex.x, apex.y) for apex in apexes]
    apex_heights = [_placed_height(apex.height, roof_height) for apex in apexes]
    ridge_points: list[Vertex] = []
    ridge_heights: list[float] = []
    constraints: list[tuple[int, int]] = []
    snapped: list[Ridge] = []
    for ridge in ridges:
        ridge_height = _placed_height(ridge.height, roof_height)
        earlier = len(ridge_points)
        ends: list[int] = []
        for x, y in ((ridge.x0, ridge.y0), (ridge.x1, ridge.y1)):
            joined = _joined_apex(apex_points, x, y)
            if joined is not None:
                if abs(apex_heights[joined] - ridge_height) > 1e-6:
                    return _unliftable("a joined ridge end shares the apex height")
                ends.append(n + joined)
                continue
            if not point_inside(x, y, ring):
                return _unliftable("a ridge end stays inside the footprint")
            meeting = _meeting_end(
                ridge_points, ridge_heights, earlier, x, y, ridge_height
            )
            if isinstance(meeting, Failure):
                return meeting
            if meeting is not None:
                ends.append(n + len(apex_points) + meeting)
                continue
            ends.append(n + len(apex_points) + len(ridge_points))
            ridge_points.append((x, y))
            ridge_heights.append(ridge_height)
        if ends[0] == ends[1]:
            return _unliftable("a ridge needs two distinct ends")
        constraints.append((ends[0], ends[1]))
        snapped.append(
            Ridge(
                ridge.x0,
                ridge.y0,
                ridge.x1,
                ridge.y1,
                height=ridge_height,
            )
        )
    for x, y in apex_points:
        if not point_inside(x, y, ring):
            return _unliftable("an apex stays inside the footprint")
    for i, first in enumerate(ridges):
        for second in ridges[i + 1 :]:
            if segments_cross(
                (first.x0, first.y0),
                (first.x1, first.y1),
                (second.x0, second.y0),
                (second.x1, second.y1),
            ):
                return _unliftable("ridges do not cross")
    interior = [*apex_points, *ridge_points]
    interior_heights = [*apex_heights, *ridge_heights]
    if not interior:
        return _unliftable("the roof needs an apex or a ridge")
    triangles = triangulate(ring, interior, constraints)
    if triangles is None:
        return _unliftable("the interior could not be cut into triangles")
    nodes = (
        *tuple(Node(x, y, 0.0) for x, y in ring),
        *tuple(
            Node(x, y, height)
            for (x, y), height in zip(interior, interior_heights, strict=True)
        ),
    )
    locked: set[tuple[int, int]] = set()
    for start, end in constraints:
        locked.add((start, end) if start < end else (end, start))
    for index in range(n):
        nxt = (index + 1) % n
        locked.add((index, nxt) if index < nxt else (nxt, index))
    built = _terrain_from_flips(
        [*ring, *interior],
        triangles,
        locked,
        nodes,
        interior_heights,
        n,
        footprint,
        eave_height,
        tuple(
            Apex(apex.x, apex.y, height=height)
            for apex, height in zip(apexes, apex_heights, strict=True)
        ),
        tuple(snapped),
    )
    if built is None:
        return _unliftable("the interior could not be cut into triangles")
    return built


def _terrain_from_flips(
    points: list[Vertex],
    triangles: list[tuple[int, int, int]],
    locked: set[tuple[int, int]],
    nodes: tuple[Node, ...],
    heights: list[float],
    boundary: int,
    footprint: list[Vertex],
    eave_height: float,
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
) -> InteriorRoof | None:
    """The triangulation, or a nearby flip, when that roof is a terrain."""

    def assemble(
        mesh: list[tuple[int, int, int]],
    ) -> InteriorRoof | None:
        if _flat_interior_triangle(mesh, heights, boundary):
            return None
        faces, arcs = _faces_from_triangles(nodes, mesh, boundary)
        if faces is None or arcs is None:
            return None
        built = _finish_roof(nodes, faces, arcs, footprint, [], eave_height)
        return InteriorRoof(
            nodes=built.nodes,
            faces=built.faces,
            arcs=built.arcs,
            ridge_height=built.ridge_height,
            total_sloped_area=built.total_sloped_area,
            validity=built.validity,
            apexes=apexes,
            ridges=ridges,
        )

    first = assemble(triangles)
    if isinstance(first, InteriorRoof) and first.validity.is_terrain:
        return first
    seen = {_mesh_key(triangles)}
    queue = [triangles]
    while queue and len(seen) < 48:
        current = queue.pop(0)
        flipped: set[tuple[int, int]] = set()
        for tri in current:
            for start, end in _edges(tri):
                edge = (start, end) if start < end else (end, start)
                if edge in locked or edge in flipped:
                    continue
                flipped.add(edge)
                nxt = _flip(current, points, start, end)
                if nxt is None:
                    continue
                key = _mesh_key(nxt)
                if key in seen:
                    continue
                seen.add(key)
                roof = assemble(nxt)
                if isinstance(roof, InteriorRoof) and roof.validity.is_terrain:
                    return roof
                queue.append(nxt)
                if len(seen) >= 48:
                    break
    return first


def _mesh_key(
    triangles: list[tuple[int, int, int]],
) -> tuple[tuple[int, int, int], ...]:
    ordered: list[tuple[int, int, int]] = []
    for one, two, three in triangles:
        a, b, c = sorted((one, two, three))
        ordered.append((a, b, c))
    return tuple(sorted(ordered))


def _blend_height(
    previous: float | None, requested: float | None, t: float, roof_height: float
) -> float:
    start = roof_height if previous is None else previous
    end = roof_height if requested is None else requested
    return (1 - t) * start + t * end


def _placed_height(height: float | None, roof_height: float) -> float:
    if height is None:
        return roof_height
    return float(height)


def _flat_interior_triangle(
    triangles: list[tuple[int, int, int]], heights: list[float], boundary: int
) -> bool:
    """A triangle of interior points at one height is a flat cap."""
    for tri in triangles:
        if min(tri) < boundary:
            continue
        used = [heights[index - boundary] for index in tri]
        if max(used) - min(used) <= 1e-6:
            return True
    return False


def _joined_apex(apexes: list[Vertex], x: float, y: float) -> int | None:
    best: int | None = None
    best_d = 0.25
    for index, (ax, ay) in enumerate(apexes):
        dist = math.hypot(x - ax, y - ay)
        if dist <= best_d:
            best = index
            best_d = dist
    return best


def _meeting_end(
    points: list[Vertex],
    heights: list[float],
    earlier: int,
    x: float,
    y: float,
    height: float,
) -> int | Failure | None:
    """The ridge end already placed here, or a Failure when the heights differ."""
    exact = next(
        (
            index
            for index, (px, py) in enumerate(points)
            if math.hypot(x - px, y - py) < 1e-6
        ),
        None,
    )
    near = exact if exact is not None else _joined_apex(points[:earlier], x, y)
    if near is None:
        return None
    if abs(heights[near] - height) > 1e-6:
        return _unliftable("ridge ends that meet share one height")
    return near


def _faces_from_triangles(
    nodes: tuple[Node, ...],
    triangles: list[tuple[int, int, int]],
    boundary: int,
) -> tuple[list[Face] | None, list[Arc] | None]:
    parent = list(range(len(triangles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    edge_owners: dict[tuple[int, int], list[int]] = {}
    for index, tri in enumerate(triangles):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge_owners.setdefault(_sorted_edge(a, b), []).append(index)
    for _edge, owners in edge_owners.items():
        if len(owners) == 2 and _coplanar(
            nodes, triangles[owners[0]], triangles[owners[1]]
        ):
            union(owners[0], owners[1])
    groups: dict[int, list[int]] = {}
    for index in range(len(triangles)):
        groups.setdefault(find(index), []).append(index)
    faces: list[Face] = []
    face_edges: list[tuple[int, int]] = []
    for members in groups.values():
        cycle = _group_cycle(triangles, members)
        if cycle is None:
            return None, None
        if _signed_area([(nodes[i].x, nodes[i].y) for i in cycle]) < 0:
            cycle = list(reversed(cycle))
        walls = [
            wall
            for start, end in zip(cycle, [*cycle[1:], cycle[0]], strict=True)
            if (wall := _wall_index(start, end, boundary)) is not None
        ]
        if not walls:
            return None, None
        pitch = _pitch_from_nodes(nodes, cycle)
        faces.append(
            _face_from_cycle(
                walls[0], pitch, cycle, nodes, walls, list(range(boundary))
            )
        )
        face_edges.extend(
            (start, end)
            for start, end in zip(cycle, [*cycle[1:], cycle[0]], strict=True)
        )
    arcs: list[Arc] = []
    seen: set[tuple[int, int]] = set()
    for start, end in face_edges:
        key = _sorted_edge(start, end)
        if key in seen:
            continue
        seen.add(key)
        kind = _arc_kind(nodes, start, end, boundary)
        arcs.append(
            Arc(
                start=start,
                end=end,
                kind=kind,
                length=_node_distance(nodes[start], nodes[end]),
            )
        )
    return faces, arcs


def _wall_index(start: int, end: int, boundary: int) -> int | None:
    if start >= boundary or end >= boundary:
        return None
    if end == (start + 1) % boundary:
        return start
    if start == (end + 1) % boundary:
        return end
    return None


def _is_wall(start: int, end: int, boundary: int) -> bool:
    return _wall_index(start, end, boundary) is not None


def _arc_kind(nodes: tuple[Node, ...], start: int, end: int, boundary: int) -> ArcKind:
    if _is_wall(start, end, boundary):
        return "eave"
    a, b = nodes[start], nodes[end]
    if a.height > 1e-6 and b.height > 1e-6:
        if abs(a.height - b.height) <= 1e-6:
            return "ridge"
        return "hip"
    corner = start if start < boundary else end
    ring = [(nodes[i].x, nodes[i].y) for i in range(boundary)]
    return "hip" if _convex_at(ring, corner) else "valley"


def _coplanar(
    nodes: tuple[Node, ...], one: tuple[int, int, int], other: tuple[int, int, int]
) -> bool:
    ids = list(dict.fromkeys((*one, *other)))
    if len(ids) < 4:
        return True
    origin = (nodes[ids[0]].x, nodes[ids[0]].y, nodes[ids[0]].height)
    normal = None
    for index in range(1, len(ids) - 1):
        normal = _plane_normal(
            origin,
            (nodes[ids[index]].x, nodes[ids[index]].y, nodes[ids[index]].height),
            (
                nodes[ids[index + 1]].x,
                nodes[ids[index + 1]].y,
                nodes[ids[index + 1]].height,
            ),
        )
        if normal is not None:
            break
    if normal is None:
        return True
    nx, ny, nz = normal
    for index in ids:
        point = nodes[index]
        dist = abs(
            nx * (point.x - origin[0])
            + ny * (point.y - origin[1])
            + nz * (point.height - origin[2])
        )
        if dist > 1e-6:
            return False
    return True


def _group_cycle(
    triangles: list[tuple[int, int, int]], members: list[int]
) -> list[int] | None:
    counts: dict[tuple[int, int], int] = {}
    for index in members:
        tri = triangles[index]
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = _sorted_edge(a, b)
            counts[key] = counts.get(key, 0) + 1
    boundary = [edge for edge, count in counts.items() if count == 1]
    if not boundary:
        return None
    followers: dict[int, list[int]] = {}
    for a, b in boundary:
        followers.setdefault(a, []).append(b)
        followers.setdefault(b, []).append(a)
    start = boundary[0][0]
    cycle = [start]
    previous = -1
    while True:
        nxts = [n for n in followers[cycle[-1]] if n != previous]
        if not nxts:
            return None
        nxt = nxts[0]
        if nxt == start:
            break
        if nxt in cycle:
            return None
        previous = cycle[-1]
        cycle.append(nxt)
        if len(cycle) > len(boundary):
            return None
    return cycle


def _sorted_edge(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def _default_apex(ring: list[Vertex], roof_height: float) -> Apex:
    """Clearance midpoint when it roofs; otherwise the nearest point that does."""
    middle = _clearance_midpoint(ring)
    if middle is not None and _apex_roofs(ring, middle, roof_height):
        return Apex(middle[0], middle[1])
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    best: Vertex | None = None
    best_d = float("inf")
    target = middle if middle is not None else (sum(xs) / len(xs), sum(ys) / len(ys))
    for i in range(1, 12):
        for j in range(1, 12):
            point = (
                min(xs) + (max(xs) - min(xs)) * i / 12,
                min(ys) + (max(ys) - min(ys)) * j / 12,
            )
            if not point_inside(point[0], point[1], ring):
                continue
            if not _apex_roofs(ring, point, roof_height):
                continue
            dist = math.hypot(point[0] - target[0], point[1] - target[1])
            if dist < best_d:
                best_d = dist
                best = point
    if best is None:
        return Apex(target[0], target[1])
    return Apex(best[0], best[1])


def _apex_roofs(ring: list[Vertex], point: Vertex, roof_height: float) -> bool:
    built = _build_interiors(
        ring, ring, roof_height, 0.0, (Apex(point[0], point[1]),), ()
    )
    return isinstance(built, InteriorRoof) and built.validity.is_terrain


def _distance_to_nearest_wall(ring: list[Vertex], point: Vertex) -> float:
    return min(
        abs(_signed_left(point, ring[i], ring[(i + 1) % len(ring)]))
        for i in range(len(ring))
    )


def _signed_left(pt: Vertex, a: Vertex, b: Vertex) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-18:
        return 0.0
    return (dx * (pt[1] - a[1]) - dy * (pt[0] - a[0])) / length
