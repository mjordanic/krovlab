"""A project is one or more cells roofed through :func:`krovlab.roof.roof`.

Each cell is one footprint at one eave height. ``project`` roofs them
independently, refuses an empty list, overlapping plan regions, and
disagreeing shared edges, and returns one value: per-cell roofs, faces
that name cell and edge, summed covering, and ridge height as the
highest point above datum. Shared walls are coincident geometry.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from krovlab._input import (
    _ORIENT_M2,
    Pitch,
    _on_segment,
    _same_point,
)
from krovlab._input import (
    _orient as _orient_points,
)
from krovlab._input import (
    _point_in_ring as _locate_in_ring,
)
from krovlab._input import (
    _signed_area as _ring_area,
)
from krovlab.roof import Arc, Face, Failure, Node, Roof, Validity, roof

_EAVE_HEIGHT_TOL_M = 1e-9
"""Metres. Shared pitched edges at this gap are treated as one height."""


@dataclass(frozen=True)
class Cell:
    """One footprint roofed as one roof.

    The same arguments :func:`roof` takes, plus an eave height for this
    cell. There is no join to another cell — shared walls are coincident
    geometry, detected later.
    """

    footprint: list[tuple[float, float]]
    """Plan vertices ``(x, y)`` in metres. Either winding is accepted."""

    pitch: Pitch | list[Pitch]
    """One slope for every face of this cell, or one value per edge."""

    holes: list[list[tuple[float, float]]] | None = None
    """Interior rings this cell does not cover, or ``None``."""

    overhang: float = 0.0
    """Eaves projection in metres. Zero is the same as omitting it."""

    eave_height: float = 0.0
    """Metres above datum of this cell's eave plane. Zero is omitting it."""

    knee_height: float | list[float] = 0.0
    """Metres of vertical wall on an edge before that edge's pitch begins.

    Zero on every edge is the same as omitting it. A list is one value
    per edge of this cell.
    """

    wrap: list[list[int]] | None = None
    """Consecutive edge groups to treat as one plane, or ``None``.

    Empty or omitted is the existing skeleton of this cell.
    """

    gambrel: Sequence[tuple[Pitch, Pitch, float] | None] | None = None
    """Optional barn break per edge: steep pitch, shallow pitch, break height.

    Break height is metres above this cell's eave. ``None`` or omitting
    it is a single pitch per wall.
    """


@dataclass(frozen=True)
class ProjectFace:
    """A roof face that names which cell and which edge of that cell."""

    cell_index: int
    """Index of the cell in the list passed to :func:`project`."""

    edge_index: int
    """Index of the edge in that cell's ring, as :attr:`Face.edge_index`."""

    pitch: float
    """Angle from horizontal, in degrees."""

    plan_area: float
    """Area of the face projected onto the horizontal, square metres."""

    sloped_area: float
    """True surface area (``plan_area / cos(pitch)``), square metres."""

    node_indices: tuple[int, ...]
    """``Project.nodes`` indices walking the face boundary, eave first."""

    eave_indices: tuple[int, ...] = ()
    """Caller-edge indices this face drains to. Empty means ``(edge_index,)``.

    Copied from the cell's :class:`~krovlab.roof.Face` so a wrap still
    names every consecutive eave after cells are concatenated.
    """


@dataclass(frozen=True)
class Project:
    """The roofs of one building, made of one or more cells."""

    roofs: tuple[Roof, ...]
    """One roof per cell, already lifted by that cell's eave height."""

    nodes: tuple[Node, ...]
    """Concatenated vertices of every cell, in cell order."""

    faces: tuple[ProjectFace, ...]
    """Every face, each naming its cell and that cell's edge."""

    arcs: tuple[Arc, ...]
    """Eaves, hips, valleys, ridges and verges of every cell.

    ``start`` and ``end`` index :attr:`nodes`.
    """

    ridge_height: float
    """Highest node on any cell, metres above datum."""

    total_sloped_area: float
    """Sum of every cell's covering area."""

    validity: Validity
    """True when every cell is a terrain.

    Overlap and shared-edge disagreement are Failures, not flags.
    """


