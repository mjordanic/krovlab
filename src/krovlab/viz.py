"""Optional visualisation. Consumes a :class:`Roof` or a :class:`Project`.

Plan, 3D solid and wavefront views all return Plotly figures. Install
the ``viz`` extra (``uv sync --extra viz``) to use this module. The
core package does not import it. A project is one plan of every cell
and one 3D solid of the lot.
"""

from __future__ import annotations

from pathlib import Path

try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "krovlab.viz requires the viz extra. Install with: uv sync --extra viz"
    ) from exc

from krovlab.project import Project
from krovlab.roof import Event, Roof

# Glossary names from CONTEXT.md. Empty kinds still appear in the legend.
ARC_COLOUR = {
    "eave": "#6b7280",
    "verge": "#0f766e",
    "hip": "#d97706",
    "valley": "#2563eb",
    "ridge": "#dc2626",
}
ARC_KINDS = ("eave", "verge", "hip", "valley", "ridge")


def plan_view(
    roof: Roof | Project,
    *,
    walls: list[tuple[float, float]] | None = None,
    wall_holes: list[list[tuple[float, float]]] | None = None,
) -> go.Figure:
    """Return a plan figure of the roof with the skeleton drawn over it.

    Arcs are coloured by classification, using the glossary names in the
    legend. Node heights are annotated in metres. A project draws every
    cell's plan extent.

    Pass ``walls`` (and ``wall_holes``) when the eaves are not the walls:
    an overhang. The dark ``walls`` line is the building; the eave arcs
    are where the roof ends.
    """
    fig = go.Figure()
    fill_name = "roof" if walls is not None else "footprint"
    cells = _roofs_of(roof)
    for i, built in enumerate(cells):
        name = fill_name if len(cells) == 1 else f"{fill_name} {i}"
        _add_footprint_trace(fig, built, name=name)
    if walls is not None:
        _add_wall_plan_traces(fig, walls, wall_holes)

    by_kind: dict[str, list[tuple[float, float]]] = {kind: [] for kind in ARC_KINDS}
    for arc in roof.arcs:
        a, b = roof.nodes[arc.start], roof.nodes[arc.end]
        bucket = by_kind[arc.kind]
        if bucket:
            bucket.append((float("nan"), float("nan")))
        bucket.append((a.x, a.y))
        bucket.append((b.x, b.y))

    for kind in ARC_KINDS:
        points = by_kind[kind] or [(float("nan"), float("nan"))]
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                mode="lines",
                line={"color": ARC_COLOUR[kind], "width": 3 if kind != "eave" else 2},
                name=kind,
                legendgroup=kind,
                hovertemplate=f"{kind}<extra></extra>",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=[node.x for node in roof.nodes],
            y=[node.y for node in roof.nodes],
            text=[f"{node.height:.2f} m" for node in roof.nodes],
            mode="markers+text",
            textposition="top center",
            marker={"size": 8, "color": "#111827"},
            name="height",
            hovertemplate="(%{x:.2f}, %{y:.2f}) %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="x (m)",
        yaxis_title="y (m)",
        yaxis_scaleanchor="x",
        yaxis_scaleratio=1,
        template="plotly_white",
        legend_title="arc",
    )
    return fig


