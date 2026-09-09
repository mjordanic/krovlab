"""Named roof properties, independent of the production validity checker.

Each function raises ``AssertionError`` with a message that starts with
the property name, so a failure tells you which invariant broke. The
checks use shapely as a second opinion; they do not call ``krovlab``
internals. Later tickets reuse these functions as-is.
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon  # type: ignore[import-untyped]

from krovlab import Face, Roof

AREA_TOL = 1e-4
"""Square metres. Loose enough for generated polygons, tight for worked examples."""

PLANAR_TOL_M = 1e-6
"""Metres of point-to-plane distance allowed before a face is warped."""

HEIGHT_TOL_M = 1e-6
"""Metres. Heights below this are at the eave."""

SLOPE_TOL = 1e-9
"""Dimensionless. Sloped area may undershoot plan area by this fraction."""


def plan_areas_sum_to_footprint_area(
    built: Roof,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> None:
    """Face plan areas sum to the footprint area — nothing unroofed or doubled."""
    footprint_area = Polygon(footprint, holes or []).area
    total = sum(face.plan_area for face in built.faces)
    assert math.isclose(total, footprint_area, rel_tol=0.0, abs_tol=AREA_TOL), (
        "plan areas sum to footprint area: "
        f"faces sum to {total} m², footprint is {footprint_area} m²"
    )
    for face in built.faces:
        poly = Polygon(
            [(built.nodes[i].x, built.nodes[i].y) for i in face.node_indices]
        )
        assert math.isclose(face.plan_area, poly.area, rel_tol=0.0, abs_tol=AREA_TOL), (
            "plan areas sum to footprint area: "
            f"face {face.edge_index} reports {face.plan_area} m², "
            f"shapely measures {poly.area} m²"
        )


def _plane_normal(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Unit normal of the plane through three points, or None if collinear."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.hypot(nx, ny, nz)
    if length < 1e-18:
        return None
    return nx / length, ny / length, nz / length


def every_face_is_planar(built: Roof) -> None:
    """Every face's vertices lie on one plane."""
    for face in built.faces:
        pts = [
            (built.nodes[i].x, built.nodes[i].y, built.nodes[i].height)
            for i in face.node_indices
        ]
        if len(pts) < 3:
            raise AssertionError(
                f"every face is planar: face {face.edge_index} has {len(pts)} vertices"
            )
        normal = None
        origin = pts[0]
        for i in range(1, len(pts) - 1):
            normal = _plane_normal(origin, pts[i], pts[i + 1])
            if normal is not None:
                break
        assert normal is not None, (
            f"every face is planar: face {face.edge_index} is collinear"
        )
        nx, ny, nz = normal
        for p in pts[1:]:
            dist = abs(
                nx * (p[0] - origin[0])
                + ny * (p[1] - origin[1])
                + nz * (p[2] - origin[2])
            )
            assert dist <= PLANAR_TOL_M, (
                "every face is planar: "
                f"face {face.edge_index} has a vertex {dist} m off the plane"
            )


def sloped_area_is_at_least_plan_area(built: Roof) -> None:
    """Sloped area is at least plan area; equal only as pitch approaches 0."""
    for face in built.faces:
        slack = SLOPE_TOL * max(face.plan_area, 1.0)
        assert face.sloped_area + slack >= face.plan_area, (
            "sloped area is at least plan area: "
            f"face {face.edge_index} has sloped {face.sloped_area} m² "
            f"< plan {face.plan_area} m²"
        )
        if face.pitch > 1.0 and face.plan_area > AREA_TOL:
            assert face.sloped_area > face.plan_area, (
                "sloped area is at least plan area: "
                f"face {face.edge_index} at pitch {face.pitch}° "
                "should be strictly larger"
            )


def _plane_height(pts: list[tuple[float, float, float]], x: float, y: float) -> float:
    """Height on the face plane at a plan point. pts must not be collinear."""
    origin = pts[0]
    normal = None
    for i in range(1, len(pts) - 1):
        normal = _plane_normal(origin, pts[i], pts[i + 1])
        if normal is not None:
            break
    assert normal is not None
    nx, ny, nz = normal
    # nx(x-x0) + ny(y-y0) + nz(z-z0) = 0
    if abs(nz) < 1e-18:
        return origin[2]
    return origin[2] - (nx * (x - origin[0]) + ny * (y - origin[1])) / nz