def project(cells: Sequence[Cell]) -> Project | Failure:
    """Roof each cell and join the results into one project.

    Parameters
    ----------
    cells
        One or more cells. Empty is ``empty``. Two cells whose roofed
        regions overlap in plan is ``overlap``. A shared edge that is a
        gable on one cell and pitched on the other is ``gable_versus_pitch``.
        A pitched shared edge at two eave heights is ``unequal_eave_height``.
        A cell that ``roof`` refuses is that same Failure.

    Returns
    -------
    Project
        Per-cell roofs, faces with cell and edge indices, summed sloped
        area, ridge height as the max above datum, and a validity result
        that is a terrain when every cell is. A party wall (both gables)
        is not counted twice as eaves. Two pitched shared eaves at the
        same height are one valley.
    Failure
        Named refusal. Nothing this function accepts raises.
    """
    if len(cells) == 0:
        return Failure(
            kind="empty",
            reason="a project needs at least one cell",
        )
    roofs: list[Roof] = []
    for cell in cells:
        built = roof(
            cell.footprint,
            cell.pitch,
            holes=cell.holes,
            overhang=cell.overhang,
            eave_height=cell.eave_height,
            knee_height=cell.knee_height,
            wrap=cell.wrap,
            gambrel=cell.gambrel,
        )
        if isinstance(built, Failure):
            return built
        roofs.append(built)
    for i, cell in enumerate(cells):
        for other in cells[i + 1 :]:
            if _roofed_regions_overlap(
                _open_ring(cell.footprint),
                [_open_ring(hole) for hole in (cell.holes or [])],
                _open_ring(other.footprint),
                [_open_ring(hole) for hole in (other.holes or [])],
            ):
                return Failure(
                    kind="overlap",
                    reason="cells overlap in plan",
                )
    valleys = _shared_edge_agreement(cells, roofs)
    if isinstance(valleys, Failure):
        return valleys
    return _assemble(roofs, valleys)


def _assemble(
    roofs: list[Roof],
    valleys: list[tuple[tuple[float, float], tuple[float, float]]],
) -> Project:
    """Concatenate roofs into one project value, joining shared eaves."""
    nodes: list[Node] = []
    faces: list[ProjectFace] = []
    arcs: list[Arc] = []
    reasons: list[str] = []
    for index, built in enumerate(roofs):
        offset = len(nodes)
        nodes.extend(built.nodes)
        faces.extend(_project_faces(index, offset, built.faces))
        arcs.extend(_shifted_arcs(offset, built.arcs))
        if not built.validity.is_terrain:
            reasons.extend(
                f"cell {index}: {reason}" for reason in built.validity.reasons
            )
    return Project(
        roofs=tuple(roofs),
        nodes=tuple(nodes),
        faces=tuple(faces),
        arcs=tuple(_rewrite_valleys(nodes, arcs, valleys)),
        ridge_height=max(node.height for node in nodes),
        total_sloped_area=sum(face.sloped_area for face in faces),
        validity=Validity(is_terrain=not reasons, reasons=tuple(reasons)),
    )


def _project_faces(
    cell_index: int, offset: int, faces: tuple[Face, ...]
) -> list[ProjectFace]:
    return [
        ProjectFace(
            cell_index=cell_index,
            edge_index=face.edge_index,
            pitch=face.pitch,
            plan_area=face.plan_area,
            sloped_area=face.sloped_area,
            node_indices=tuple(i + offset for i in face.node_indices),
            eave_indices=face.eave_indices,
        )
        for face in faces
    ]


def _shifted_arcs(offset: int, arcs: tuple[Arc, ...]) -> list[Arc]:
    return [
        Arc(
            start=arc.start + offset,
            end=arc.end + offset,
            kind=arc.kind,
            length=arc.length,
        )
        for arc in arcs
    ]


def _shared_edge_agreement(
    cells: Sequence[Cell], roofs: list[Roof]
) -> list[tuple[tuple[float, float], tuple[float, float]]] | Failure:
    """Party walls pass; pitched matches become valleys; the rest fail."""
    valleys: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i, cell in enumerate(cells):
        for ei, (a0, a1) in enumerate(_outer_edges(cell.footprint)):
            for j, other in enumerate(cells[i + 1 :], start=i + 1):
                for ej, (b0, b1) in enumerate(_outer_edges(other.footprint)):
                    if not _segments_coincide(a0, a1, b0, b1):
                        continue
                    gable_a = _edge_is_gable(roofs[i], ei)
                    gable_b = _edge_is_gable(roofs[j], ej)
                    if gable_a and gable_b:
                        continue
                    if gable_a or gable_b:
                        return Failure(
                            kind="gable_versus_pitch",
                            reason=(
                                "a shared edge is a gable on one cell and "
                                "pitched on the other"
                            ),
                        )
                    if abs(cell.eave_height - other.eave_height) > _EAVE_HEIGHT_TOL_M:
                        return Failure(
                            kind="unequal_eave_height",
                            reason=("a pitched shared edge has unequal eave heights"),
                        )
                    valleys.append((a0, a1))
    return valleys


def _outer_edges(
    ring: list[tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    pts = _open_ring(ring)
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n)]


def _edge_is_gable(built: Roof, edge_index: int) -> bool:
    return all(face.edge_index != edge_index for face in built.faces)