def solid_view(
    roof: Roof | Project,
    *,
    walls: list[tuple[float, float]] | None = None,
    wall_holes: list[list[tuple[float, float]]] | None = None,
) -> go.Figure:
    """Return an orbitable 3D figure of the roof solid.

    Face vertices use the node heights the roof already reports. There
    is no lifting step. A project is one solid of every cell. ``walls``
    is the building outline at height 0, drawn inside the eaves when an
    overhang is applied.
    """
    fig = go.Figure()
    xs = [node.x for node in roof.nodes]
    ys = [node.y for node in roof.nodes]
    zs = [node.height for node in roof.nodes]
    i: list[int] = []
    j: list[int] = []
    k: list[int] = []
    for face in roof.faces:
        for tri in _triangulate(face.node_indices, xs, ys):
            i.append(tri[0])
            j.append(tri[1])
            k.append(tri[2])
    fig.add_trace(
        go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=i,
            j=j,
            k=k,
            color="#d1d5db",
            flatshading=True,
            name="face",
            hovertemplate="(%{x:.2f}, %{y:.2f}, %{z:.2f} m)<extra></extra>",
            lighting={"ambient": 0.55, "diffuse": 0.8, "specular": 0.1},
        )
    )
    by_kind: dict[str, list[tuple[float, float, float]]] = {
        kind: [] for kind in ARC_KINDS
    }
    for arc in roof.arcs:
        a, b = roof.nodes[arc.start], roof.nodes[arc.end]
        bucket = by_kind[arc.kind]
        if bucket:
            bucket.append((float("nan"), float("nan"), float("nan")))
        bucket.append((a.x, a.y, a.height))
        bucket.append((b.x, b.y, b.height))
    for kind in ARC_KINDS:
        points = by_kind[kind] or [(float("nan"), float("nan"), float("nan"))]
        fig.add_trace(
            go.Scatter3d(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                z=[p[2] for p in points],
                mode="lines",
                line={"color": ARC_COLOUR[kind], "width": 6 if kind != "eave" else 4},
                name=kind,
                legendgroup=kind,
                hovertemplate=f"{kind}<extra></extra>",
            )
        )
    if walls is not None:
        _add_wall_solid_traces(fig, walls, wall_holes)
    fig.update_layout(
        scene={
            "xaxis_title": "x (m)",
            "yaxis_title": "y (m)",
            "zaxis_title": "height (m)",
            "aspectmode": "data",
        },
        template="plotly_white",
        legend_title="arc",
    )
    return fig