def roof_is_a_terrain(
    built: Roof,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> None:
    """Sampled plan points inside the footprint have exactly one height."""
    poly = Polygon(footprint, holes or [])
    minx, miny, maxx, maxy = poly.bounds
    nx_s, ny_s = 7, 7
    samples: list[tuple[float, float]] = []
    for i in range(nx_s):
        for j in range(ny_s):
            x = minx + (i + 0.5) / nx_s * (maxx - minx)
            y = miny + (j + 0.5) / ny_s * (maxy - miny)
            if poly.covers(Point(x, y)):
                samples.append((x, y))
    centroid = poly.centroid
    if poly.covers(centroid):
        samples.append((centroid.x, centroid.y))
    assert samples, "roof is a terrain: no sample points landed inside the footprint"
    for x, y in samples:
        heights: list[float] = []
        sample = Point(x, y)
        for face in built.faces:
            face_poly = Polygon(
                [(built.nodes[i].x, built.nodes[i].y) for i in face.node_indices]
            )
            # GEOS `covers` can miss a point that sits on a verge to ~1e-16 m.
            if face_poly.covers(sample) or face_poly.distance(sample) <= HEIGHT_TOL_M:
                pts = [
                    (built.nodes[i].x, built.nodes[i].y, built.nodes[i].height)
                    for i in face.node_indices
                ]
                heights.append(_plane_height(pts, x, y))
        assert heights, (
            "roof is a terrain: "
            f"point ({x:.4f}, {y:.4f}) is in the footprint but on no face"
        )
        ref = heights[0]
        for h in heights[1:]:
            assert math.isclose(h, ref, rel_tol=0.0, abs_tol=HEIGHT_TOL_M * 10), (
                f"roof is a terrain: point ({x:.4f}, {y:.4f}) has heights {heights}"
            )


def _caller_rings(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None,
) -> list[list[tuple[float, float]]]:
    return [footprint, *(holes or [])]


def _edge_endpoints(
    rings: list[list[tuple[float, float]]], edge_index: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    remaining = edge_index
    for ring in rings:
        n = len(ring)
        if remaining < n:
            return ring[remaining], ring[(remaining + 1) % n]
        remaining -= n
    raise AssertionError(
        f"drainage to own eave: edge_index {edge_index} is past the footprint edges"
    )


def _face_eave_indices(face: Face) -> tuple[int, ...]:
    if face.eave_indices:
        return face.eave_indices
    return (face.edge_index,)


def _nearest_on_segments(
    x: float,
    y: float,
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> tuple[float, float]:
    best = segments[0][0]
    best_d = float("inf")
    for a, b in segments:
        ax, ay = a
        bx, by = b
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        if ab2 < 1e-24:
            px, py = ax, ay
        else:
            t = ((x - ax) * abx + (y - ay) * aby) / ab2
            t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
            px, py = ax + t * abx, ay + t * aby
        dist = math.hypot(x - px, y - py)
        if dist < best_d:
            best_d = dist
            best = (px, py)
    return best


def drainage_runs_to_each_faces_own_eave(
    built: Roof,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> None:
    """Steepest descent on every face points toward that face's own eave.

    The eave is the footprint edges named by ``face.eave_indices`` (or
    ``face.edge_index``), the union of wrapped edges when a face wraps.
    """
    rings = _caller_rings(footprint, holes)
    for face in built.faces:
        pts = [
            (built.nodes[i].x, built.nodes[i].y, built.nodes[i].height)
            for i in face.node_indices
        ]
        origin = pts[0]
        normal = None
        for i in range(1, len(pts) - 1):
            normal = _plane_normal(origin, pts[i], pts[i + 1])
            if normal is not None:
                break
        assert normal is not None, (
            f"drainage to own eave: face {face.edge_index} is collinear"
        )
        nx, ny, nz = normal
        # z = z0 - (nx(x-x0) + ny(y-y0)) / nz   ⇒  grad(z) = (-nx/nz, -ny/nz)
        if abs(nz) < 1e-18:
            continue
        grad_x, grad_y = -nx / nz, -ny / nz
        eave_ids = _face_eave_indices(face)
        segments = [_edge_endpoints(rings, idx) for idx in eave_ids]
        poly = Polygon(
            [(built.nodes[i].x, built.nodes[i].y) for i in face.node_indices]
        )
        cx, cy = poly.centroid.x, poly.centroid.y
        mx, my = _nearest_on_segments(cx, cy, segments)
        inward_x, inward_y = cx - mx, cy - my
        # Height must increase as we walk inward from this eave, so the
        # steepest descent (-grad) points back toward the eave.
        assert grad_x * inward_x + grad_y * inward_y > 0.0, (
            "drainage to own eave: "
            f"face {face.edge_index} does not drain toward footprint edge "
            f"{face.edge_index}"
        )


def _turn_cross(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> float:
    """Twice the signed area of triangle abc. Positive is a left (CCW) turn."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _vertex_is_convex(
    footprint: list[tuple[float, float]], index: int, ccw: bool
) -> bool:
    n = len(footprint)
    a = footprint[(index - 1) % n]
    b = footprint[index]
    c = footprint[(index + 1) % n]
    cross = _turn_cross(a, b, c)
    return cross > 0.0 if ccw else cross < 0.0


def _closest_corner(
    rings: list[list[tuple[float, float]]], x: float, y: float
) -> tuple[int, int]:
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


def arc_classification_matches_geometry(
    built: Roof,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> None:
    """Ridges and knee eaves horizontal; hips convex; valleys reflex;
    verges on walls.
    """
    rings = _caller_rings(footprint, holes)
    n_edges = sum(len(ring) for ring in rings)
    for arc in built.arcs:
        a, b = built.nodes[arc.start], built.nodes[arc.end]
        if arc.kind == "ridge":
            assert min(a.height, b.height) > HEIGHT_TOL_M, (
                "arc classification matches geometry: "
                f"ridge between nodes {arc.start} and {arc.end} touches the eave"
            )
            assert abs(a.height - b.height) <= HEIGHT_TOL_M, (
                "arc classification matches geometry: "
                f"ridge between nodes {arc.start} and {arc.end} is not horizontal"
            )
        elif arc.kind == "eave":
            assert abs(a.height - b.height) <= HEIGHT_TOL_M, (
                "arc classification matches geometry: "
                f"eave between nodes {arc.start} and {arc.end} is not horizontal"
            )
            on_wall = all(
                any(
                    _point_on_segment(
                        end.x, end.y, *_edge_endpoints(rings, idx), HEIGHT_TOL_M * 10
                    )
                    for idx in range(n_edges)
                )
                for end in (a, b)
            )
            assert on_wall, (
                "arc classification matches geometry: "
                f"eave between nodes {arc.start} and {arc.end} "
                "does not lie on a footprint edge"
            )
        elif arc.kind == "verge":
            on_wall = all(
                any(
                    _point_on_segment(
                        end.x, end.y, *_edge_endpoints(rings, idx), HEIGHT_TOL_M * 10
                    )
                    for idx in range(n_edges)
                )
                for end in (a, b)
            )
            assert on_wall, (
                "arc classification matches geometry: "
                f"verge between nodes {arc.start} and {arc.end} "
                "does not lie on a wall"
            )
        elif arc.kind in ("hip", "valley"):
            # Sloping. The first segment of a hip/valley meets a footprint
            # corner; later segments run between skeleton nodes of different
            # height. Only the eave-touching end is constrained to a corner.
            assert abs(a.height - b.height) > HEIGHT_TOL_M, (
                "arc classification matches geometry: "
                f"{arc.kind} between nodes {arc.start} and {arc.end} is "
                "horizontal (that would be a ridge)"
            )
            for end in (a, b):
                if end.height > HEIGHT_TOL_M:
                    continue
                ri, corner = _closest_corner(rings, end.x, end.y)
                ring = rings[ri]
                vx, vy = ring[corner]
                assert math.hypot(end.x - vx, end.y - vy) <= HEIGHT_TOL_M * 10, (
                    "arc classification matches geometry: "
                    f"{arc.kind} meets the eave away from a footprint corner"
                )
                signed = 0.0
                n = len(ring)
                for i in range(n):
                    x1, y1 = ring[i]
                    x2, y2 = ring[(i + 1) % n]
                    signed += x1 * y2 - x2 * y1
                ccw = signed > 0.0
                convex = _vertex_is_convex(ring, corner, ccw)
                if ri > 0:
                    convex = not convex
                if arc.kind == "hip":
                    assert convex, (
                        "arc classification matches geometry: "
                        f"hip rises from reflex corner {corner}"
                    )
                else:
                    assert not convex, (
                        "arc classification matches geometry: "
                        f"valley rises from convex corner {corner}"
                    )
        else:
            raise AssertionError(
                f"arc classification matches geometry: unknown kind {arc.kind!r}"
            )
