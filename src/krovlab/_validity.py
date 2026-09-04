"""Production checks that fill ``Roof.validity``.

These run inside :func:`krovlab.roof.roof` so a caller learns whether the
result is a terrain without running the test suite. They use only the
standard library; shapely stays a test-only second opinion.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from krovlab.roof import Arc, Face, Node, Validity

AREA_TOL = 1e-4
PLANAR_TOL_M = 1e-6
HEIGHT_TOL_M = 1e-6
SLOPE_TOL = 1e-9


def assess(
    nodes: tuple[Node, ...],
    faces: tuple[Face, ...],
    arcs: tuple[Arc, ...],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> Validity:
    """Return the validity of a roof assembled from ``nodes`` / ``faces`` / ``arcs``."""
    from krovlab.roof import Validity

    hole_rings = holes or []
    reasons: list[str] = []
    reasons.extend(_plan_area_reasons(nodes, faces, footprint, hole_rings))
    reasons.extend(_planar_reasons(nodes, faces))
    reasons.extend(_sloped_reasons(faces))
    reasons.extend(_terrain_reasons(nodes, faces, footprint, hole_rings))
    reasons.extend(_drainage_reasons(nodes, faces, footprint, hole_rings))
    reasons.extend(_arc_reasons(nodes, faces, arcs, footprint, hole_rings))
    return Validity(is_terrain=not reasons, reasons=tuple(reasons))


def _area(pts: list[tuple[float, float]]) -> float:
    """Delegate to the single shoelace in ``roof.py``; do not copy it."""
    from krovlab.roof import _signed_area

    return _signed_area(pts)


def _plan_area_reasons(
    nodes: tuple[Node, ...],
    faces: tuple[Face, ...],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[str]:
    footprint_area = abs(_area(footprint)) - sum(abs(_area(h)) for h in holes)
    total = sum(face.plan_area for face in faces)
    if not math.isclose(total, footprint_area, rel_tol=0.0, abs_tol=AREA_TOL):
        return [
            "plan areas sum to footprint area: "
            f"faces sum to {total} m², footprint is {footprint_area} m²"
        ]
    return []


def _xyz(nodes: tuple[Node, ...], index: int) -> tuple[float, float, float]:
    node = nodes[index]
    return node.x, node.y, node.height


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


def _face_normal(
    nodes: tuple[Node, ...], face: Face
) -> tuple[float, float, float] | None:
    pts = [_xyz(nodes, i) for i in face.node_indices]
    origin = pts[0]
    for i in range(1, len(pts) - 1):
        normal = _plane_normal(origin, pts[i], pts[i + 1])
        if normal is not None:
            return normal
    return None


def _planar_reasons(nodes: tuple[Node, ...], faces: tuple[Face, ...]) -> list[str]:
    reasons: list[str] = []
    for face in faces:
        pts = [_xyz(nodes, i) for i in face.node_indices]
        if len(pts) < 3:
            reasons.append(
                f"every face is planar: face {face.edge_index} has {len(pts)} vertices"
            )
            continue
        normal = _face_normal(nodes, face)
        if normal is None:
            reasons.append(f"every face is planar: face {face.edge_index} is collinear")
            continue
        nx, ny, nz = normal
        origin = pts[0]
        for p in pts[1:]:
            dist = abs(
                nx * (p[0] - origin[0])
                + ny * (p[1] - origin[1])
                + nz * (p[2] - origin[2])
            )
            if dist > PLANAR_TOL_M:
                reasons.append(
                    "every face is planar: "
                    f"face {face.edge_index} has a vertex {dist} m off the plane"
                )
                break
    return reasons


def _sloped_reasons(faces: tuple[Face, ...]) -> list[str]:
    reasons: list[str] = []
    for face in faces:
        slack = SLOPE_TOL * max(face.plan_area, 1.0)
        if face.sloped_area + slack < face.plan_area:
            reasons.append(
                "sloped area is at least plan area: "
                f"face {face.edge_index} has sloped {face.sloped_area} m² "
                f"< plan {face.plan_area} m²"
            )
        elif (
            face.pitch > 1.0
            and face.plan_area > AREA_TOL
            and face.sloped_area <= face.plan_area
        ):
            reasons.append(
                "sloped area is at least plan area: "
                f"face {face.edge_index} at pitch {face.pitch}° "
                "should be strictly larger"
            )
    return reasons


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """True if (x, y) is inside or on the boundary of a closed ring."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (x - xi) ** 2 + (y - yi) ** 2 < 1e-24:
            return True
        # On an edge.
        dx, dy = xj - xi, yj - yi
        cross = (x - xi) * dy - (y - yi) * dx
        if abs(cross) < 1e-12:
            along = (x - xi) * dx + (y - yi) * dy
            if 0.0 <= along <= dx * dx + dy * dy:
                return True
        if yj == yi:
            j = i
            continue
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _plane_height(nodes: tuple[Node, ...], face: Face, x: float, y: float) -> float:
    pts = [_xyz(nodes, i) for i in face.node_indices]
    origin = pts[0]
    normal = _face_normal(nodes, face)
    if normal is None:
        return origin[2]
    nx, ny, nz = normal
    if abs(nz) < 1e-18:
        return origin[2]
    return origin[2] - (nx * (x - origin[0]) + ny * (y - origin[1])) / nz