def wavefront_view(
    roof: Roof,
    time: float,
    *,
    walls: list[tuple[float, float]] | None = None,
    wall_holes: list[list[tuple[float, float]]] | None = None,
) -> go.Figure:
    """Return a plan figure of the wavefront at ``time`` over the footprint.

    ``time`` is height in metres: the wavefront rises at unit rate, so a
    chosen time is a horizontal cut through the roof. Negative time and
    time past the end of the propagation still produce a figure — the
    footprint with an empty wavefront — rather than erroring.
    """
    fig = go.Figure()
    fill_name = "roof" if walls is not None else "footprint"
    _add_footprint_trace(fig, roof, name=fill_name)
    if walls is not None:
        _add_wall_plan_traces(fig, walls, wall_holes)
    points = _wavefront_segments(roof, time)
    if not points:
        points = [(float("nan"), float("nan"))]
    fig.add_trace(
        go.Scatter(
            x=[p[0] for p in points],
            y=[p[1] for p in points],
            mode="lines",
            line={"color": "#7c3aed", "width": 3},
            name="wavefront",
            hovertemplate="wavefront<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="x (m)",
        yaxis_title="y (m)",
        yaxis_scaleanchor="x",
        yaxis_scaleratio=1,
        template="plotly_white",
        legend_title="wavefront",
        title=f"t = {time:.3f} m",
    )
    return fig


def wavefront_steps(
    roof: Roof,
    events: tuple[Event, ...] | None = None,
    *,
    walls: list[tuple[float, float]] | None = None,
    wall_holes: list[list[tuple[float, float]]] | None = None,
) -> list[go.Figure]:
    """Return a wavefront view at each successive step time.

    Step times are the event times from ticket 04 when ``events`` is
    given, so a developer can land on an event rather than near it.
    Without the log, node heights are used — time is height. Time 0 is
    always included so the sequence starts at the footprint.
    """
    return [
        wavefront_view(roof, time, walls=walls, wall_holes=wall_holes)
        for time in _step_times(roof, events)
    ]


def _step_times(
    roof: Roof, events: tuple[Event, ...] | None
) -> tuple[float, ...]:
    times: set[float] = {0.0}
    if events is not None:
        times.update(event.time for event in events)
    else:
        times.update(node.height for node in roof.nodes)
    return tuple(sorted(times))


def write_html(fig: go.Figure, path: str | Path) -> Path:
    """Write a self-contained HTML file that opens over ``file://``.

    Plotly.js is inlined so the file needs no server and no network.
    """
    destination = Path(path)
    fig.write_html(
        destination,
        include_plotlyjs=True,
        full_html=True,
    )
    return destination


def _roofs_of(geometry: Roof | Project) -> tuple[Roof, ...]:
    """The cell roofs to draw. A single roof is a one-cell tuple."""
    if isinstance(geometry, Project):
        return geometry.roofs
    return (geometry,)


def _add_footprint_trace(
    fig: go.Figure, roof: Roof, *, name: str = "footprint"
) -> None:
    """Draw the eave ring — the roof's plan extent — under the skeleton."""
    ring = _footprint_ring(roof)
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    fig.add_trace(
        go.Scatter(
            x=[*xs, xs[0]],
            y=[*ys, ys[0]],
            mode="lines",
            fill="toself",
            fillcolor="rgba(243, 244, 246, 0.85)",
            line={"color": "#d1d5db", "width": 1},
            name=name,
            hoverinfo="skip",
            showlegend=True,
        )
    )


WALL_COLOUR = "#7c2d12"
WALL_FILL = "rgba(124, 45, 18, 0.20)"


def _closed_xy(ring: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """Repeat the first vertex so a scatter trace closes."""
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    if not xs:
        return xs, ys
    return [*xs, xs[0]], [*ys, ys[0]]


def _add_wall_plan_traces(
    fig: go.Figure,
    walls: list[tuple[float, float]],
    wall_holes: list[list[tuple[float, float]]] | None,
) -> None:
    """Building outline, distinct from the eaves (the roof edge)."""
    xs, ys = _closed_xy(walls)
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            fill="toself",
            fillcolor=WALL_FILL,
            line={"color": WALL_COLOUR, "width": 3},
            name="walls",
            hovertemplate="walls<extra></extra>",
        )
    )
    for i, hole in enumerate(wall_holes or []):
        hxs, hys = _closed_xy(hole)
        fig.add_trace(
            go.Scatter(
                x=hxs,
                y=hys,
                mode="lines",
                line={"color": WALL_COLOUR, "width": 2, "dash": "dash"},
                name="walls (hole)" if i == 0 else f"walls (hole {i})",
                hovertemplate="walls (hole)<extra></extra>",
                showlegend=i == 0,
            )
        )


def _add_wall_solid_traces(
    fig: go.Figure,
    walls: list[tuple[float, float]],
    wall_holes: list[list[tuple[float, float]]] | None,
) -> None:
    """Building outline at height 0, inside the eaves when they overhang."""
    xs, ys = _closed_xy(walls)
    fig.add_trace(
        go.Scatter3d(
            x=xs,
            y=ys,
            z=[0.0] * len(xs),
            mode="lines",
            line={"color": WALL_COLOUR, "width": 8},
            name="walls",
            hovertemplate="walls<extra></extra>",
        )
    )
    for i, hole in enumerate(wall_holes or []):
        hxs, hys = _closed_xy(hole)
        fig.add_trace(
            go.Scatter3d(
                x=hxs,
                y=hys,
                z=[0.0] * len(hxs),
                mode="lines",
                line={"color": WALL_COLOUR, "width": 6},
                name="walls (hole)" if i == 0 else f"walls (hole {i})",
                hovertemplate="walls (hole)<extra></extra>",
                showlegend=i == 0,
            )
        )


