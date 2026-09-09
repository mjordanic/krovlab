"""Roof-graph embedding when consecutive edges are one plane.

Topology comes from the outline's skeleton dual with wrap faces merged.
Vertex positions are then the intersections of supporting planes, so each
face is planar by construction. Not a public seam.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from krovlab._skeleton import RawSkeleton
    from krovlab.roof import Failure, Roof


_DET_TOL = 1e-18
_XY_TOL = 1e-9


def embed_wrap(
    rings: list[list[tuple[float, float]]],
    ring_pitches: list[float],
    raw: RawSkeleton,
    edge_map: list[int],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    eave_height: float,
    wrap_groups: list[tuple[int, ...]],
    caller_pitches: list[float],
) -> Roof | Failure:
    """Assemble a wrapped roof from skeleton topology and supporting planes."""
    from krovlab.roof import (
        Arc,
        Face,
        Failure,
        Node,
        _classify_arc,
        _finish_roof,
        _next_indices,
        _node_distance,
        _signed_area,
        _walk_cycle,
    )

    next_idx = _next_indices(rings)
    n = len(next_idx)
    gabled = [p >= 90.0 for p in ring_pitches]
    logical = _logical_ids(edge_map, wrap_groups)
    eave_of = _eave_indices_by_logical(wrap_groups, edge_map)
    planes = _face_planes(rings, next_idx, ring_pitches, logical, eave_of, edge_map)
    if isinstance(planes, Failure):
        return planes

    adj: list[dict[int, list[int]]] = [{} for _ in range(n)]

    def link(face: int, a: int, b: int) -> None:
        nbrs = adj[face].setdefault(a, [])
        if b not in nbrs:
            nbrs.append(b)
        nbrs_b = adj[face].setdefault(b, [])
        if a not in nbrs_b:
            nbrs_b.append(a)

    for i in range(n):
        if gabled[i]:
            continue
        link(i, i, next_idx[i])
    for a, b, face_a, face_b in raw.arcs:
        if gabled[face_a] and gabled[face_b]:
            continue
        if logical[face_a] == logical[face_b] and not gabled[face_a]:
            continue
        if not gabled[face_a]:
            link(face_a, a, b)
        if not gabled[face_b]:
            link(face_b, a, b)

    merged_adj: dict[int, dict[int, list[int]]] = {}
    for i in range(n):
        if gabled[i]:
            continue
        bucket = merged_adj.setdefault(logical[i], {})
        for node, nbrs in adj[i].items():
            dest = bucket.setdefault(node, [])
            for nbr in nbrs:
                if nbr not in dest:
                    dest.append(nbr)

    incident = _incident_logical(raw.arcs, logical, gabled, n, next_idx)
    drop = {
        node
        for node, lids in incident.items()
        if node >= n and len(lids) < 3
    }

    nodes = [Node(x, y, h) for x, y, h in raw.nodes]
    for node, lids in incident.items():
        if node in drop or node < n or len(lids) != 3:
            continue
        ids = sorted(lids)
        if any(lid not in planes for lid in ids):
            continue
        hit = _intersect_three_planes(planes[ids[0]], planes[ids[1]], planes[ids[2]])
        if hit is None:
            continue
        nodes[node] = Node(*hit)

    pts: list[tuple[float, float]] = []
    for ring in rings:
        pts.extend(ring)
    for group in wrap_groups:
        polyline = _wrap_polyline_on_ring(group, edge_map, pts, next_idx)
        if polyline is None:
            continue
        plane = planes.get(group[0])
        if plane is None:
            continue
        for vertex in polyline[1:-1]:
            for i, pt in enumerate(pts):
                if math.hypot(pt[0] - vertex[0], pt[1] - vertex[1]) <= _XY_TOL:
                    x, y = nodes[i].x, nodes[i].y
                    nodes[i] = Node(x, y, plane[0] * x + plane[1] * y + plane[2])
                    break

    built_nodes = tuple(nodes)
    faces: list[Face] = []
    eave_pairs: set[tuple[int, int]] = set()
    boundary: set[tuple[int, int]] = set()
    emitted: set[int] = set()
    for i in range(n):
        if gabled[i]:
            continue
        lid = logical[i]
        if lid in emitted:
            continue
        eaves = eave_of[lid]
        start = _ring_index_of(eaves[0], edge_map)
        cycle = _walk_cycle(merged_adj.get(lid, {}), start, next_idx[start])
        cycle = _dedupe_cycle([idx for idx in cycle if idx not in drop])
        if len(cycle) < 3:
            return Failure(
                kind="nonplanar_wrap",
                reason="the wrap could not embed as a planar terrain",
            )
        for edge in eaves:
            ring_edge = _ring_index_of(edge, edge_map)
            eave_pairs.add(_undirected(ring_edge, next_idx[ring_edge]))
        for u, v in zip(cycle, cycle[1:] + cycle[:1], strict=True):
            boundary.add(_undirected(u, v))
        plan_area = abs(
            _signed_area([(built_nodes[j].x, built_nodes[j].y) for j in cycle])
        )
        pitch = caller_pitches[lid]
        cos_pitch = math.cos(math.radians(pitch))
        sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
        faces.append(
            Face(
                edge_index=lid,
                pitch=pitch,
                plan_area=plan_area,
                sloped_area=sloped_area,
                node_indices=tuple(cycle),
                eave_indices=eaves,
            )
        )
        emitted.add(lid)

    height_tol = 1e-9
    arcs: list[Arc] = []
    seen_arcs: set[tuple[int, int]] = set()
    for a, b in sorted(boundary):
        key = _undirected(a, b)
        if key in seen_arcs:
            continue
        seen_arcs.add(key)
        kind = (
            "eave"
            if key in eave_pairs
            else _classify_arc(built_nodes[a], built_nodes[b], rings, height_tol)
        )
        arcs.append(
            Arc(
                start=a,
                end=b,
                kind=kind,
                length=_node_distance(built_nodes[a], built_nodes[b]),
            )
        )

    built = _finish_roof(built_nodes, faces, arcs, footprint, holes, eave_height)
    from krovlab._validity import _planar_reasons

    if _planar_reasons(built.nodes, built.faces) or not built.validity.is_terrain:
        return Failure(
            kind="nonplanar_wrap",
            reason="the wrap could not embed as a planar terrain",
        )
    return built


def _undirected(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def _dedupe_cycle(cycle: list[int]) -> list[int]:
    if not cycle:
        return cycle
    out: list[int] = []
    for idx in cycle:
        if not out or out[-1] != idx:
            out.append(idx)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _logical_ids(edge_map: list[int], wrap_groups: list[tuple[int, ...]]) -> list[int]:
    owner = {edge: group[0] for group in wrap_groups for edge in group}
    return [owner.get(edge_map[i], edge_map[i]) for i in range(len(edge_map))]


def _eave_indices_by_logical(
    wrap_groups: list[tuple[int, ...]], edge_map: list[int]
) -> dict[int, tuple[int, ...]]:
    grouped = {group[0]: group for group in wrap_groups}
    out: dict[int, tuple[int, ...]] = {}
    for caller in edge_map:
        out.setdefault(caller, grouped.get(caller, (caller,)))
    for group in wrap_groups:
        out[group[0]] = group
    return out


def _ring_index_of(caller: int, edge_map: list[int]) -> int:
    for i, mapped in enumerate(edge_map):
        if mapped == caller:
            return i
    return 0


def _incident_logical(
    raw_arcs: tuple[tuple[int, int, int, int], ...],
    logical: list[int],
    gabled: list[bool],
    n_outline: int,
    next_idx: list[int],
) -> dict[int, set[int]]:
    incident: dict[int, set[int]] = {}

    def add(node: int, face: int) -> None:
        if gabled[face]:
            return
        incident.setdefault(node, set()).add(logical[face])

    for a, b, face_a, face_b in raw_arcs:
        add(a, face_a)
        add(b, face_a)
        add(a, face_b)
        add(b, face_b)
    for i in range(n_outline):
        add(i, i)
        add(next_idx[i], i)
    return incident


def _face_planes(
    rings: list[list[tuple[float, float]]],
    next_idx: list[int],
    ring_pitches: list[float],
    logical: list[int],
    eave_of: dict[int, tuple[int, ...]],
    edge_map: list[int],
) -> dict[int, tuple[float, float, float]] | Failure:
    from krovlab.roof import Failure

    pts: list[tuple[float, float]] = []
    for ring in rings:
        pts.extend(ring)
    planes: dict[int, tuple[float, float, float]] = {}
    done: set[int] = set()
    for i, lid in enumerate(logical):
        if lid in done or ring_pitches[i] >= 90.0:
            continue
        done.add(lid)
        eaves = eave_of[lid]
        pitch = ring_pitches[i]
        if len(eaves) == 1:
            plane = _edge_plane(pts[i], pts[next_idx[i]], pitch)
        else:
            polyline = _wrap_polyline_on_ring(eaves, edge_map, pts, next_idx)
            if polyline is None:
                return Failure(
                    kind="nonplanar_wrap",
                    reason="the wrap could not embed as a planar terrain",
                )
            plane = _wrap_plane(polyline, pitch)
        if plane is None:
            return Failure(
                kind="nonplanar_wrap",
                reason="the wrap could not embed as a planar terrain",
            )
        planes[lid] = plane
    return planes


def _wrap_polyline_on_ring(
    eaves: tuple[int, ...],
    edge_map: list[int],
    pts: list[tuple[float, float]],
    next_idx: list[int],
) -> list[tuple[float, float]] | None:
    ring_edges = [_ring_index_of(edge, edge_map) for edge in eaves]
    polyline: list[tuple[float, float]] = []
    for ring_i in ring_edges:
        start = pts[ring_i]
        end = pts[next_idx[ring_i]]
        last = polyline[-1] if polyline else None
        if last is None:
            polyline.append(start)
            polyline.append(end)
            continue
        to_start = math.hypot(last[0] - start[0], last[1] - start[1])
        to_end = math.hypot(last[0] - end[0], last[1] - end[1])
        if to_start <= _XY_TOL:
            polyline.append(end)
        elif to_end <= _XY_TOL:
            polyline.append(start)
        else:
            return None
    return polyline if len(polyline) >= 3 else None


def _edge_plane(
    start: tuple[float, float], end: tuple[float, float], pitch: float
) -> tuple[float, float, float] | None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-18 or pitch >= 90.0:
        return None
    nx, ny = -dy / length, dx / length
    slope = math.tan(math.radians(pitch))
    a, b = slope * nx, slope * ny
    return a, b, -a * start[0] - b * start[1]


def _wrap_plane(
    pts: list[tuple[float, float]], pitch: float
) -> tuple[float, float, float] | None:
    if len(pts) < 3 or pitch >= 90.0:
        return None
    start, end = pts[0], pts[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return None
    inx = 0.0
    iny = 0.0
    for i in range(len(pts) - 1):
        ex = pts[i + 1][0] - pts[i][0]
        ey = pts[i + 1][1] - pts[i][1]
        elen = math.hypot(ex, ey)
        if elen < 1e-18:
            continue
        inx += -ey / elen
        iny += ex / elen
    px, py = -dy / chord, dx / chord
    if inx * px + iny * py < 0.0:
        px, py = -px, -py
    slope = math.tan(math.radians(pitch))
    a, b = slope * px, slope * py
    return a, b, -a * start[0] - b * start[1]


def _intersect_three_planes(
    p: tuple[float, float, float],
    q: tuple[float, float, float],
    r: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    a1, b1, c1 = p
    a2, b2, c2 = q
    a3, b3, c3 = r
    a11, a12 = a1 - a2, b1 - b2
    a21, a22 = a1 - a3, b1 - b3
    rhs1, rhs2 = c2 - c1, c3 - c1
    det = a11 * a22 - a12 * a21
    if abs(det) < _DET_TOL:
        return None
    x = (rhs1 * a22 - a12 * rhs2) / det
    y = (a11 * rhs2 - rhs1 * a21) / det
    z = a1 * x + b1 * y + c1
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        return None
    return x, y, z
