"""HTTP form wrapping ``roof`` and the existing Plotly views."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from flask import Flask, render_template, request

from krovlab import Failure, Pitch, Roof, roof
from krovlab.viz import plan_view, solid_view
from web.corpus import DEFAULT_PRESET, Preset, load_presets
from web.figures import input_footprint


@dataclass(frozen=True)
class EdgeRow:
    """One footprint edge on the form: index, endpoints, posted pitch."""

    index: int
    start: tuple[Any, Any]
    end: tuple[Any, Any]
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
        stale = _fixture_changed(request.method, request.form, preset.name)
        footprint, holes, parse_error = _rings_for_request(
            request.method, request.form, preset, stale
        )
        n_edges = len(footprint) + sum(len(hole) for hole in (holes or []))
        fallback = _expand_pitches(preset.pitch, n_edges)
        draw_overhang = preset.overhang
        form_overhang: float | str = preset.overhang
        form_eave_height: float | str = 0.0
        result: Roof | Failure
        if parse_error is not None:
            apply_to_all = request.form.get("apply_to_all") or (
                str(fallback[0]) if fallback else ""
            )
            pitches = _posted_pitches(
                request.form, n_edges, fallback, apply_to_all
            )
            result = parse_error
            draw_rings: tuple[
                list[tuple[float, float]],
                list[list[tuple[float, float]]] | None,
            ] = ([], None)
        elif request.method == "POST" and not stale:
            apply_to_all = request.form.get("apply_to_all") or ""
            pitches = _posted_pitches(
                request.form, n_edges, fallback, apply_to_all
            )
            if not apply_to_all:
                apply_to_all = str(pitches[0]) if pitches else ""
            parsed_overhang = _posted_overhang(request.form, preset.overhang)
            parsed_eave_height = _posted_eave_height(request.form)
            parsed_footprint = cast(list[tuple[float, float]], footprint)
            parsed_holes = cast(
                list[list[tuple[float, float]]] | None, holes
            )
            if isinstance(parsed_overhang, Failure):
                result = parsed_overhang
                form_overhang = request.form.get("overhang") or preset.overhang
                draw_overhang = 0.0
                draw_rings = (parsed_footprint, parsed_holes)
            elif isinstance(parsed_eave_height, Failure):
                result = parsed_eave_height
                form_eave_height = request.form.get("eave_height") or 0.0
                draw_rings = (parsed_footprint, parsed_holes)
            else:
                draw_overhang = parsed_overhang
                form_overhang = parsed_overhang
                form_eave_height = parsed_eave_height
                result = roof(
                    parsed_footprint,
                    pitches,
                    holes=parsed_holes,
                    overhang=parsed_overhang,
                    eave_height=parsed_eave_height,
                )
                draw_rings = (parsed_footprint, parsed_holes)
        else:
            pitches = fallback
            apply_to_all = str(pitches[0]) if pitches else ""
            parsed_footprint = cast(list[tuple[float, float]], footprint)
            parsed_holes = cast(
                list[list[tuple[float, float]]] | None, holes
            )
            result = roof(
                parsed_footprint,
                pitches,
                holes=parsed_holes,
                overhang=preset.overhang,
            )
            draw_rings = (parsed_footprint, parsed_holes)
        rows = _edge_rows(footprint, holes, pitches)
        plan_html, solid_html, footprint_html = _draw(
            result, draw_rings[0], draw_rings[1], draw_overhang
        )
        return render_template(
            "page.html",
            names=list(presets),
            selected=preset.name,
            apply_to_all=apply_to_all,
            overhang=form_overhang,
            eave_height=form_eave_height,
            edges=rows,
            footprint=footprint,
            hole=holes[0] if holes else [],
            describe=_describe(result),
            plan_html=plan_html,
            solid_html=solid_html,
            footprint_html=footprint_html,
            edit_vertices=bool(
                request.method == "POST" and request.form.get("edit_vertices")
            ),
        )

    return app


def _fixture_changed(method: str, form: Mapping[str, str], name: str) -> bool:
    if method != "POST":
        return False
    loaded = form.get("loaded_fixture")
    return bool(loaded) and loaded != name


def _rings_for_request(
    method: str,
    form: Mapping[str, str],
    preset: Preset,
    stale: bool,
) -> tuple[
    list[tuple[Any, Any]],
    list[list[tuple[Any, Any]]] | None,
    Failure | None,
]:
    if method != "POST" or stale:
        return preset.footprint, preset.holes, None
    if not form.get("edit_vertices"):
        return preset.footprint, preset.holes, None
    posted_outer = _posted_ring(form, "outer")
    if posted_outer is None:
        return preset.footprint, preset.holes, None
    parsed_outer = _as_xy_ring(posted_outer, "footprint")
    posted_hole = _posted_ring(form, "hole")
    if isinstance(parsed_outer, Failure):
        holes: list[list[tuple[Any, Any]]] | None = (
            [posted_hole] if posted_hole else None
        )
        return posted_outer, holes, parsed_outer
    if posted_hole is None:
        return parsed_outer, None, None
    parsed_hole = _as_xy_ring(posted_hole, "hole")
    if isinstance(parsed_hole, Failure):
        return parsed_outer, [posted_hole], parsed_hole
    return parsed_outer, [parsed_hole], None


def _posted_ring(
    form: Mapping[str, str], prefix: str
) -> list[tuple[str, str]] | None:
    points: list[tuple[str, str]] = []
    i = 0
    while True:
        raw_x = form.get(f"{prefix}-x-{i}")
        raw_y = form.get(f"{prefix}-y-{i}")
        if raw_x is None and raw_y is None:
            break
        points.append((raw_x or "", raw_y or ""))
        i += 1
    if i == 0:
        return None
    while points and points[-1] == ("", ""):
        points.pop()
    return points if points else None


def _as_xy_ring(
    points: list[tuple[str, str]], name: str
) -> list[tuple[float, float]] | Failure:
    ring: list[tuple[float, float]] = []
    for i, (raw_x, raw_y) in enumerate(points):
        try:
            ring.append((float(raw_x), float(raw_y)))
        except ValueError:
            return Failure(
                kind="degenerate",
                reason=f"{name} vertex {i} is not an (x, y) metre pair",
            )
    return ring


def _posted_pitches(
    form: Mapping[str, str],
    n: int,
    fallback: list[Pitch],
    apply_to_all: str,
) -> list[Pitch]:
    pitches: list[Pitch] = []
    for i in range(n):
        if form.get(f"gable-{i}"):
            pitches.append("90")
            continue
        posted = form.get(f"pitch-{i}")
        if posted is not None and posted != "":
            pitches.append(posted)
        elif apply_to_all:
            pitches.append(apply_to_all)
        else:
            pitches.append(fallback[i] if i < len(fallback) else "")
    return pitches


def _posted_overhang(
    form: Mapping[str, str], fallback: float
) -> float | Failure:
    raw = form.get("overhang")
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )


def _posted_eave_height(form: Mapping[str, str]) -> float | Failure:
    raw = form.get("eave_height")
    if raw is None or raw.strip() == "":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )


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
    footprint: list[tuple[Any, Any]],
    holes: list[list[tuple[Any, Any]]] | None,
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
    if not result.validity.is_terrain:
        lines.append("validity.reasons:")
        lines.extend(result.validity.reasons)
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
