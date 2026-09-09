"""A project is one or more cells roofed through :func:`krovlab.roof.roof`.

Each cell is one footprint at one eave height. ``project`` roofs them
independently, refuses an empty list and overlapping plan regions, and
returns one value: per-cell roofs, faces that name cell and edge, summed
covering, and ridge height as the highest point above datum. Shared-wall
agreement is not decided here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from krovlab._input import Pitch
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


@dataclass(frozen=True)
class Cell:
    """One footprint roofed by a single straight skeleton.

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
    """True when every cell is a terrain. Overlap is a Failure, not a flag."""


def project(cells: Sequence[Cell]) -> Project | Failure:
    """Roof each cell and join the results into one project.

    Parameters
    ----------
    cells
        One or more cells. Empty is ``empty``. Two cells whose roofed
        regions overlap in plan is ``overlap``. A cell that ``roof``
        refuses is that same Failure. Shared-edge agreement is not
        checked.

    Returns
    -------
    Project
        Per-cell roofs, faces with cell and edge indices, summed sloped
        area, ridge height as the max above datum, and a validity result
        that is a terrain when every cell is.
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
    return _assemble(roofs)


def _assemble(roofs: list[Roof]) -> Project:
    """Concatenate roofs into one project value."""
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
        arcs=tuple(arcs),
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
        (o1 > orient_tol and o2 < -orient_tol)
        or (o1 < -orient_tol and o2 > orient_tol)
    ) and (
        (o3 > orient_tol and o4 < -orient_tol)
        or (o3 < -orient_tol and o4 > orient_tol)
    )
