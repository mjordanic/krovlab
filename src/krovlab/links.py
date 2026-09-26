"""Roof a footprint from the walls, corners, and ridge ends the visitor connected.

A wall names one apex or one whole ridge. A corner names an allowed end of
those targets, or is left unset and resolved here. A join connects a ridge
end to another ridge end or to an apex. Standing on the same spot does not
connect anything. Faces that are open, unjoined, or not one plane are left
out, and the roof records why. Positions are not pulled back.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from krovlab._input import check_footprint
from krovlab.experimental import (
    Apex,
    Ridge,
    _clearance_midpoint,
    _distance_to_nearest_wall,
)
from krovlab.roof import (
    Arc,
    ArcKind,
    Face,
    Failure,
    Node,
    Roof,
    Validity,
    _classify_arc,
    _face_from_cycle,
    _finish_roof,
)

type Vertex = tuple[float, float]
type PointKey = tuple[str, int] | tuple[str, int, int]
_HEIGHT_TOL = 1e-6
_PLANAR_TOL = 1e-6


@dataclass(frozen=True)
class Target:
    """An apex, a whole ridge, or one end of a ridge.

    A wall leaves ``end`` unset. A corner or a join sets ``end`` to 0 or 1
    on a ridge. ``kind`` ``"none"`` is no line, and only at a corner where
    the two walls already lie in one straight line.
    """

    kind: Literal["apex", "ridge", "none"]
    index: int = 0
    end: int | None = None


@dataclass(frozen=True)
class LinkPlan:
    """The apexes, ridges, and connections read off a straight skeleton."""

    apexes: tuple[Apex, ...]
    ridges: tuple[Ridge, ...]
    walls: tuple[Target | None, ...]
    corners: tuple[Target | None, ...]
    joins: tuple[tuple[Target, Target], ...]


def links_from_skeleton(
    footprint: list[Vertex], pitch: float = 45.0
) -> LinkPlan | Failure:
    """The links that rebuild ``roof(footprint, pitch)``."""
    from krovlab.roof import roof as skeleton_roof

    ring = check_footprint(footprint)
    if isinstance(ring, Failure):
        return ring
    built = skeleton_roof(ring, pitch)
    if isinstance(built, Failure):
        return LinkPlan(
            (),
            (),
            (None,) * len(ring),
            (None,) * len(ring),
            (),
        )
    return _plan_from_roof(ring, built)


def _plan_from_roof(ring: list[Vertex], built: Roof) -> LinkPlan:
    count = len(ring)
    ridge_of_nodes: dict[tuple[int, int], int] = {}
    point_of: dict[int, Target] = {}
    ridges: list[Ridge] = []
    for arc in built.arcs:
        if arc.kind != "ridge":
            continue
        index = len(ridges)
        start, end = built.nodes[arc.start], built.nodes[arc.end]
        ridges.append(Ridge(start.x, start.y, end.x, end.y, height=start.height))
        ridge_of_nodes[(min(arc.start, arc.end), max(arc.start, arc.end))] = index
        point_of[arc.start] = Target("ridge", index, 0)
        point_of[arc.end] = Target("ridge", index, 1)
    apexes: list[Apex] = []
    for index, node in enumerate(built.nodes):
        if node.height <= _HEIGHT_TOL or index in point_of:
            continue
        point_of[index] = Target("apex", len(apexes))
        apexes.append(Apex(node.x, node.y, height=node.height))
    ends_at: dict[int, list[Target]] = {}
    for placed_index, target in point_of.items():
        if target.kind == "ridge":
            ends_at.setdefault(placed_index, []).append(target)
    joins: list[tuple[Target, Target]] = []
    for targets in ends_at.values():
        if len(targets) < 2:
            continue
        first = targets[0]
        for other in targets[1:]:
            joins.append((first, other))
    for arc in built.arcs:
        if arc.kind == "eave":
            continue
        left = point_of.get(arc.start)
        right = point_of.get(arc.end)
        if left is None or right is None:
            continue
        pair = (min(arc.start, arc.end), max(arc.start, arc.end))
        if pair in ridge_of_nodes:
            continue
        if left == right:
            continue
        joins.append((left, right))
    corner_nodes: list[int | None] = [None] * count
    wall_targets: list[Target | None] = [None] * count
    for face in built.faces:
        edge = face.edge_index
        if edge < 0 or edge >= count:
            continue
        cycle = list(face.node_indices)
        slot = _eave_slot(cycle, edge, count)
        if slot is None:
            continue
        corner_nodes[edge] = cycle[(slot - 1) % len(cycle)]
        corner_nodes[(edge + 1) % count] = cycle[(slot + 2) % len(cycle)]
        wall_targets[edge] = _wall_target(cycle, edge, count, ridge_of_nodes, point_of)
    placed = tuple(ridges)
    corners: list[Target | None] = []
    for index, corner_node in enumerate(corner_nodes):
        point = None if corner_node is None else point_of.get(corner_node)
        corners.append(
            _stored_corner(index, ring, wall_targets, point, tuple(apexes), placed)
        )
    return LinkPlan(
        tuple(apexes),
        placed,
        tuple(wall_targets),
        tuple(corners),
        tuple(joins),
    )


def _eave_slot(cycle: list[int], edge: int, count: int) -> int | None:
    nxt = (edge + 1) % count
    for index, node in enumerate(cycle):
        if node == edge and cycle[(index + 1) % len(cycle)] == nxt:
            return index
    return None


def _wall_target(
    cycle: list[int],
    edge: int,
    count: int,
    ridge_of_nodes: dict[tuple[int, int], int],
    point_of: dict[int, Target],
) -> Target | None:
    found: list[int] = []
    for start, end in zip(cycle, cycle[1:] + cycle[:1], strict=True):
        pair = (min(start, end), max(start, end))
        ridge = ridge_of_nodes.get(pair)
        if ridge is not None and ridge not in found:
            found.append(ridge)
    if len(found) == 1:
        return Target("ridge", found[0])
    slot = _eave_slot(cycle, edge, count)
    if slot is None:
        return None
    ends = (
        point_of.get(cycle[(slot - 1) % len(cycle)]),
        point_of.get(cycle[(slot + 1) % len(cycle)]),
    )
    whole = [_whole_target(point) for point in ends if point is not None]
    if not whole:
        return None
    if len(found) > 1:
        for ridge in found:
            if any(point.kind == "ridge" and point.index == ridge for point in whole):
                return Target("ridge", ridge)
    return whole[0]


def _whole_target(point: Target) -> Target:
    if point.kind == "apex":
        return Target("apex", point.index)
    return Target("ridge", point.index)


def _stored_corner(
    index: int,
    ring: list[Vertex],
    walls: list[Target | None],
    point: Target | None,
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
) -> Target | None:
    if point is None:
        return None
    count = len(ring)
    left = walls[(index - 1) % count]
    right = walls[index]
    hosts = [wall for wall in (left, right) if wall is not None]
    if len(hosts) == 2 and not _same_wall_target(hosts[0], hosts[1]):
        return point
    if not hosts:
        return point
    nearer = _nearer(ring[index], hosts[0], apexes, ridges, set())
    if point == nearer:
        return None
    return point


def roof_from_links(
    footprint: list[Vertex],
    apexes: Sequence[Apex] = (),
    ridges: Sequence[Ridge] = (),
    *,
    walls: Sequence[Target | None],
    corners: Sequence[Target | None] | None = None,
    joins: Sequence[tuple[Target, Target]] = (),
    roof_height: float | None = None,
    eave_height: float = 0.0,
    overhang: float = 0.0,
) -> Roof | Failure:
    """Draw each connected wall along the links. Typed positions stay put."""
    ring = check_footprint(footprint)
    if isinstance(ring, Failure):
        return ring
    if overhang:
        from krovlab._offset import apply_overhang

        expanded = apply_overhang(ring, [], overhang)
        if isinstance(expanded, Failure):
            return expanded
        ring = [(float(x), float(y)) for x, y in expanded[0]]
    count = len(ring)
    if len(walls) != count:
        return Failure(
            kind="degenerate",
            reason="each wall has one target, or none",
        )
    corner_row: list[Target | None]
    if corners is None:
        corner_row = [None] * count
    else:
        if len(corners) != count:
            return Failure(
                kind="degenerate",
                reason="each corner has one target, or none",
            )
        corner_row = list(corners)
    placed_apexes = tuple(apexes)
    placed_ridges = tuple(ridges)
    height = _resolved_roof_height(ring, placed_apexes, placed_ridges, roof_height)
    if isinstance(height, Failure):
        return height
    if not _targets_exist(walls, corner_row, joins, placed_apexes, placed_ridges):
        return Failure(
            kind="degenerate",
            reason="a link names a missing apex or ridge",
        )
    notes: list[str] = []
    resolved = _resolve_corners(
        ring, walls, corner_row, placed_apexes, placed_ridges, notes
    )
    nodes, apex_at, ridge_at = _placed_nodes(
        ring, placed_apexes, placed_ridges, height
    )
    adjacent = _link_graph(placed_apexes, placed_ridges, joins)
    faces: list[Face] = []
    for edge, wall in enumerate(walls):
        if wall is None:
            notes.append(f"wall {edge + 1} is open")
            continue
        start = resolved[edge]
        end = resolved[(edge + 1) % count]
        if start is None or end is None:
            continue
        face = _face_from_wall(
            edge,
            start,
            end,
            nodes,
            adjacent,
            apex_at,
            ridge_at,
            notes,
        )
        if face is not None:
            faces.append(face)
    arcs = _arcs_from_faces(nodes, faces, ring)
    built = _finish_roof(tuple(nodes), faces, arcs, list(ring), [], eave_height)
    reasons = [*notes, *built.validity.reasons]
    return Roof(
        nodes=built.nodes,
        faces=built.faces,
        arcs=built.arcs,
        ridge_height=built.ridge_height,
        total_sloped_area=built.total_sloped_area,
        validity=Validity(is_terrain=not reasons, reasons=tuple(reasons)),
    )


def _resolved_roof_height(
    ring: list[Vertex],
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
    roof_height: float | None,
) -> float | Failure:
    needs_box = any(apex.height is None for apex in apexes) or any(
        ridge.height is None for ridge in ridges
    )
    if not needs_box:
        return roof_height if roof_height is not None else 0.0
    if roof_height is None:
        middle = _clearance_midpoint(ring)
        if middle is None:
            return Failure(
                kind="degenerate",
                reason="no interior point from which the faces can fan",
            )
        return _distance_to_nearest_wall(ring, middle)
    if (
        isinstance(roof_height, bool)
        or not isinstance(roof_height, (int, float))
        or not math.isfinite(roof_height)
        or roof_height <= 0
    ):
        return Failure(
            kind="degenerate",
            reason="roof height must be metres above the eaves, greater than zero",
        )
    return float(roof_height)


def _targets_exist(
    walls: Sequence[Target | None],
    corners: Sequence[Target | None],
    joins: Sequence[tuple[Target, Target]],
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
) -> bool:
    named: list[tuple[Target, bool]] = []
    for wall in walls:
        if wall is not None:
            named.append((wall, False))
    for corner in corners:
        if corner is not None and corner.kind != "none":
            named.append((corner, True))
    for left, right in joins:
        named.append((left, True))
        named.append((right, True))
    for target, end_required in named:
        if not _target_exists(target, len(apexes), len(ridges), end_required):
            return False
    return True


def _target_exists(
    target: Target, apex_count: int, ridge_count: int, end_required: bool
) -> bool:
    if target.kind == "apex":
        return 0 <= target.index < apex_count and target.end is None
    if target.kind != "ridge":
        return False
    if not 0 <= target.index < ridge_count:
        return False
    if end_required:
        return target.end in (0, 1)
    return target.end is None


def _resolve_corners(
    ring: list[Vertex],
    walls: Sequence[Target | None],
    corners: Sequence[Target | None],
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
    notes: list[str],
) -> list[Target | None]:
    count = len(ring)
    resolved: list[Target | None] = []
    for index in range(count):
        left = walls[(index - 1) % count]
        right = walls[index]
        choice = corners[index]
        allowed = _allowed_targets(left, right)
        if choice is not None and choice.kind == "none":
            resolved.append(choice)
            continue
        if choice is not None:
            if choice not in allowed:
                notes.append(f"corner {index + 1} is not an allowed end")
                resolved.append(None)
            else:
                resolved.append(choice)
            continue
        hosts = [wall for wall in (left, right) if wall is not None]
        if len(hosts) == 2 and not _same_wall_target(hosts[0], hosts[1]):
            notes.append(f"corner {index + 1} is open")
            resolved.append(None)
            continue
        if not hosts:
            resolved.append(None)
            continue
        avoid = _ends_already_used(index, walls, corners, hosts[0])
        resolved.append(_nearer(ring[index], hosts[0], apexes, ridges, avoid))
    return resolved


def allowed_corner_targets(
    left: Target | None, right: Target | None
) -> tuple[Target, ...]:
    """Ends a corner may use, given the two walls that meet there."""
    return tuple(_allowed_targets(left, right))


def _allowed_targets(
    left: Target | None, right: Target | None
) -> list[Target]:
    hosts = [wall for wall in (left, right) if wall is not None]
    if not hosts:
        return []
    if len(hosts) == 2 and not _same_wall_target(hosts[0], hosts[1]):
        return [*_ends_of(hosts[0]), *_ends_of(hosts[1])]
    return _ends_of(hosts[0])


def _ends_of(wall: Target) -> list[Target]:
    if wall.kind == "apex":
        return [Target("apex", wall.index)]
    return [Target("ridge", wall.index, 0), Target("ridge", wall.index, 1)]


def _same_wall_target(left: Target, right: Target) -> bool:
    return left.kind == right.kind and left.index == right.index


def _ends_already_used(
    index: int,
    walls: Sequence[Target | None],
    corners: Sequence[Target | None],
    host: Target,
) -> set[int]:
    count = len(walls)
    used: set[int] = set()
    for other in ((index - 1) % count, (index + 1) % count):
        choice = corners[other]
        if (
            choice is not None
            and choice.kind == "ridge"
            and choice.index == host.index
            and choice.end is not None
            and host.kind == "ridge"
        ):
            used.add(choice.end)
    return used


def _nearer(
    point: Vertex,
    wall: Target,
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
    avoid: set[int],
) -> Target:
    if wall.kind == "apex":
        return Target("apex", wall.index)
    ridge = ridges[wall.index]
    ends = ((0, ridge.x0, ridge.y0), (1, ridge.x1, ridge.y1))
    distances = [
        (math.hypot(point[0] - x, point[1] - y), end) for end, x, y in ends
    ]
    nearest = min(distance for distance, _end in distances)
    candidates = [
        end for distance, end in distances if abs(distance - nearest) <= 1e-9
    ]
    for end in candidates:
        if end not in avoid:
            return Target("ridge", wall.index, end)
    return Target("ridge", wall.index, candidates[0])


def _placed_nodes(
    ring: list[Vertex],
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
    roof_height: float,
) -> tuple[list[Node], dict[int, int], dict[tuple[int, int], int]]:
    nodes = [Node(x, y, 0.0) for x, y in ring]
    apex_at: dict[int, int] = {}
    for index, apex in enumerate(apexes):
        apex_at[index] = len(nodes)
        nodes.append(Node(apex.x, apex.y, _height_of(apex.height, roof_height)))
    ridge_at: dict[tuple[int, int], int] = {}
    for index, ridge in enumerate(ridges):
        height = _height_of(ridge.height, roof_height)
        for end, x, y in (
            (0, ridge.x0, ridge.y0),
            (1, ridge.x1, ridge.y1),
        ):
            ridge_at[(index, end)] = len(nodes)
            nodes.append(Node(x, y, height))
    return nodes, apex_at, ridge_at


def _height_of(height: float | None, roof_height: float) -> float:
    if height is None:
        return roof_height
    return float(height)


def _link_graph(
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
    joins: Sequence[tuple[Target, Target]],
) -> dict[PointKey, list[tuple[PointKey, float]]]:
    adjacent: dict[PointKey, list[tuple[PointKey, float]]] = {}
    for index, ridge in enumerate(ridges):
        _add_edge(
            adjacent,
            ("ridge", index, 0),
            ("ridge", index, 1),
            math.hypot(ridge.x1 - ridge.x0, ridge.y1 - ridge.y0),
        )
    for left, right in joins:
        start = _point_key(left)
        end = _point_key(right)
        if start is None or end is None or start == end:
            continue
        if _same_ridge_ends(start, end):
            continue
        _add_edge(
            adjacent,
            start,
            end,
            _key_length(start, end, apexes, ridges),
        )
    return adjacent


def _key_length(
    start: PointKey,
    end: PointKey,
    apexes: tuple[Apex, ...],
    ridges: tuple[Ridge, ...],
) -> float:
    ax, ay = _key_xy(start, apexes, ridges)
    bx, by = _key_xy(end, apexes, ridges)
    return math.hypot(bx - ax, by - ay)


def _key_xy(
    key: PointKey, apexes: tuple[Apex, ...], ridges: tuple[Ridge, ...]
) -> Vertex:
    if key[0] == "apex":
        apex = apexes[key[1]]
        return apex.x, apex.y
    ridge = ridges[key[1]]
    if key[-1] == 0:
        return ridge.x0, ridge.y0
    return ridge.x1, ridge.y1


def _point_key(target: Target) -> PointKey | None:
    if target.kind == "apex":
        return ("apex", target.index)
    if target.kind == "ridge" and target.end in (0, 1):
        return ("ridge", target.index, target.end)
    return None


def _same_ridge_ends(start: PointKey, end: PointKey) -> bool:
    return (
        start[0] == "ridge"
        and end[0] == "ridge"
        and start[1] == end[1]
        and start[-1] != end[-1]
    )


def _add_edge(
    adjacent: dict[PointKey, list[tuple[PointKey, float]]],
    start: PointKey,
    end: PointKey,
    length: float,
) -> None:
    adjacent.setdefault(start, []).append((end, length))
    adjacent.setdefault(end, []).append((start, length))


def _face_from_wall(
    edge: int,
    start: Target,
    end: Target,
    nodes: list[Node],
    adjacent: dict[PointKey, list[tuple[PointKey, float]]],
    apex_at: dict[int, int],
    ridge_at: dict[tuple[int, int], int],
    notes: list[str],
) -> Face | None:
    path = _shortest(_point_key(end), _point_key(start), adjacent)
    if not path:
        notes.append(f"wall {edge + 1}'s corners are not connected")
        return None
    count = _boundary_count(nodes)
    polygon = [edge, (edge + 1) % count]
    for key in path:
        node = _node_of(key, apex_at, ridge_at)
        if node != polygon[-1]:
            polygon.append(node)
    if len(polygon) >= 2 and polygon[0] == polygon[-1]:
        polygon.pop()
    if len(polygon) < 3:
        notes.append(f"wall {edge + 1}'s corners are not connected")
        return None
    built = tuple(nodes)
    if not _is_plane(built, polygon):
        if _same_ridge_point(start, end):
            notes.append(f"wall {edge + 1}'s ridge is not parallel to the wall")
        else:
            notes.append(f"wall {edge + 1} is not one plane")
        return None
    pitch = _pitch(built, polygon)
    return _face_from_cycle(edge, pitch, polygon, built)


def _boundary_count(nodes: list[Node]) -> int:
    count = 0
    for node in nodes:
        if node.height > _HEIGHT_TOL:
            break
        count += 1
    return count


def _node_of(
    key: PointKey | None,
    apex_at: dict[int, int],
    ridge_at: dict[tuple[int, int], int],
) -> int:
    if key is None:
        return -1
    if key[0] == "apex":
        return apex_at[key[1]]
    return ridge_at[(key[1], key[-1])]


def _same_ridge_point(start: Target, end: Target) -> bool:
    return (
        start.kind == "ridge"
        and end.kind == "ridge"
        and start.index == end.index
        and start.end is not None
        and end.end is not None
    )


def _shortest(
    start: PointKey | None,
    goal: PointKey | None,
    adjacent: dict[PointKey, list[tuple[PointKey, float]]],
) -> list[PointKey] | None:
    if start is None or goal is None:
        return None
    if start == goal:
        return [start]
    distances = {start: 0.0}
    previous: dict[PointKey, PointKey | None] = {start: None}
    queue: list[tuple[float, int, PointKey]] = [(0.0, 0, start)]
    stamp = 0
    while queue:
        distance, _stamp, node = heapq.heappop(queue)
        if distance > distances.get(node, math.inf):
            continue
        if node == goal:
            break
        for nxt, weight in adjacent.get(node, []):
            trial = distance + weight
            if trial < distances.get(nxt, math.inf) - 1e-12:
                distances[nxt] = trial
                previous[nxt] = node
                stamp += 1
                heapq.heappush(queue, (trial, stamp, nxt))
    if goal not in previous:
        return None
    path: list[PointKey] = []
    cursor: PointKey | None = goal
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    path.reverse()
    return path


def _is_plane(nodes: tuple[Node, ...], polygon: list[int]) -> bool:
    normal = _normal(nodes, polygon)
    if normal is None:
        return False
    origin = _xyz(nodes, polygon[0])
    nx, ny, nz = normal
    for index in polygon[1:]:
        x, y, z = _xyz(nodes, index)
        dist = abs(
            nx * (x - origin[0]) + ny * (y - origin[1]) + nz * (z - origin[2])
        )
        if dist > _PLANAR_TOL:
            return False
    return True


def _pitch(nodes: tuple[Node, ...], polygon: list[int]) -> float:
    normal = _normal(nodes, polygon)
    if normal is None:
        return 0.0
    nx, ny, nz = normal
    return math.degrees(math.atan2(math.hypot(nx, ny), abs(nz)))


def _normal(
    nodes: tuple[Node, ...], polygon: list[int]
) -> tuple[float, float, float] | None:
    origin = _xyz(nodes, polygon[0])
    for index in range(1, len(polygon) - 1):
        normal = _unit_normal(
            origin, _xyz(nodes, polygon[index]), _xyz(nodes, polygon[index + 1])
        )
        if normal is not None:
            return normal
    return None


def _unit_normal(
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


def _xyz(nodes: tuple[Node, ...], index: int) -> tuple[float, float, float]:
    node = nodes[index]
    return node.x, node.y, node.height


def _arcs_from_faces(
    nodes: list[Node], faces: list[Face], ring: list[Vertex]
) -> list[Arc]:
    built = tuple(nodes)
    seen: set[tuple[int, int]] = set()
    arcs: list[Arc] = []
    for face in faces:
        cycle = list(face.node_indices)
        pairs = list(zip(cycle, cycle[1:] + cycle[:1], strict=True))
        for start, end in pairs:
            key = (start, end) if start < end else (end, start)
            if key in seen or start == end:
                continue
            seen.add(key)
            kind = _arc_kind(built[start], built[end], ring)
            length = math.dist(
                (built[start].x, built[start].y, built[start].height),
                (built[end].x, built[end].y, built[end].height),
            )
            arcs.append(Arc(start=start, end=end, kind=kind, length=length))
    return arcs


def _arc_kind(start: Node, end: Node, ring: list[Vertex]) -> ArcKind:
    if start.height <= _HEIGHT_TOL and end.height <= _HEIGHT_TOL:
        return "eave"
    return _classify_arc(start, end, [ring], _HEIGHT_TOL)
