"""Hypothesis strategies for footprints the library currently roofs.

Widen :func:`footprints` in place as later tickets add reflex corners,
holes, and the rest. The invariant tests import this strategy and should
not grow their own generators.
"""

from __future__ import annotations

import math

from hypothesis import assume
from hypothesis import strategies as st
from shapely.geometry import Polygon  # type: ignore[import-untyped]

# Degrees. Away from the 0/90 bounds where weight blows up or faces vanish.
PITCHES = st.floats(
    min_value=5.0,
    max_value=80.0,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)


def _affine_ngon(
    n: int,
    radius: float,
    sx: float,
    sy: float,
    rot: float,
    tx: float,
    ty: float,
) -> list[tuple[float, float]]:
    """Regular n-gon, stretched, rotated and translated.

    An affine image of a regular polygon stays strictly convex provided
    both scale factors are positive, so this never yields reflex corners
    or collinear vertices.
    """
    c, s = math.cos(rot), math.sin(rot)
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        x, y = sx * radius * math.cos(a), sy * radius * math.sin(a)
        pts.append((c * x - s * y + tx, s * x + c * y + ty))
    return pts


@st.composite
def convex_polygons(draw: st.DrawFn) -> list[tuple[float, float]]:
    """A strictly convex polygon large enough to roof stably."""
    n = draw(st.integers(min_value=3, max_value=8))
    radius = draw(st.floats(min_value=4.0, max_value=40.0, allow_nan=False))
    sx = draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False))
    sy = draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False))
    rot = draw(st.floats(min_value=0.0, max_value=math.pi, allow_nan=False))
    tx = draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False))
    ty = draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False))
    pts = _affine_ngon(n, radius, sx, sy, rot, tx, ty)
    poly = Polygon(pts)
    assume(poly.is_valid and poly.area >= 4.0)
    return pts


def footprints() -> st.SearchStrategy[list[tuple[float, float]]]:
    """Footprints in the class the library currently roofs.

    Today that class is convex, no holes. Ticket 06 widens this to simple
    polygons with reflex corners; later tickets add holes. Change the body
    of this function, not the invariant tests that call it.
    """
    return convex_polygons()