def _in_footprint(
    x: float,
    y: float,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> bool:
    """True if the point is inside the outer ring and outside every hole."""
    if not _point_in_ring(x, y, footprint):
        return False
    return all(not _point_in_ring(x, y, hole) for hole in holes)


def _centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Polygon centroid; falls back to the vertex mean if area is ~0."""
    n = len(pts)
    a = _area(pts)
    if abs(a) < 1e-18:
        return (
            sum(p[0] for p in pts) / n,
            sum(p[1] for p in pts) / n,
        )
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    # ``_area`` is the 0.5-shoelace, so 6A = 3 * sum(cross) = 3 * 2A.
    return cx / (6.0 * a), cy / (6.0 * a)


def _caller_rings(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    return [footprint, *holes]


def _edge_endpoints(
    rings: list[list[tuple[float, float]]], edge_index: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Caller-edge endpoints. Edges are outer first, then each hole."""
    remaining = edge_index
    for ring in rings:
        n = len(ring)
        if remaining < n:
            return ring[remaining], ring[(remaining + 1) % n]
        remaining -= n
    raise IndexError(f"edge_index {edge_index} is past the footprint edges")


def _terrain_reasons(
    nodes: tuple[Node, ...],
    faces: tuple[Face, ...],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[str]:
    xs = [p[0] for p in footprint]
    ys = [p[1] for p in footprint]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    samples: list[tuple[float, float]] = []
    grid = 7
    for i in range(grid):
        for j in range(grid):
            x = minx + (i + 0.5) / grid * (maxx - minx)
            y = miny + (j + 0.5) / grid * (maxy - miny)
            if _in_footprint(x, y, footprint, holes):
                samples.append((x, y))
    cx, cy = _centroid(footprint)
    if _in_footprint(cx, cy, footprint, holes):
        samples.append((cx, cy))
    for face in faces:
        ring = [(nodes[i].x, nodes[i].y) for i in face.node_indices]
        if len(ring) < 3:
            continue
        fx, fy = _centroid(ring)
        if _in_footprint(fx, fy, footprint, holes):
            samples.append((fx, fy))
    if not samples:
        return ["roof is a terrain: no sample points landed inside the footprint"]
    reasons: list[str] = []
    for x, y in samples:
        heights: list[float] = []
        for face in faces:
            ring = [(nodes[i].x, nodes[i].y) for i in face.node_indices]
            if _point_in_ring(x, y, ring):
                heights.append(_plane_height(nodes, face, x, y))
        if not heights:
            reasons.append(
                "roof is a terrain: "
                f"point ({x:.4f}, {y:.4f}) is in the footprint but on no face"
            )
            continue
        ref = heights[0]
        if any(abs(h - ref) > HEIGHT_TOL_M * 10 for h in heights[1:]):
            reasons.append(
                f"roof is a terrain: point ({x:.4f}, {y:.4f}) has heights {heights}"
            )
    return reasons


def _drainage_reasons(
    nodes: tuple[Node, ...],
    faces: tuple[Face, ...],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[str]:
    """Steepest descent on each face must point toward that face's own eave."""
    rings = _caller_rings(footprint, holes)
    reasons: list[str] = []
    for face in faces:
        normal = _face_normal(nodes, face)
        if normal is None:
            reasons.append(f"drainage to own eave: face {face.edge_index} is collinear")
            continue
        nx, ny, nz = normal
        if abs(nz) < 1e-18:
            reasons.append(f"drainage to own eave: face {face.edge_index} is vertical")
            continue
        # z = z0 - (nx(x-x0)+ny(y-y0))/nz  ⇒  grad(z) = (-nx/nz, -ny/nz)
        grad_x, grad_y = -nx / nz, -ny / nz
        a, b = _edge_endpoints(rings, face.edge_index)
        mx, my = 0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])
        pts = [nodes[i] for i in face.node_indices]
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        inward_x, inward_y = cx - mx, cy - my
        if grad_x * inward_x + grad_y * inward_y <= 0.0:
            reasons.append(
                "drainage to own eave: "
                f"face {face.edge_index} does not drain toward footprint edge "
                f"{face.edge_index}"
            )
    return reasons


def _turn_cross(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _vertex_is_convex(
    footprint: list[tuple[float, float]], index: int, ccw: bool
) -> bool:
    n = len(footprint)
    cross = _turn_cross(
        footprint[(index - 1) % n], footprint[index], footprint[(index + 1) % n]
    )
    return cross > 0.0 if ccw else cross < 0.0


def _closest_corner(
    rings: list[list[tuple[float, float]]], x: float, y: float
) -> tuple[int, int]:
    """Return (ring_index, vertex_index) of the nearest footprint corner."""
    best_ring = 0
    best_vertex = 0
    best_dist = float("inf")
    for ri, ring in enumerate(rings):
        for i, (vx, vy) in enumerate(ring):
            dist = math.hypot(vx - x, vy - y)
            if dist < best_dist:
                best_dist = dist
                best_ring = ri
                best_vertex = i
    return best_ring, best_vertex


def _point_on_segment(
    px: float,
    py: float,
    a: tuple[float, float],
    b: tuple[float, float],
    tol: float,
) -> bool:
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-24:
        return math.hypot(apx, apy) <= tol
    along = (apx * abx + apy * aby) / ab2
    if along < -1e-9 or along > 1.0 + 1e-9:
        return False
    dist = abs(apx * aby - apy * abx) / math.sqrt(ab2)
    return dist <= tol


def _gabled_edge_indices(
    faces: tuple[Face, ...], rings: list[list[tuple[float, float]]]
) -> list[int]:
    n_edges = sum(len(ring) for ring in rings)
    faced = {face.edge_index for face in faces}
    return [i for i in range(n_edges) if i not in faced]


def _on_gabled_edge(
    x: float,
    y: float,
    rings: list[list[tuple[float, float]]],
    gabled: list[int],
    tol: float,
) -> bool:
    return any(
        _point_on_segment(x, y, *_edge_endpoints(rings, idx), tol) for idx in gabled
    )


def _arc_reasons(
    nodes: tuple[Node, ...],
    faces: tuple[Face, ...],
    arcs: tuple[Arc, ...],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[str]:
    rings = _caller_rings(footprint, holes)
    gabled = _gabled_edge_indices(faces, rings)
    reasons: list[str] = []
    for arc in arcs:
        a, b = nodes[arc.start], nodes[arc.end]
        if arc.kind == "ridge":
            if min(a.height, b.height) <= HEIGHT_TOL_M:
                reasons.append(
                    "arc classification matches geometry: "
                    f"ridge between nodes {arc.start} and {arc.end} touches the eave"
                )
            elif abs(a.height - b.height) > HEIGHT_TOL_M:
                reasons.append(
                    "arc classification matches geometry: "
                    f"ridge between nodes {arc.start} and {arc.end} is not horizontal"
                )
        elif arc.kind == "eave":
            if a.height > HEIGHT_TOL_M or b.height > HEIGHT_TOL_M:
                reasons.append(
                    "arc classification matches geometry: "
                    f"eave between nodes {arc.start} and {arc.end} "
                    "leaves the eave plane"
                )
        elif arc.kind == "verge":
            tol = HEIGHT_TOL_M * 10
            if not (
                _on_gabled_edge(a.x, a.y, rings, gabled, tol)
                and _on_gabled_edge(b.x, b.y, rings, gabled, tol)
            ):
                reasons.append(
                    "arc classification matches geometry: "
                    f"verge between nodes {arc.start} and {arc.end} "
                    "does not lie on a gable wall"
                )
        elif arc.kind in ("hip", "valley"):
            if abs(a.height - b.height) <= HEIGHT_TOL_M:
                reasons.append(
                    "arc classification matches geometry: "
                    f"{arc.kind} between nodes {arc.start} and {arc.end} is "
                    "horizontal (that would be a ridge)"
                )
                continue
            for end in (a, b):
                if end.height > HEIGHT_TOL_M:
                    continue
                ri, corner = _closest_corner(rings, end.x, end.y)
                ring = rings[ri]
                vx, vy = ring[corner]
                if math.hypot(end.x - vx, end.y - vy) > HEIGHT_TOL_M * 10:
                    reasons.append(
                        "arc classification matches geometry: "
                        f"{arc.kind} meets the eave away from a footprint corner"
                    )
                    continue
                ccw = _area(ring) > 0.0
                convex = _vertex_is_convex(ring, corner, ccw)
                # A convex hole-polygon corner is reflex for the roofed region.
                if ri > 0:
                    convex = not convex
                if arc.kind == "hip" and not convex:
                    reasons.append(
                        "arc classification matches geometry: "
                        f"hip rises from reflex corner {corner}"
                    )
                if arc.kind == "valley" and convex:
                    reasons.append(
                        "arc classification matches geometry: "
                        f"valley rises from convex corner {corner}"
                    )
        else:
            reasons.append(
                f"arc classification matches geometry: unknown kind {arc.kind!r}"
            )
    return reasons
