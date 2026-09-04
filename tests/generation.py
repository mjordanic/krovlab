"""Hypothesis strategies for footprints the library currently roofs.

Widen :func:`footprints` and :func:`roof_cases` in place as later tickets
add gables and the rest. The invariant tests import these strategies and
should not grow their own generators.
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

# Per-edge lists stay in a tighter band. Extreme weight ratios on reflex
# polygons (very flat vs steep, parallel catch-up) can stall the wavefront.
PER_EDGE_PITCHES = st.floats(
    min_value=20.0,
    max_value=60.0,
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
    pitch-sensitive. Holes are drawn by :func:`roof_cases`, not here —
    this strategy stays a single ring so polygon checks stay simple.
    """
    return st.one_of(convex_polygons(), l_polygons(), u_polygons())


@st.composite
def rectangle_with_hole(
    draw: st.DrawFn,
) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    """Axis-aligned rectangle with a rectangular courtyard, both thick enough."""
    w = draw(st.floats(min_value=12.0, max_value=18.0, allow_nan=False))
    h = draw(st.floats(min_value=12.0, max_value=18.0, allow_nan=False))
    inset = draw(st.floats(min_value=2.5, max_value=4.0, allow_nan=False))
    hole_w = w - 2.0 * inset
    hole_h = h - 2.0 * inset
    assume(hole_w >= 2.5 and hole_h >= 2.5)
    pose = _draw_rigid(draw)
    outer = _accept(_affine([(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)], *pose))
    hole = _affine(
        [
            (inset, inset),
            (inset + hole_w, inset),
            (inset + hole_w, inset + hole_h),
            (inset, inset + hole_h),
        ],
        *pose,
    )
    return outer, [hole]


@st.composite
def roof_cases(
    draw: st.DrawFn,
) -> tuple[
    list[tuple[float, float]],
    float | list[float],
    list[list[tuple[float, float]]],
]:
    """Uniform pitch on every supported footprint, including courtyards.

    Per-edge lists stay on convex polygons without holes: mixed weights
    on reflex or holed shapes are covered by worked examples.
    """
    if draw(st.integers(min_value=0, max_value=2)) == 0:
        outer, holes = draw(rectangle_with_hole())
        return outer, draw(PITCHES), holes
    if draw(st.booleans()):
        return draw(footprints()), draw(PITCHES), []
    footprint = draw(convex_polygons())
    n = len(footprint)
    pitches = [draw(PER_EDGE_PITCHES) for _ in range(n)]
    if all(abs(p - pitches[0]) <= 1e-9 for p in pitches):
        other = draw(PER_EDGE_PITCHES.filter(lambda p: abs(p - pitches[0]) > 1.0))
        pitches[draw(st.integers(min_value=0, max_value=n - 1))] = other
    return footprint, pitches, []
