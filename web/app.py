"""HTTP form wrapping ``roof`` and the existing Plotly views."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flask import Flask, render_template, request

from krovlab import Failure, Pitch, Roof, roof
from krovlab.viz import plan_view, solid_view
from web.corpus import DEFAULT_PRESET, Preset, load_presets
from web.figures import input_footprint


@dataclass(frozen=True)
class EdgeRow:
    """One footprint edge on the form: index, endpoints, posted pitch."""

    index: int
    start: tuple[float, float]
    end: tuple[float, float]
    pitch: str
    gable: bool


def create_app() -> Flask:
    """Build the single-page form app. One route for GET and POST."""
    app = Flask(__name__)
    presets = load_presets()

    @app.route("/", methods=["GET", "POST"])
    def index() -> str:
        name = (
            request.form.get("fixture", DEFAULT_PRESET)
            if request.method == "POST"
            else DEFAULT_PRESET
        )
        preset = presets.get(name, presets[DEFAULT_PRESET])
        n_edges = _edge_count(preset)
        fallback = _expand_pitches(preset.pitch, n_edges)
        if request.method == "POST":
            pitches = _posted_pitches(request.form, n_edges, fallback)
            apply_to_all = request.form.get("apply_to_all") or (
                pitches[0] if pitches else ""
            )
            overhang = _posted_overhang(request.form, preset.overhang)
        else:
            pitches = fallback
            apply_to_all = pitches[0] if pitches else ""
            overhang = preset.overhang
        rows = _edge_rows(preset.footprint, preset.holes, pitches)
        result = roof(
            preset.footprint,
            pitches,
            holes=preset.holes,
            overhang=overhang,
        )
        plan_html, solid_html, footprint_html = _draw(
            result, preset.footprint, preset.holes, overhang
        )
        return render_template(
            "page.html",
            names=list(presets),
            selected=preset.name,
            preset=preset,
            apply_to_all=apply_to_all,
            overhang=overhang,
            edges=rows,
            describe=_describe(result),
            plan_html=plan_html,
            solid_html=solid_html,
            footprint_html=footprint_html,
        )

    return app


def _edge_count(preset: Preset) -> int:
    n = len(preset.footprint)
    if preset.holes:
        n += sum(len(hole) for hole in preset.holes)
    return n


def _posted_pitches(
    form: Mapping[str, str], n: int, fallback: list[Pitch]
) -> list[Pitch]:
    pitches: list[Pitch] = []
    for i in range(n):
        if form.get(f"gable-{i}"):
            pitches.append("90")
            continue
        posted = form.get(f"pitch-{i}")
        if posted is not None and posted != "":
            pitches.append(posted)
        else:
            pitches.append(fallback[i] if i < len(fallback) else "")
    return pitches


def _posted_overhang(form: Mapping[str, str], fallback: float) -> float:
    raw = form.get("overhang")
    if raw is None or raw.strip() == "":
        return fallback
    return float(raw)


def _expand_pitches(pitch: Pitch | list[Pitch], n: int) -> list[Pitch]:
    if isinstance(pitch, list):
        return list(pitch)
    return [pitch] * n


def _is_gable(pitch: Pitch) -> bool:
    if isinstance(pitch, tuple):
        return False
    try:
        return float(pitch) == 90.0
    except ValueError:
        return False


def _edge_rows(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None,
    pitches: list[Pitch],
) -> list[EdgeRow]:
    rings = [footprint, *(holes or [])]
    rows: list[EdgeRow] = []
    for ring in rings:
        count = len(ring)
        for i, start in enumerate(ring):
            end = ring[(i + 1) % count]
            raw = pitches[len(rows)] if len(rows) < len(pitches) else ""
            gable = _is_gable(raw)
            rows.append(
                EdgeRow(
                    index=len(rows),
                    start=start,
                    end=end,
                    pitch="90" if gable else str(raw),
                    gable=gable,
                )
            )
    return rows


def _describe(result: Roof | Failure) -> str:
    if isinstance(result, Failure):
        return f"Failure\nkind: {result.kind}\n{result.reason}"
    lines = [
        f"terrain: {result.validity.is_terrain}",
        f"ridge height: {result.ridge_height:.3f} m",
        f"total sloped area: {result.total_sloped_area:.3f} m²",
    ]
    by_kind: dict[str, list[float]] = defaultdict(list)
    for arc in result.arcs:
        by_kind[arc.kind].append(arc.length)
    for kind in ("eave", "hip", "valley", "ridge", "verge"):
        lengths = by_kind.get(kind)
        if lengths:
            lines.append(f"{kind}: {sum(lengths):.3f} m")
    return "\n".join(lines)


def _draw(
    result: Roof | Failure,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None,
    overhang: float,
) -> tuple[str | None, str | None, str | None]:
    if isinstance(result, Failure):
        return (
            None,
            None,
            _embed(input_footprint(footprint, holes), include_js=True),
        )
    walls: dict[str, Any] = {}
    if overhang != 0.0:
        walls = {"walls": footprint, "wall_holes": holes}
    plan_html = _embed(plan_view(result, **walls), include_js=True)
    solid_html: str | None = None
    if result.validity.is_terrain:
        solid_html = _embed(solid_view(result, **walls), include_js=False)
    return plan_html, solid_html, None


def _embed(fig: Any, *, include_js: bool) -> str:
    js: bool | str = "cdn" if include_js else False
    html: str = fig.to_html(full_html=False, include_plotlyjs=js)
    return html
