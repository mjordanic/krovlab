"""HTTP form wrapping ``roof`` / ``project`` and the existing Plotly views."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from flask import Flask, render_template, request

from krovlab import Cell, Failure, Pitch, Project, Roof, project, roof
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
    pitch_name: str
    gable_name: str
    knee: str
    knee_name: str


@dataclass(frozen=True)
class ExtraCellView:
    """Posted tables for a cell after the first, so the form can round-trip."""

    index: int
    prefix: str
    footprint: list[tuple[Any, Any]]
    hole: list[tuple[Any, Any]]
    edges: list[EdgeRow]
    overhang: float | str
    eave_height: float | str
    wrap_groups: list[str]


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
        extra_views: list[ExtraCellView] = []
        extra_footprints: list[list[tuple[float, float]]] = []
        knees: list[float] = [0.0] * n_edges
        posted_wrap_fields = _posted_wraps(request.form)
        wrap_groups: list[str] = _wrap_group_strings(
            posted_wrap_fields if not isinstance(posted_wrap_fields, Failure) else []
        )
        result: Roof | Project | Failure
        if parse_error is not None:
            apply_to_all = request.form.get("apply_to_all") or (
                str(fallback[0]) if fallback else ""
            )
            pitches = _posted_pitches(request.form, n_edges, fallback, apply_to_all)
            posted_knees = _posted_knees(request.form, n_edges)
            if not isinstance(posted_knees, Failure):
                knees = posted_knees
            result = parse_error
            draw_rings: tuple[
                list[tuple[float, float]],
                list[list[tuple[float, float]]] | None,
            ] = ([], None)
        elif request.method == "POST" and not stale:
            apply_to_all = request.form.get("apply_to_all") or ""
            pitches = _posted_pitches(request.form, n_edges, fallback, apply_to_all)
            if not apply_to_all:
                apply_to_all = str(pitches[0]) if pitches else ""
            parsed_overhang = _posted_overhang(request.form, preset.overhang)
            parsed_eave_height = _posted_eave_height(request.form, preset.eave_height)
            parsed_knees = _posted_knees(request.form, n_edges)
            parsed_wraps = _posted_wraps(request.form)
            parsed_footprint = cast(list[tuple[float, float]], footprint)
            parsed_holes = cast(list[list[tuple[float, float]]] | None, holes)
            if isinstance(parsed_overhang, Failure):
                result = parsed_overhang
                form_overhang = request.form.get("overhang") or preset.overhang
                draw_overhang = 0.0
                draw_rings = (parsed_footprint, parsed_holes)
            elif isinstance(parsed_eave_height, Failure):
                result = parsed_eave_height
                form_eave_height = request.form.get("eave_height") or 0.0
                draw_rings = (parsed_footprint, parsed_holes)
            elif isinstance(parsed_knees, Failure):
                result = parsed_knees
                draw_rings = (parsed_footprint, parsed_holes)
            elif isinstance(parsed_wraps, Failure):
                result = parsed_wraps
                draw_rings = (parsed_footprint, parsed_holes)
            else:
                draw_overhang = parsed_overhang
                form_overhang = parsed_overhang
                form_eave_height = parsed_eave_height
                knees = parsed_knees
                wrap_groups = _wrap_group_strings(parsed_wraps)
                draw_rings = (parsed_footprint, parsed_holes)
                extra_views, extra_parsed = _extra_cells_for_post(
                    request.form, apply_to_all, preset
                )
                if isinstance(extra_parsed, Failure):
                    result = extra_parsed
                elif extra_parsed:
                    extra_footprints = [cell.footprint for cell in extra_parsed]
                    result = project(
                        [
                            Cell(
                                parsed_footprint,
                                pitches,
                                holes=parsed_holes,
                                overhang=parsed_overhang,
                                eave_height=parsed_eave_height,
                                knee_height=parsed_knees,
                                wrap=parsed_wraps or None,
                            ),
                            *extra_parsed,
                        ]
                    )
                else:
                    result = roof(
                        parsed_footprint,
                        pitches,
                        holes=parsed_holes,
                        overhang=parsed_overhang,
                        eave_height=parsed_eave_height,
                        knee_height=parsed_knees,
                        wrap=parsed_wraps or None,
                    )
        else:
            pitches = fallback
            apply_to_all = str(pitches[0]) if pitches else ""
            form_eave_height = preset.eave_height
            parsed_footprint = cast(list[tuple[float, float]], footprint)
            parsed_holes = cast(list[list[tuple[float, float]]] | None, holes)
            extra_views = _extra_views_from_cells(preset.extra_cells)
            extra_footprints = [cell.footprint for cell in preset.extra_cells]
            result = _from_preset(preset)
            draw_rings = (parsed_footprint, parsed_holes)
        rows = _edge_rows(footprint, holes, pitches, knees=knees)
        plan_html, solid_html, footprint_html = _draw(
            result,
            draw_rings[0],
            draw_rings[1],
            draw_overhang,
            extra_footprints,
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
            extra_cells=extra_views,
            wrap_groups=wrap_groups,
            describe=_describe(result),
            plan_html=plan_html,
            solid_html=solid_html,
            footprint_html=footprint_html,
            edit_vertices=bool(
                (request.method == "POST" and request.form.get("edit_vertices"))
                or extra_views
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


def _posted_ring(form: Mapping[str, str], prefix: str) -> list[tuple[str, str]] | None:
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
    *,
    prefix: str = "",
) -> list[Pitch]:
    pitches: list[Pitch] = []
    for i in range(n):
        if form.get(f"{prefix}gable-{i}"):
            pitches.append("90")
            continue
        posted = form.get(f"{prefix}pitch-{i}")
        if posted is not None and posted != "":
            pitches.append(posted)
        elif apply_to_all:
            pitches.append(apply_to_all)
        else:
            pitches.append(fallback[i] if i < len(fallback) else "")
    return pitches


def _posted_overhang(
    form: Mapping[str, str], fallback: float, *, field: str = "overhang"
) -> float | Failure:
    raw = form.get(field)
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )


def _posted_eave_height(
    form: Mapping[str, str],
    fallback: float = 0.0,
    *,
    field: str = "eave_height",
) -> float | Failure:
    raw = form.get(field)
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )


def _posted_knees(
    form: Mapping[str, str],
    n: int,
    *,
    prefix: str = "",
) -> list[float] | Failure:
    knees: list[float] = []
    for i in range(n):
        raw = form.get(f"{prefix}knee-{i}")
        if raw is None or str(raw).strip() == "":
            knees.append(0.0)
            continue
        try:
            value = float(raw)
        except ValueError:
            return Failure(
                kind="degenerate",
                reason=(
                    "knee height must be a finite number of metres, zero or positive"
                ),
            )
        knees.append(value)
    return knees


def _posted_wraps(
    form: Mapping[str, str],
    *,
    prefix: str = "",
) -> list[list[int]] | Failure:
    groups: list[list[int]] = []
    index = 0
    while index < 64:
        raw = form.get(f"{prefix}wrap-{index}")
        if raw is None:
            break
        text = str(raw).strip()
        if text == "":
            index += 1
            continue
        try:
            edges = [int(part.strip()) for part in text.split(",") if part.strip()]
        except ValueError:
            return Failure(
                kind="degenerate",
                reason="wrap groups name edges by integer index",
            )
        if edges:
            groups.append(edges)
        index += 1
    return groups


def _wrap_group_strings(groups: list[list[int]] | None) -> list[str]:
    if not groups:
        return []
    return [",".join(str(i) for i in group) for group in groups]


def _expand_knees(value: float | list[float], n: int) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    return [float(value)] * n


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
    *,
    prefix: str = "",
    knees: list[float] | None = None,
) -> list[EdgeRow]:
    rings = [footprint, *(holes or [])]
    rows: list[EdgeRow] = []
    for ring in rings:
        count = len(ring)
        for i, start in enumerate(ring):
            end = ring[(i + 1) % count]
            raw = pitches[len(rows)] if len(rows) < len(pitches) else ""
            gable = _is_gable(raw)
            index = len(rows)
            knee = 0.0
            if knees is not None and index < len(knees):
                knee = knees[index]
            rows.append(
                EdgeRow(
                    index=index,
                    start=start,
                    end=end,
                    pitch="90" if gable else str(raw),
                    gable=gable,
                    pitch_name=f"{prefix}pitch-{index}",
                    gable_name=f"{prefix}gable-{index}",
                    knee=str(knee),
                    knee_name=f"{prefix}knee-{index}",
                )
            )
    return rows


def _from_preset(preset: Preset) -> Roof | Project | Failure:
    cells = [
        Cell(
            preset.footprint,
            preset.pitch,
            holes=preset.holes,
            overhang=preset.overhang,
            eave_height=preset.eave_height,
        ),
        *preset.extra_cells,
    ]
    if len(cells) == 1:
        return roof(
            cells[0].footprint,
            cells[0].pitch,
            holes=cells[0].holes,
            overhang=cells[0].overhang,
            eave_height=cells[0].eave_height,
            knee_height=cells[0].knee_height,
        )
    return project(cells)


def _extra_cells_for_post(
    form: Mapping[str, str], apply_to_all: str, preset: Preset
) -> tuple[list[ExtraCellView], list[Cell] | Failure]:
    if form.get("edit_vertices"):
        return _posted_extra_cells(form, apply_to_all)
    extras = list(preset.extra_cells)
    return _extra_views_from_cells(extras), extras


def _extra_views_from_cells(cells: Sequence[Cell]) -> list[ExtraCellView]:
    return [_view_from_cell(i + 1, cell) for i, cell in enumerate(cells)]


def _view_from_cell(index: int, cell: Cell) -> ExtraCellView:
    prefix = f"cell-{index}-"
    hole = cell.holes[0] if cell.holes else []
    n_edges = len(cell.footprint) + len(hole)
    pitches = _expand_pitches(cell.pitch, n_edges)
    knees = _expand_knees(cell.knee_height, n_edges)
    return ExtraCellView(
        index=index,
        prefix=prefix,
        footprint=cell.footprint,
        hole=hole,
        edges=_edge_rows(
            cell.footprint,
            [hole] if hole else None,
            pitches,
            prefix=prefix,
            knees=knees,
        ),
        overhang=cell.overhang,
        eave_height=cell.eave_height,
        wrap_groups=_wrap_group_strings(cell.wrap),
    )


def _posted_extra_cells(
    form: Mapping[str, str], apply_to_all: str
) -> tuple[list[ExtraCellView], list[Cell] | Failure]:
    views: list[ExtraCellView] = []
    cells: list[Cell] = []
    index = 1
    while form.get(f"cell-{index}-outer-x-0") is not None:
        prefix = f"cell-{index}-"
        posted_outer = _posted_ring(form, f"{prefix}outer")
        posted_hole = _posted_ring(form, f"{prefix}hole")
        outer_display = posted_outer or []
        hole_display = posted_hole or []
        n_edges = len(outer_display) + len(hole_display)
        pitches = _posted_pitches(form, n_edges, [], apply_to_all, prefix=prefix)
        posted_knees = _posted_knees(form, n_edges, prefix=prefix)
        posted_wraps = _posted_wraps(form, prefix=prefix)
        display_knees = posted_knees if not isinstance(posted_knees, Failure) else None
        display_wraps = (
            _wrap_group_strings(posted_wraps)
            if not isinstance(posted_wraps, Failure)
            else []
        )
        raw_overhang = form.get(f"{prefix}overhang") or "0"
        raw_eave = form.get(f"{prefix}eave_height") or "0"
        views.append(
            ExtraCellView(
                index=index,
                prefix=prefix,
                footprint=outer_display,
                hole=hole_display,
                edges=_edge_rows(
                    outer_display,
                    [hole_display] if hole_display else None,
                    pitches,
                    prefix=prefix,
                    knees=display_knees,
                ),
                overhang=raw_overhang,
                eave_height=raw_eave,
                wrap_groups=display_wraps,
            )
        )
        if posted_outer is None:
            return views, Failure(
                kind="degenerate",
                reason=f"cell {index} needs an outer ring",
            )
        parsed_outer = _as_xy_ring(posted_outer, f"cell {index} footprint")
        if isinstance(parsed_outer, Failure):
            return views, parsed_outer
        parsed_holes: list[list[tuple[float, float]]] | None = None
        if posted_hole:
            parsed_hole = _as_xy_ring(posted_hole, f"cell {index} hole")
            if isinstance(parsed_hole, Failure):
                return views, parsed_hole
            parsed_holes = [parsed_hole]
        overhang = _posted_overhang(form, 0.0, field=f"{prefix}overhang")
        if isinstance(overhang, Failure):
            return views, overhang
        eave_height = _posted_eave_height(form, field=f"{prefix}eave_height")
        if isinstance(eave_height, Failure):
            return views, eave_height
        if isinstance(posted_knees, Failure):
            return views, posted_knees
        if isinstance(posted_wraps, Failure):
            return views, posted_wraps
        cells.append(
            Cell(
                parsed_outer,
                pitches,
                holes=parsed_holes,
                overhang=overhang,
                eave_height=eave_height,
                knee_height=posted_knees,
                wrap=posted_wraps or None,
            )
        )
        index += 1
    return views, cells


def _describe(result: Roof | Project | Failure) -> str:
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
    lines.append("faces:")
    for face in result.faces:
        eaves = face.eave_indices or (face.edge_index,)
        if len(eaves) > 1:
            named = ", ".join(str(i) for i in eaves)
            lines.append(f"  edges {named}: one plane, pitch {face.pitch:g}°")
        else:
            lines.append(f"  edge {face.edge_index}: pitch {face.pitch:g}°")
    if not result.validity.is_terrain:
        lines.append("validity.reasons:")
        lines.extend(result.validity.reasons)
    return "\n".join(lines)


def _draw(
    result: Roof | Project | Failure,
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]] | None,
    overhang: float,
    extra_footprints: list[list[tuple[float, float]]] | None = None,
) -> tuple[str | None, str | None, str | None]:
    extras = extra_footprints or []
    if isinstance(result, Failure):
        return (
            None,
            None,
            _embed(
                input_footprint(footprint, holes, extras),
                include_js=True,
            ),
        )
    if isinstance(result, Project):
        plan_html = _embed(plan_view(result), include_js=True)
        solid_html: str | None = None
        if result.validity.is_terrain:
            solid_html = _embed(solid_view(result), include_js=False)
        return plan_html, solid_html, None
    walls: dict[str, Any] = {}
    if overhang != 0.0:
        walls = {"walls": footprint, "wall_holes": holes}
    plan_html = _embed(plan_view(result, **walls), include_js=True)
    solid_html = None
    if result.validity.is_terrain:
        solid_html = _embed(solid_view(result, **walls), include_js=False)
    return plan_html, solid_html, None


def _embed(fig: Any, *, include_js: bool) -> str:
    js: bool | str = "cdn" if include_js else False
    html: str = fig.to_html(full_html=False, include_plotlyjs=js)
    return html
