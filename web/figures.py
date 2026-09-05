"""Plotly figures owned by the web app.

The input-footprint drawing is shown on a Failure. It is not added to
``krovlab.viz``.
"""

from __future__ import annotations

try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "the web extra requires Plotly. Install with: uv sync --extra web"
    ) from exc


def input_footprint(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None = None,
) -> go.Figure:
    """Plan of the submitted rings — used when there is no roof to draw."""
    fig = go.Figure()
    if footprint:
        xs = [p[0] for p in footprint] + [footprint[0][0]]
        ys = [p[1] for p in footprint] + [footprint[0][1]]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name="walls",
                line={"color": "#7c2d12", "width": 2},
                fill="toself",
                fillcolor="rgba(124, 45, 18, 0.10)",
                marker={"size": 7, "color": "#7c2d12"},
            )
        )
    hole_list = holes or []
    for i, hole in enumerate(hole_list):
        if not hole:
            continue
        xs = [p[0] for p in hole] + [hole[0][0]]
        ys = [p[1] for p in hole] + [hole[0][1]]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name="hole" if len(hole_list) == 1 else f"hole {i}",
                line={"color": "#1d4ed8", "width": 2, "dash": "dot"},
                marker={"size": 6, "color": "#1d4ed8"},
            )
        )
    fig.update_layout(
        xaxis_title="x (m)",
        yaxis_title="y (m)",
        yaxis_scaleanchor="x",
        yaxis_scaleratio=1,
        template="plotly_white",
        legend_title="input",
    )
    return fig