def _wavefront_segments(roof: Roof, time: float) -> list[tuple[float, float]]:
    """Plan polylines where the roof meets height ``time``.

    Time is height, so this is the wavefront. Each face contributes the
    segments of its boundary that lie on the cutting plane; NaNs separate
    disjoint pieces. Out-of-range times yield an empty list.
    """
    points: list[tuple[float, float]] = []
    for face in roof.faces:
        cycle = face.node_indices
        if len(cycle) < 2:
            continue
        contour = _face_contour(roof, cycle, time)
        if len(contour) < 2:
            continue
        if points:
            points.append((float("nan"), float("nan")))
        points.extend(contour)
    for a, b in _gable_wavefront_edges(roof, time):
        if points:
            points.append((float("nan"), float("nan")))
        points.append(a)
        points.append(b)
    return points


def _face_contour(
    roof: Roof, cycle: tuple[int, ...], time: float
) -> list[tuple[float, float]]:
    """Ordered plan points where a face boundary meets height ``time``."""
    tol = 1e-9
    contour: list[tuple[float, float]] = []
    n = len(cycle)
    for i in range(n):
        a = roof.nodes[cycle[i]]
        b = roof.nodes[cycle[(i + 1) % n]]
        ha, hb = a.height, b.height
        on_a = abs(ha - time) <= tol
        on_b = abs(hb - time) <= tol
        if on_a and on_b:
            contour.append((a.x, a.y))
            contour.append((b.x, b.y))
            continue
        if on_a:
            contour.append((a.x, a.y))
            continue
        if (ha < time < hb) or (hb < time < ha):
            denom = hb - ha
            if abs(denom) <= tol:
                continue
            frac = (time - ha) / denom
            contour.append((a.x + frac * (b.x - a.x), a.y + frac * (b.y - a.y)))
    return contour


