"""Optional visualisation. Consumes a :class:`Roof`, never the algorithm.

Plan and 3D solid views both return Plotly figures. Install the ``viz``
extra (``uv sync --extra viz``) to use this module. The core package
does not import it.
"""

from __future__ import annotations

from pathlib import Path

try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "krovlab.viz requires the viz extra. Install with: uv sync --extra viz"
    ) from exc

from krovlab.roof import Roof

# Glossary names from CONTEXT.md. Empty kinds still appear in the legend.
ARC_COLOUR = {
    "eave": "#6b7280",
    "verge": "#0f766e",
    "hip": "#d97706",
    "valley": "#2563eb",
    "ridge": "#dc2626",
}
ARC_KINDS = ("eave", "verge", "hip", "valley", "ridge")


def plan_view(roof: Roof) -> go.Figure:
    """Return a plan figure of the footprint with the skeleton drawn over it.

    Arcs are coloured by classification, using the glossary names in the
    legend. Node heights are annotated in metres.
    """
    fig = go.Figure()
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
            name="footprint",
            hoverinfo="skip",
            showlegend=True,
        )
    )

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


def solid_view(roof: Roof) -> go.Figure:
    """Return an orbitable 3D figure of the roof solid.

    Face vertices use the node heights the roof already reports. There
    is no lifting step.
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
    eave, so fall back to the original vertices (height-0 nodes, which
    the skeleton records first).
    """
    closed = _eave_ring(roof)
    if closed is not None:
        return closed
    outer: list[tuple[float, float]] = []
    for node in roof.nodes:
        if node.height > 1e-9:
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
