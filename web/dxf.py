"""DXF footprint adapter for the form server.

The core package does not import this module. ezdxf stays a web extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any

import ezdxf
from ezdxf.lldxf.const import DXFError

from krovlab._input import check_footprint, check_holes
from krovlab.roof import Failure

SIZE_LIMIT = 2 * 1024 * 1024
_SCALES = {"mm": 1000.0, "cm": 100.0, "m": 1.0}
_BULGE = 1e-12
_CLOSED = 1e-9

_NOT_DXF = "This file is not a DXF."
_TOO_LARGE = "This DXF is larger than 2 MB."
_NO_POLYLINE = "No closed straight polyline was found in model space."
_EXPLODE = (
    "This file has block inserts and no model-space polyline. "
    "Explode the insert in CAD and upload again."
)
_TWO_OUTER = "This file has two outermost rings. Upload one building footprint."


@dataclass(frozen=True)
class DxfFootprint:
    """One outer ring and zero or more holes, in metres."""

    outer: list[tuple[float, float]]
    holes: list[list[tuple[float, float]]]


def rings_from_dxf(data: bytes, units: str) -> DxfFootprint | str:
    """Return metre rings from a DXF body, or a short visitor-facing message."""
    if len(data) > SIZE_LIMIT:
        return _TOO_LARGE
    scale = _SCALES.get(units, _SCALES["mm"])
    try:
        doc = _read_doc(data)
    except (DXFError, ValueError, OSError, UnicodeError):
        return _NOT_DXF
    inserts = 0
    model_polylines = 0
    candidates: list[list[tuple[float, float]]] = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "INSERT":
            inserts += 1
            continue
        if kind == "LWPOLYLINE":
            model_polylines += 1
            ring = _lw_ring(entity, scale)
            if ring is not None:
                candidates.append(ring)
        elif kind == "POLYLINE":
            model_polylines += 1
            ring = _poly_ring(entity, scale)
            if ring is not None:
                candidates.append(ring)
    if not candidates:
        if inserts and model_polylines == 0:
            return _EXPLODE
        return _NO_POLYLINE
    outer_indexes = [
        i
        for i, ring in enumerate(candidates)
        if not any(
            j != i and _strictly_inside(ring, other)
            for j, other in enumerate(candidates)
        )
    ]
    if len(outer_indexes) != 1:
        return _TWO_OUTER
    outer_index = outer_indexes[0]
    outer_raw = candidates[outer_index]
    inner_raw = [ring for i, ring in enumerate(candidates) if i != outer_index]
    outer = check_footprint(outer_raw)
    if isinstance(outer, Failure):
        return outer.reason
    holes = check_holes(inner_raw, outer)
    if isinstance(holes, Failure):
        return holes.reason
    return DxfFootprint(outer=outer, holes=holes)


def _read_doc(data: bytes) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return ezdxf.read(StringIO(text))  # type: ignore[attr-defined]


def _lw_ring(entity: Any, scale: float) -> list[tuple[float, float]] | None:
    get_points = getattr(entity, "get_points", None)
    if get_points is None:
        return None
    points = list(get_points("xyb"))
    if any(abs(float(row[2])) > _BULGE for row in points):
        return None
    ring = [(float(row[0]) / scale, float(row[1]) / scale) for row in points]
    closed = bool(
        getattr(entity, "closed", False) or getattr(entity, "is_closed", False)
    )
    return _closed_xy(ring, closed)


def _poly_ring(entity: Any, scale: float) -> list[tuple[float, float]] | None:
    vertices = getattr(entity, "vertices", None)
    if vertices is None:
        return None
    ring: list[tuple[float, float]] = []
    for vertex in vertices:
        dxf = getattr(vertex, "dxf", None)
        if dxf is None:
            continue
        bulge = float(getattr(dxf, "bulge", 0.0) or 0.0)
        if abs(bulge) > _BULGE:
            return None
        loc = getattr(dxf, "location", None)
        if loc is None:
            continue
        ring.append((float(loc.x) / scale, float(loc.y) / scale))
    closed = bool(
        getattr(entity, "is_closed", False) or getattr(entity, "closed", False)
    )
    return _closed_xy(ring, closed)


def _closed_xy(
    ring: list[tuple[float, float]], flagged: bool
) -> list[tuple[float, float]] | None:
    if len(ring) >= 2 and _same(ring[0], ring[-1]):
        ring = ring[:-1]
        flagged = True
    if not flagged or len(ring) < 3:
        return None
    return ring


def _same(a: tuple[float, float], b: tuple[float, float]) -> bool:
    dx, dy = a[0] - b[0], a[1] - b[1]
    return (dx * dx + dy * dy) <= _CLOSED * _CLOSED


def _strictly_inside(
    inner: list[tuple[float, float]], outer: list[tuple[float, float]]
) -> bool:
    return bool(inner) and all(_point_in(x, y, outer) for x, y in inner)


def _point_in(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_at = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_at:
                inside = not inside
        j = i
    return inside
