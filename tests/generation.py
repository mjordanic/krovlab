"""Hypothesis strategies for footprints the library currently roofs.

Widen :func:`footprints` in place as later tickets add holes and the rest.
The invariant tests import this strategy and should not grow their own
generators.
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


def _affine(
    pts: list[tuple[float, float]],
    sx: float,
    sy: float,
    rot: float,
    tx: float,
    ty: float,
) -> list[tuple[float, float]]:
    """Scale, rotate and translate. Positive scales keep winding."""
    c, s = math.cos(rot), math.sin(rot)
    out: list[tuple[float, float]] = []
    for x, y in pts:
        x, y = sx * x, sy * y
        out.append((c * x - s * y + tx, s * x + c * y + ty))
    return out


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
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        pts.append((radius * math.cos(a), radius * math.sin(a)))
    return _affine(pts, sx, sy, rot, tx, ty)


def _draw_pose(draw: st.DrawFn) -> tuple[float, float, float, float, float]:
    sx = draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False))
    sy = draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False))
    rot = draw(st.floats(min_value=0.0, max_value=math.pi, allow_nan=False))
    tx = draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False))
    ty = draw(st.floats(min_value=-20.0, max_value=20.0, allow_nan=False))
    return sx, sy, rot, tx, ty


def _draw_rigid(draw: st.DrawFn) -> tuple[float, float, float, float, float]:
    """Uniform scale and translate, no rotation. Axis-aligned reflex templates."""
    scale = draw(st.floats(min_value=0.8, max_value=1.4, allow_nan=False))
    tx = draw(st.floats(min_value=-10.0, max_value=10.0, allow_nan=False))
    ty = draw(st.floats(min_value=-10.0, max_value=10.0, allow_nan=False))
    return scale, scale, 0.0, tx, ty


def _min_edge(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    return min(
        math.hypot(pts[(i + 1) % n][0] - pts[i][0], pts[(i + 1) % n][1] - pts[i][1])
        for i in range(n)
    )


def _accept(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    poly = Polygon(pts)
    assume(poly.is_valid and poly.area >= 16.0)
    assume(_min_edge(pts) >= 2.5)
    assume(poly.area / poly.length >= 0.7)
    return pts


@st.composite
def convex_polygons(draw: st.DrawFn) -> list[tuple[float, float]]:
    """A strictly convex polygon large enough to roof stably."""
    n = draw(st.integers(min_value=3, max_value=8))
    radius = draw(st.floats(min_value=4.0, max_value=40.0, allow_nan=False))
    sx, sy, rot, tx, ty = _draw_pose(draw)
    pts = _affine_ngon(n, radius, sx, sy, rot, tx, ty)
    poly = Polygon(pts)
    assume(poly.is_valid and poly.area >= 4.0)
    return pts


@st.composite
def l_polygons(draw: st.DrawFn) -> list[tuple[float, float]]:
    """An L-shape: one reflex corner. Both arms stay several metres thick."""
    w = draw(st.floats(min_value=10.0, max_value=16.0, allow_nan=False))
    h = draw(st.floats(min_value=8.0, max_value=14.0, allow_nan=False))
    cut_w = draw(st.floats(min_value=3.0, max_value=w - 4.0, allow_nan=False))
    cut_h = draw(st.floats(min_value=3.0, max_value=h - 4.0, allow_nan=False))
    pts = [
        (0.0, 0.0),
        (w, 0.0),
        (w, h - cut_h),
        (w - cut_w, h - cut_h),
        (w - cut_w, h),
        (0.0, h),
    ]
    return _accept(_affine(pts, *_draw_rigid(draw)))


@st.composite
def u_polygons(draw: st.DrawFn) -> list[tuple[float, float]]:
    """A U-shape: two reflex corners at the slot."""
    w = draw(st.floats(min_value=10.0, max_value=16.0, allow_nan=False))
    h = draw(st.floats(min_value=8.0, max_value=12.0, allow_nan=False))
    slot_w = draw(st.floats(min_value=3.0, max_value=5.0, allow_nan=False))
    slot_h = draw(st.floats(min_value=3.0, max_value=5.0, allow_nan=False))
    left = (w - slot_w) / 2.0
    right = left + slot_w
    pts = [
        (0.0, 0.0),
        (w, 0.0),
        (w, h),
        (right, h),
        (right, h - slot_h),
        (left, h - slot_h),
        (left, h),
        (0.0, h),
    ]
    return _accept(_affine(pts, *_draw_rigid(draw)))


def footprints() -> st.SearchStrategy[list[tuple[float, float]]]:
    """Footprints in the class the library currently roofs.

    Simple polygons, including L and U shapes with reflex corners.
    T-shapes are covered by worked examples rather than generation:
    their two reflex corners often event at the same instant, which is
    pitch-sensitive. Later tickets add holes. Change the body of this
    function, not the invariant tests that call it.
    """
    return st.one_of(convex_polygons(), l_polygons(), u_polygons())