def _segments_coincide(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    """True when ab and cd are the same segment to vertex tolerance."""
    if _same_point(a, b) or _same_point(c, d):
        return False
    if (_same_point(a, c) and _same_point(b, d)) or (
        _same_point(a, d) and _same_point(b, c)
    ):
        return True
    if (
        abs(_orient_points(a, b, c)) > _ORIENT_M2
        or abs(_orient_points(a, b, d)) > _ORIENT_M2
    ):
        return False
    return (
        _on_segment(a, b, c)
        and _on_segment(a, b, d)
        and _on_segment(c, d, a)
        and _on_segment(c, d, b)
    )


def _rewrite_valleys(
    nodes: list[Node],
    arcs: list[Arc],
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[Arc]:
    """Drop both shared eaves and count the inner gutter once as a valley."""
    drop: set[int] = set()
    added: list[Arc] = []
    for segment in segments:
        hits = [
            i
            for i, arc in enumerate(arcs)
            if i not in drop
            and arc.kind == "eave"
            and _arc_on_segment(arc, nodes, segment[0], segment[1])
        ]
        if len(hits) < 2:
            continue
        first = arcs[hits[0]]
        added.append(
            Arc(
                start=first.start,
                end=first.end,
                kind="valley",
                length=first.length,
            )
        )
        drop.update(hits)
    return [arc for i, arc in enumerate(arcs) if i not in drop] + added


def _arc_on_segment(
    arc: Arc,
    nodes: list[Node],
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    start = nodes[arc.start]
    end = nodes[arc.end]
    return _point_on_segment((start.x, start.y), a, b) and _point_on_segment(
        (end.x, end.y), a, b
    )


def _point_on_segment(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    if abs(_orient_points(a, b, p)) > _ORIENT_M2:
        return False
    return _on_segment(a, b, p)


def _open_ring(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop a closing duplicate of the first vertex, if present."""
    pts = list(ring)
    if len(pts) >= 2 and pts[0] == pts[-1]:
        return pts[:-1]
    return pts


def _roofed_regions_overlap(
    outer_a: list[tuple[float, float]],
    holes_a: list[list[tuple[float, float]]],
    outer_b: list[tuple[float, float]],
    holes_b: list[list[tuple[float, float]]],
) -> bool:
    """True when two roofed regions (outer minus holes) share interior."""
    if _rings_properly_cross(outer_a, outer_b):
        return True
    if _any_vertex_inside(outer_a, holes_a, outer_b, holes_b):
        return True
    if _any_vertex_inside(outer_b, holes_b, outer_a, holes_a):
        return True
    sample_a = _interior_point(outer_a, holes_a)
    if sample_a is not None and _in_roofed(*sample_a, outer_b, holes_b) == "in":
        return True
    sample_b = _interior_point(outer_b, holes_b)
    return sample_b is not None and _in_roofed(*sample_b, outer_a, holes_a) == "in"


def _any_vertex_inside(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    other_outer: list[tuple[float, float]],
    other_holes: list[list[tuple[float, float]]],
) -> bool:
    for x, y in outer:
        if _in_roofed(x, y, other_outer, other_holes) == "in":
            return True
    for hole in holes:
        for x, y in hole:
            if _in_roofed(x, y, other_outer, other_holes) == "in":
                return True
    return False


def _in_roofed(
    x: float,
    y: float,
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> str:
    """``"in"``, ``"on"``, or ``"out"`` of the roofed region."""
    loc = _locate_in_ring(x, y, outer)
    if loc == "out":
        return "out"
    for hole in holes:
        hole_loc = _locate_in_ring(x, y, hole)
        if hole_loc == "in":
            return "out"
        if hole_loc == "on":
            return "on"
    return loc


def _interior_point(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> tuple[float, float] | None:
    """A point strictly in the roofed region, or ``None``."""
    n = len(outer)
    cx = sum(p[0] for p in outer) / n
    cy = sum(p[1] for p in outer) / n
    if _in_roofed(cx, cy, outer, holes) == "in":
        return (cx, cy)
    inward = 1.0 if _ring_area(outer) > 0.0 else -1.0
    for i in range(n):
        ax, ay = outer[i]
        bx, by = outer[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-12:
            continue
        nx, ny = -dy / length * inward, dx / length * inward
        px = (ax + bx) / 2.0 + nx * 1e-4
        py = (ay + by) / 2.0 + ny * 1e-4
        if _in_roofed(px, py, outer, holes) == "in":
            return (px, py)
    return None


def _rings_properly_cross(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> bool:
    """True if an edge of ``a`` properly crosses an edge of ``b``."""
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
    """True if ab and cd cross at a point interior to both segments."""
    orient_tol = 1e-12
    o1 = _orient_points(a, b, c)
    o2 = _orient_points(a, b, d)
    o3 = _orient_points(c, d, a)
    o4 = _orient_points(c, d, b)
    return (
        (o1 > orient_tol and o2 < -orient_tol) or (o1 < -orient_tol and o2 > orient_tol)
    ) and (
        (o3 > orient_tol and o4 < -orient_tol) or (o3 < -orient_tol and o4 > orient_tol)
    )
