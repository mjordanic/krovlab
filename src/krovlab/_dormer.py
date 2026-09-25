"""Clip child roofs onto host faces after cells are roofed.

Not a public seam. ``project`` roofs every cell first, then each dormer
is located by plan overlap onto exactly one face of that cell.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from krovlab._input import (
    _ORIENT_M2,
    _point_in_ring,
    _signed_area,
    check_footprint,
)
from krovlab._input import (
    _orient as _orient_points,
)
from krovlab._validity import _centroid, _plane_height
from krovlab.roof import Face, Failure, Node, Roof, Validity, roof

if TYPE_CHECKING:
    from krovlab.project import Project


@dataclass(frozen=True)
class Placement:
    """A dormer child located on one host face."""

    cell_index: int
    face_index: int
    child: Roof
    ring: list[tuple[float, float]]


def locate_and_build(
    roofs: list[Roof],
    dormers: list[object],
) -> list[Placement] | Failure:
    """Place each dormer on exactly one host face, or name why not."""
    from krovlab.project import Dormer

    placements: list[Placement] = []
    for item in dormers:
        if not isinstance(item, Dormer):
            return Failure(
                kind="degenerate",
                reason="each dormer needs a cell, a plan ring, and a pitch",
            )
        if item.cell_index < 0 or item.cell_index >= len(roofs):
            return Failure(
                kind="dormer_outside",
                reason="a dormer must lie on a host face",
            )
        cleaned = check_footprint(item.footprint)
        if isinstance(cleaned, Failure):
            return cleaned
        host = roofs[item.cell_index]
        located = _host_face(host, cleaned)
        if isinstance(located, Failure):
            return located
        child = roof(cleaned, item.pitch)
        if isinstance(child, Failure):
            return child
        placements.append(
            Placement(
                cell_index=item.cell_index,
                face_index=located,
                child=child,
                ring=cleaned,
            )
        )
    return placements


def apply_placements(
    built: Project,
    roofs: list[Roof],
    placements: list[Placement],
) -> Project:
    """Subtract openings, lift children onto host planes, and mark non-terrain."""
    from krovlab.project import Project, _project_faces, _shifted_arcs

    nodes = list(built.nodes)
    faces = list(built.faces)
    arcs = list(built.arcs)
    index_of: dict[tuple[int, int], int] = {}
    cursor = 0
    for cell_index, cell_roof in enumerate(roofs):
        for face_index in range(len(cell_roof.faces)):
            index_of[(cell_index, face_index)] = cursor
            cursor += 1

    holes_for: dict[int, list[list[int]]] = {}
    for place in placements:
        pidx = index_of[(place.cell_index, place.face_index)]
        host_face = faces[pidx]
        host_roof = roofs[place.cell_index]
        source = host_roof.faces[place.face_index]
        hole_ids: list[int] = []
        for x, y in place.ring:
            hole_ids.append(len(nodes))
            nodes.append(Node(x, y, _plane_height(host_roof.nodes, source, x, y)))
        holes_for.setdefault(pidx, []).append(hole_ids)

        opening_plan = abs(_signed_area(place.ring))
        cos_pitch = math.cos(math.radians(host_face.pitch))
        opening_sloped = opening_plan / cos_pitch if cos_pitch != 0.0 else opening_plan
        faces[pidx] = replace(
            host_face,
            plan_area=host_face.plan_area - opening_plan,
            sloped_area=host_face.sloped_area - opening_sloped,
        )

        offset = len(nodes)
        nodes.extend(_lifted_nodes(place.child, host_roof.nodes, source))
        faces.extend(_project_faces(place.cell_index, offset, place.child.faces))
        arcs.extend(_shifted_arcs(offset, place.child.arcs))

    for pidx, hole_rings in holes_for.items():
        face = faces[pidx]
        cycle = list(face.node_indices)
        for hole in hole_rings:
            cycle = _keyhole(cycle, hole, nodes)
        faces[pidx] = replace(face, node_indices=tuple(cycle))

    reasons = list(built.validity.reasons)
    reasons.append("a project with dormers is not a single terrain")
    return Project(
        roofs=built.roofs,
        nodes=tuple(nodes),
        faces=tuple(faces),
        arcs=tuple(arcs),
        ridge_height=max(node.height for node in nodes),
        total_sloped_area=sum(face.sloped_area for face in faces),
        validity=Validity(is_terrain=False, reasons=tuple(reasons)),
    )


def _host_face(host: Roof, ring: list[tuple[float, float]]) -> int | Failure:
    """Return the unique host-face index that contains ``ring`` in plan."""
    inside: list[int] = []
    overlap: list[int] = []
    for index, face in enumerate(host.faces):
        polygon = [(host.nodes[i].x, host.nodes[i].y) for i in face.node_indices]
        relation = _ring_on_face(ring, polygon)
        if relation == "in":
            inside.append(index)
        elif relation == "overlap":
            overlap.append(index)
    if len(inside) == 1 and not overlap:
        return inside[0]
    if len(inside) > 1 or len(overlap) > 1 or (inside and overlap):
        return Failure(
            kind="dormer_two_faces",
            reason="a dormer must sit on a single host face",
        )
    return Failure(
        kind="dormer_outside",
        reason="a dormer must lie on a host face",
    )


def _ring_on_face(
    inner: list[tuple[float, float]], outer: list[tuple[float, float]]
) -> str:
    """``"in"``, ``"overlap"``, or ``"out"`` of the face's plan polygon."""
    verts = [_point_in_ring(x, y, outer) for x, y in inner]
    cx, cy = _centroid(inner)
    centre = _point_in_ring(cx, cy, outer)
    if all(loc != "out" for loc in verts) and centre == "in":
        return "in"
    if any(loc == "in" for loc in verts) or centre == "in":
        return "overlap"
    if _rings_properly_cross(inner, outer):
        return "overlap"
    return "out"