def _gable_wavefront_edges(
    roof: Roof, time: float
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Stationary gable-wall edges of the wavefront at ``time``.

    A gable has no face, so a height cut of the sloped faces leaves a
    gap. The two verges of a gable meet at the wall; the segment
    between them at this height is the edge that never moved.
    """
    by_peak: dict[int, list[tuple[int, int]]] = {}
    for arc in roof.arcs:
        if arc.kind != "verge":
            continue
        a, b = roof.nodes[arc.start], roof.nodes[arc.end]
        peak = arc.start if a.height >= b.height else arc.end
        by_peak.setdefault(peak, []).append((arc.start, arc.end))
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for pair in by_peak.values():
        if len(pair) != 2:
            continue
        p1 = _point_on_arc_at_height(roof, pair[0][0], pair[0][1], time)
        p2 = _point_on_arc_at_height(roof, pair[1][0], pair[1][1], time)
        if p1 is None or p2 is None:
            continue
        if abs(p1[0] - p2[0]) <= 1e-9 and abs(p1[1] - p2[1]) <= 1e-9:
            continue
        edges.append((p1, p2))
    return edges


def _point_on_arc_at_height(
    roof: Roof, start: int, end: int, time: float
) -> tuple[float, float] | None:
    """Plan point of an arc at height ``time``, or None if the arc misses it."""
    a, b = roof.nodes[start], roof.nodes[end]
    lo, hi = (a.height, b.height) if a.height <= b.height else (b.height, a.height)
    tol = 1e-9
    if time < lo - tol or time > hi + tol:
        return None
    denom = b.height - a.height
    if abs(denom) <= tol:
        return (a.x, a.y)
    frac = (time - a.height) / denom
    return (a.x + frac * (b.x - a.x), a.y + frac * (b.y - a.y))


def _eave_ring(roof: Roof) -> list[tuple[float, float]] | None:
    """Closed plan ring from eave arcs, or None if they do not form a cycle."""
    eaves = [arc for arc in roof.arcs if arc.kind == "eave"]
    if not eaves:
        return None
    successor = {arc.start: arc.end for arc in eaves}
    start = eaves[0].start
    order = [start]
    current = start
    for _ in range(len(eaves)):
        nxt = successor.get(current)
        if nxt is None:
            return None
        if nxt == start:
            return [(roof.nodes[i].x, roof.nodes[i].y) for i in order]
        order.append(nxt)
        current = nxt
    return None


def _footprint_ring(roof: Roof) -> list[tuple[float, float]]:
    """Plan ring of the footprint, reconstructed from the roof value.

    Eaves close the ring on a fully hipped roof. Gabled edges have no
    eave, so fall back to the original vertices (the first nodes, which
    sit at this cell's eave height — zero by default).
    """
    closed = _eave_ring(roof)
    if closed is not None:
        return closed
    eave = min((node.height for node in roof.nodes), default=0.0)
    outer: list[tuple[float, float]] = []
    for node in roof.nodes:
        if node.height > eave + 1e-9:
            break
        outer.append((node.x, node.y))
    return outer


def _triangulate(
    cycle: tuple[int, ...], xs: list[float], ys: list[float]
) -> list[tuple[int, int, int]]:
    """Ear-clip a simple plan polygon. Indices refer to the coordinate lists."""
    if len(cycle) < 3:
        return []
    remaining = list(cycle)
    triangles: list[tuple[int, int, int]] = []
    ccw = _ring_signed_area(remaining, xs, ys) > 0.0
    guard = 0
    limit = len(cycle) * len(cycle)
    while len(remaining) > 3 and guard < limit:
        guard += 1
        n = len(remaining)
        clipped = False
        for i in range(n):
            prev = remaining[(i - 1) % n]
            cur = remaining[i]
            nxt = remaining[(i + 1) % n]
            if not _is_ear(prev, cur, nxt, remaining, xs, ys, ccw):
                continue
            triangles.append((prev, cur, nxt))
            del remaining[i]
            clipped = True
            break
        if not clipped:
            break
    if len(remaining) >= 3:
        origin = remaining[0]
        for t in range(1, len(remaining) - 1):
            triangles.append((origin, remaining[t], remaining[t + 1]))
    return triangles


def _ring_signed_area(idxs: list[int], xs: list[float], ys: list[float]) -> float:
    total = 0.0
    n = len(idxs)
    for i in range(n):
        a, b = idxs[i], idxs[(i + 1) % n]
        total += xs[a] * ys[b] - xs[b] * ys[a]
    return 0.5 * total


def _is_ear(
    prev: int,
    cur: int,
    nxt: int,
    remaining: list[int],
    xs: list[float],
    ys: list[float],
    ccw: bool,
) -> bool:
    dx1 = xs[cur] - xs[prev]
    dy1 = ys[cur] - ys[prev]
    dx2 = xs[nxt] - xs[cur]
    dy2 = ys[nxt] - ys[cur]
    cross = dx1 * dy2 - dy1 * dx2
    convex = cross > 1e-12 if ccw else cross < -1e-12
    if not convex:
        return False
    for idx in remaining:
        if idx in (prev, cur, nxt):
            continue
        if _point_in_triangle(
            xs[idx],
            ys[idx],
            xs[prev],
            ys[prev],
            xs[cur],
            ys[cur],
            xs[nxt],
            ys[nxt],
        ):
            return False
    return True


def _point_in_triangle(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
) -> bool:
    v0x, v0y = cx - ax, cy - ay
    v1x, v1y = bx - ax, by - ay
    v2x, v2y = px - ax, py - ay
    dot00 = v0x * v0x + v0y * v0y
    dot01 = v0x * v1x + v0y * v1y
    dot02 = v0x * v2x + v0y * v2y
    dot11 = v1x * v1x + v1y * v1y
    dot12 = v1x * v2x + v1y * v2y
    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < 1e-18:
        return False
    u = (dot11 * dot02 - dot01 * dot12) / denom
    v = (dot00 * dot12 - dot01 * dot02) / denom
    return u >= -1e-12 and v >= -1e-12 and u + v <= 1.0 + 1e-12
