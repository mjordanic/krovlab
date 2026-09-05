"""HTTP form wrapping ``roof`` and the existing Plotly views."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from flask import Flask, render_template, request

from krovlab import Failure, Pitch, Roof, roof
from krovlab.viz import plan_view, solid_view
from web.corpus import DEFAULT_PRESET, Preset, load_presets
from web.figures import input_footprint


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
        result = roof(
            preset.footprint,
            preset.pitch,
            holes=preset.holes,
            overhang=preset.overhang,
        )
        plan_html, solid_html, footprint_html = _draw(result, preset)
        return render_template(
            "page.html",
            names=list(presets),
            selected=preset.name,
            preset=preset,
            pitch_text=_pitch_text(preset.pitch),
            describe=_describe(result),
            plan_html=plan_html,
            solid_html=solid_html,
            footprint_html=footprint_html,
        )

    return app


def _pitch_text(pitch: Pitch | list[Pitch]) -> str:
    if isinstance(pitch, list):
        return ", ".join(str(value) for value in pitch)
    return str(pitch)


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
    result: Roof | Failure, preset: Preset
) -> tuple[str | None, str | None, str | None]:
    if isinstance(result, Failure):
        return (
            None,
            None,
            _embed(input_footprint(preset.footprint, preset.holes), include_js=True),
        )
    plan_html = _embed(plan_view(result), include_js=True)
    solid_html: str | None = None
    if result.validity.is_terrain:
        solid_html = _embed(solid_view(result), include_js=False)
    return plan_html, solid_html, None


def _embed(fig: Any, *, include_js: bool) -> str:
    js: bool | str = "cdn" if include_js else False
    html: str = fig.to_html(full_html=False, include_plotlyjs=js)
    return html