def _rings_properly_cross(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> bool:
    n, m = len(a), len(b)
    for i in range(n):
        p, q = a[i], a[(i + 1) % n]
        for j in range(m):
            r, s = b[j], b[(j + 1) % m]
            if _segments_properly_cross(p, q, r, s):
                return True
    return False


def _segments_properly_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = _orient_points(a, b, c)
    o2 = _orient_points(a, b, d)
    o3 = _orient_points(c, d, a)
    o4 = _orient_points(c, d, b)
    return (
        (o1 > _ORIENT_M2 and o2 < -_ORIENT_M2) or (o1 < -_ORIENT_M2 and o2 > _ORIENT_M2)
    ) and (
        (o3 > _ORIENT_M2 and o4 < -_ORIENT_M2) or (o3 < -_ORIENT_M2 and o4 > _ORIENT_M2)
    )


def _lifted_nodes(
    child: Roof, host_nodes: tuple[Node, ...], host_face: Face
) -> list[Node]:
    return [
        Node(
            node.x,
            node.y,
            node.height + _plane_height(host_nodes, host_face, node.x, node.y),
        )
        for node in child.nodes
    ]


def _keyhole(outer: list[int], hole: list[int], nodes: list[Node]) -> list[int]:
    """Join a hole to ``outer`` with a bridge so 3D can ear-clip a host opening."""
    if len(outer) < 3 or len(hole) < 3:
        return outer
    outer_pts = [(nodes[i].x, nodes[i].y) for i in outer]
    hole_pts = [(nodes[i].x, nodes[i].y) for i in hole]
    if _signed_area(outer_pts) * _signed_area(hole_pts) > 0.0:
        hole = list(reversed(hole))
    best_o = 0
    best_h = 0
    best_d = float("inf")
    for i, oi in enumerate(outer):
        for j, hj in enumerate(hole):
            dist = math.hypot(nodes[oi].x - nodes[hj].x, nodes[oi].y - nodes[hj].y)
            if dist < best_d:
                best_d = dist
                best_o = i
                best_h = j
    outer_rot = outer[best_o:] + outer[:best_o]
    hole_rot = hole[best_h:] + hole[:best_h]
    return [*outer_rot, outer_rot[0], *hole_rot, hole_rot[0]]
