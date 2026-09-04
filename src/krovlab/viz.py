"""Optional plan-view rendering. Consumes a :class:`Roof`, never the algorithm.

Install the ``viz`` extra (``uv sync --extra viz``) to use this module.
The core package does not import it.
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
