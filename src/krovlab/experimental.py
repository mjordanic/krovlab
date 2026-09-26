"""Apexes, ridges, and the reflections of a footprint.

:mod:`krovlab.links` roofs from the connections the visitor made.
This module holds the points those connections name. It does not
build a roof. ``import krovlab`` does not import it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from krovlab._skeleton import skeleton as _straight_skeleton
from krovlab.roof import _oriented_ring

type Vertex = tuple[float, float]


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
    roof height passed to :func:`krovlab.links.roof_from_links`.
    """

    x0: float
    y0: float
    x1: float
    y1: float
    height: float | None = None


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
