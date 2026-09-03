"""Named roof properties, independent of the production validity checker.

Each function raises ``AssertionError`` with a message that starts with
the property name, so a failure tells you which invariant broke. The
checks use shapely as a second opinion; they do not call ``krovlab``
internals. Later tickets reuse these functions as-is.
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon  # type: ignore[import-untyped]

from krovlab import Roof

AREA_TOL = 1e-4
"""Square metres. Loose enough for generated polygons, tight for worked examples."""

PLANAR_TOL_M = 1e-6
"""Metres of point-to-plane distance allowed before a face is warped."""

HEIGHT_TOL_M = 1e-6
"""Metres. Heights below this are at the eave."""

SLOPE_TOL = 1e-9
"""Dimensionless. Sloped area may undershoot plan area by this fraction."""


def plan_areas_sum_to_footprint_area(
    built: Roof, footprint: list[tuple[float, float]]
) -> None:
    """Face plan areas sum to the footprint area — nothing unroofed or doubled."""
    footprint_area = Polygon(footprint).area
    total = sum(face.plan_area for face in built.faces)
    assert math.isclose(total, footprint_area, rel_tol=0.0, abs_tol=AREA_TOL), (
        "plan areas sum to footprint area: "
        f"faces sum to {total} m², footprint is {footprint_area} m²"
    )
    for face in built.faces:
        poly = Polygon(
            [(built.nodes[i].x, built.nodes[i].y) for i in face.node_indices]
        )
        assert math.isclose(
            face.plan_area, poly.area, rel_tol=0.0, abs_tol=AREA_TOL
        ), (
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


def _plane_height(
    pts: list[tuple[float, float, float]], x: float, y: float
) -> float:
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


def roof_is_a_terrain(built: Roof, footprint: list[tuple[float, float]]) -> None:
    """Sampled plan points inside the footprint have exactly one height."""
    poly = Polygon(footprint)
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
        for face in built.faces:
            face_poly = Polygon(
                [(built.nodes[i].x, built.nodes[i].y) for i in face.node_indices]
            )
            if face_poly.covers(Point(x, y)):
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
                "roof is a terrain: "
                f"point ({x:.4f}, {y:.4f}) has heights {heights}"
            )


def drainage_runs_to_each_faces_own_eave(
    built: Roof, footprint: list[tuple[float, float]]
) -> None:
    """Steepest descent on every face points toward that face's own eave.

    The eave is the one named by ``face.edge_index`` on the caller's
    footprint, not whichever footprint edge happens to be nearest.
    """
    n = len(footprint)
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
        # Inward: from this face's eave into the face (and so into the building).
        a = footprint[face.edge_index]
        b = footprint[(face.edge_index + 1) % n]
        mx, my = 0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])
        nodes = [built.nodes[i] for i in face.node_indices]
        cx = sum(p.x for p in nodes) / len(nodes)
        cy = sum(p.y for p in nodes) / len(nodes)
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


def _closest_footprint_vertex(
    footprint: list[tuple[float, float]], x: float, y: float
) -> int:
    return min(
        range(len(footprint)),
        key=lambda i: math.hypot(footprint[i][0] - x, footprint[i][1] - y),
    )


def arc_classification_matches_geometry(
    built: Roof, footprint: list[tuple[float, float]]
) -> None:
    """Ridges are horizontal; hips rise from convex corners; valleys from reflex."""
    signed = 0.0
    n = len(footprint)
    for i in range(n):
        x1, y1 = footprint[i]
        x2, y2 = footprint[(i + 1) % n]
        signed += x1 * y2 - x2 * y1
    ccw = signed > 0.0
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
            assert a.height <= HEIGHT_TOL_M and b.height <= HEIGHT_TOL_M, (
                "arc classification matches geometry: "
                f"eave between nodes {arc.start} and {arc.end} leaves the eave plane"
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
                corner = _closest_footprint_vertex(footprint, end.x, end.y)
                vx, vy = footprint[corner]
                assert math.hypot(end.x - vx, end.y - vy) <= HEIGHT_TOL_M * 10, (
                    "arc classification matches geometry: "
                    f"{arc.kind} meets the eave away from a footprint corner"
                )
                convex = _vertex_is_convex(footprint, corner, ccw)
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
