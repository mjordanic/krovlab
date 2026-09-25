"""HTTP form wrapping ``roof`` / ``project`` and the existing Plotly views."""

from __future__ import annotations

import math
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from krovlab import Cell, Dormer, Failure, Pitch, Project, Roof, project, roof
from krovlab.experimental import roof_from_face_graph
from krovlab.viz import plan_view, solid_view
from web.agent.loop import HelpModel, run_turn
from web.agent.rate_limit import RateLimiter
from web.dxf import DxfFootprint, rings_from_dxf
from web.examples import (
    DEFAULT_EXAMPLE,
    DEFAULT_EXPERIMENTAL_EXAMPLE,
    WALL_HINTS,
    Example,
    load_examples,
    load_experimental_examples,
)
from web.figures import input_footprint
from web.mesh import glb_bytes, obj_bytes


@dataclass(frozen=True)
class WallView:
    """One wall on a cell: exclusive type plus the fields that type needs."""

    index: int
    number: int
    start: tuple[Any, Any]
    end: tuple[Any, Any]
    kind: str
    pitch: str
    knee: str
    shallow: str
    break_height: str
    hint: str
    prefix: str
    type_name: str
    pitch_name: str
    knee_name: str
    shallow_name: str
    break_name: str


@dataclass(frozen=True)
class CellView:
    """One cell card on the form, including the first cell (prefix empty)."""

    index: int
    title: str
    prefix: str
    walls: list[WallView]
    footprint: list[tuple[Any, Any]]
    hole: list[tuple[Any, Any]]
    overhang: str
    eave_height: str
    use_overhang: bool
    use_eave: bool
    use_hole: bool
    extra_holes: list[list[tuple[Any, Any]]] = field(default_factory=list)


@dataclass(frozen=True)
class DormerView:
    """Posted millimetre table for one dormer ring."""

    index: int
    cell_index: int
    footprint: list[tuple[Any, Any]]
    pitches: list[str]
    kinds: list[str]


def create_app(
    *,
    model: HelpModel | None = None,
    limiter: RateLimiter | None = None,
) -> Flask:
    """Build the form app. ``POST /agent`` is the help JSON exception."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
    if os.environ.get("PORT"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # type: ignore[method-assign]
    examples = load_examples()
    experimental_examples = load_experimental_examples()
    help_model = model if model is not None else _live_model()
    help_limiter = limiter if limiter is not None else RateLimiter()
    agent_enabled = help_model is not None

    @app.route("/", methods=["GET", "POST"])
    def index() -> str:
        if request.method != "POST":
            method = _posted_method(request.args)
            catalog = _catalog(method, examples, experimental_examples)
            default = _default_example(method)
            slug = request.args.get("example") or default
            example = catalog.get(slug, catalog[default])
            result: Roof | Project | Failure
            if method == "experimental":
                result = _run_experimental_example(example)
            else:
                result = _run_cells(list(example.cells), list(example.dormers))
            return _render(
                example,
                _example_groups(catalog),
                cells=_cell_views_from_cells(example.cells),
                dormers=_dormer_views_from_items(example.dormers),
                result=result,
                set_pitch=_default_set_pitch(example.cells[0]),
                edit_coordinates=False,
                agent_enabled=agent_enabled,
                method=method,
                mesh_face_graph=(
                    _example_face_graph(example) if method == "experimental" else None
                ),
            )
        method = _posted_method(request.form)
        catalog = _catalog(method, examples, experimental_examples)
        default = _default_example(method)
        slug = request.form.get("example") or default
        example = catalog.get(slug, catalog[default])
        return _render_post(
            request.form,
            example,
            _example_groups(catalog),
            agent_enabled=agent_enabled,
            files=request.files,
            is_upload="upload_dxf" in request.form,
        )

    @app.post("/agent")
    def agent_turn() -> Any:
        if help_model is None:
            return jsonify(error="Help is not configured on this server."), 503
        if not help_limiter.allow(request.remote_addr or "unknown"):
            return jsonify(
                error="Too many help requests from this address. Try later."
            ), 429
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Send JSON with fields and messages."), 400
        form = _as_form(payload.get("fields"))
        if form is None or "outer-x-0" not in form:
            return jsonify(
                error="fields must be the current form (including the footprint)."
            ), 400
        raw_messages = payload.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            return jsonify(error="messages must be a non-empty list."), 400
        describe = payload.get("describe")
        selected = payload.get("selected")
        try:
            reply = run_turn(
                help_model,
                form=form,
                messages=raw_messages,
                describe=describe if isinstance(describe, str) else "",
                selected=selected if isinstance(selected, dict) else None,
            )
        except Exception as exc:
            app.logger.exception("help agent model call failed")
            return jsonify(error=_public_model_error(exc)), _model_status(exc)
        return jsonify(reply=reply.reply, fields=reply.fields)

    @app.post("/roof.obj")
    def download_obj() -> Response:
        return _mesh_response(request.form, "obj")

    @app.post("/roof.glb")
    def download_glb() -> Response:
        return _mesh_response(request.form, "glb")

    return app


def _mesh_response(form: Mapping[str, str], kind: str) -> Response:
    result = _result_from_form(form)
    if isinstance(result, Failure) or not _shows_solid(result):
        return Response("No 3D solid to download.", status=404)
    if kind == "obj":
        body = obj_bytes(result)
        return Response(
            body,
            mimetype="text/plain",
            headers={"Content-Disposition": 'attachment; filename="roof.obj"'},
        )
    body = glb_bytes(result)
    return Response(
        body,
        mimetype="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="roof.glb"'},
    )


def _result_from_form(form: Mapping[str, str]) -> Roof | Project | Failure:
    if _posted_method(form) == "experimental":
        catalog = load_experimental_examples()
        slug = form.get("example") or DEFAULT_EXPERIMENTAL_EXAMPLE
        example = catalog.get(slug, catalog[DEFAULT_EXPERIMENTAL_EXAMPLE])
        return _run_experimental_from_form(form, _posted_face_graph(form), example)
    set_pitch = form.get("set_pitch") or "45"
    _, parsed = _posted_cells(form, set_pitch)
    _, parsed_dormers = _posted_dormers(form)
    if isinstance(parsed, Failure):
        return parsed
    if isinstance(parsed_dormers, Failure):
        return parsed_dormers
    return _run_cells(parsed, parsed_dormers)


def _live_model() -> HelpModel | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from web.agent.gemini import GeminiModel
    except ImportError:
        return None
    return GeminiModel(api_key=key)


def _as_form(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            return None
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                out[key] = "on"
            continue
        out[key] = str(value)
    return out


def _public_model_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "429" in text or "resource_exhausted" in text or "quota" in text:
        return "Help is used up this month. Try again after the cap resets."
    return "Help could not reach the language model."


def _model_status(exc: Exception) -> int:
    text = str(exc).lower()
    if "429" in text or "resource_exhausted" in text or "quota" in text:
        return 429
    return 502


def _example_groups(
    examples: dict[str, Example],
) -> list[tuple[str, list[Example]]]:
    groups: list[tuple[str, list[Example]]] = []
    current = ""
    bucket: list[Example] = []
    for item in examples.values():
        if item.group != current:
            if bucket:
                groups.append((current, bucket))
            current = item.group
            bucket = [item]
        else:
            bucket.append(item)
    if bucket:
        groups.append((current, bucket))
    return groups


def _render_post(
    form: Mapping[str, str],
    example: Example,
    groups: list[tuple[str, list[Example]]],
    *,
    agent_enabled: bool,
    files: Mapping[str, Any] | None = None,
    is_upload: bool = False,
) -> str:
    set_pitch = form.get("set_pitch") or "45"
    edit_coordinates = bool(form.get("edit_coordinates"))
    method = _posted_method(form)
    views, parsed = _posted_cells(form, set_pitch)
    dormer_views, parsed_dormers = _posted_dormers(form)
    face_graph = _posted_face_graph(form)
    result: Roof | Project | Failure
    if method == "experimental":
        result = _run_experimental_from_form(form, face_graph, example)
    elif isinstance(parsed, Failure):
        result = parsed
    elif isinstance(parsed_dormers, Failure):
        result = parsed_dormers
    else:
        result = _run_cells(parsed, parsed_dormers)
    dxf_units = form.get("dxf_units") or "mm"
    if dxf_units not in {"mm", "cm", "m"}:
        dxf_units = "mm"
    dxf_message = ""
    needs_update = False
    selected_cell = form.get("selected_cell") or ""
    shown_cells = views
    shown_dormers = dormer_views
    used_graph = (
        face_graph
        if face_graph is not None
        else _example_face_graph(example)
    )
    posted_height = form.get("roof_height")
    mesh_roof_height = (
        posted_height.strip()
        if method == "experimental" and posted_height and posted_height.strip()
        else None
    )
    if is_upload:
        loaded = _load_dxf(files, dxf_units)
        if isinstance(loaded, str):
            dxf_message = loaded
        else:
            index = _selected_cell_index(form, len(views))
            views = _apply_dxf_to_cell(views, index, loaded, set_pitch)
            needs_update = True
            selected_cell = str(index)
    return _render(
        example,
        groups,
        cells=views,
        dormers=dormer_views,
        result=result,
        set_pitch=set_pitch,
        edit_coordinates=edit_coordinates,
        agent_enabled=agent_enabled,
        method=method,
        dxf_units=dxf_units,
        dxf_message=dxf_message,
        needs_update=needs_update,
        selected_cell=selected_cell,
        mesh_cells=shown_cells,
        mesh_dormers=shown_dormers,
        mesh_face_graph=used_graph if method == "experimental" else None,
        mesh_roof_height=mesh_roof_height,
    )


def _load_dxf(files: Mapping[str, Any] | None, units: str) -> DxfFootprint | str:
    if files is None:
        return rings_from_dxf(b"", units)
    storage = files.get("dxf")
    if storage is None or not getattr(storage, "filename", None):
        return rings_from_dxf(b"", units)
    data = storage.read()
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data)
    return rings_from_dxf(bytes(data), units)


def _selected_cell_index(form: Mapping[str, str], n: int) -> int:
    raw = form.get("selected_cell")
    if raw is None or str(raw).strip() in ("", "-1"):
        return 0
    try:
        index = int(raw)
    except ValueError:
        return 0
    if index < 0 or index >= n:
        return 0
    return index


def _apply_dxf_to_cell(
    views: list[CellView],
    index: int,
    footprint: DxfFootprint,
    set_pitch: str,
) -> list[CellView]:
    if not views:
        return views
    if index < 0 or index >= len(views):
        index = 0
    current = views[index]
    holes = list(footprint.holes)
    hole = list(holes[0]) if holes else []
    extra = [list(item) for item in holes[1:]]
    n_edges = len(footprint.outer) + sum(len(item) for item in holes)
    pitches: list[Pitch] = [set_pitch] * n_edges
    updated = _cell_view_from_parts(
        current.index,
        current.prefix,
        list(footprint.outer),
        hole,
        pitches,
        None,
        None,
        current.overhang,
        current.eave_height,
        current.use_overhang,
        current.use_eave,
        bool(holes),
        set_pitch,
        extra_holes=extra,
    )
    return [updated if i == index else cell for i, cell in enumerate(views)]


def _render(
    example: Example,
    groups: list[tuple[str, list[Example]]],
    *,
    cells: list[CellView],
    dormers: list[DormerView],
    result: Roof | Project | Failure,
    set_pitch: str,
    edit_coordinates: bool,
    agent_enabled: bool,
    method: str = "skeleton",
    dxf_units: str = "mm",
    dxf_message: str = "",
    needs_update: bool = False,
    selected_cell: str = "",
    mesh_cells: list[CellView] | None = None,
    mesh_dormers: list[DormerView] | None = None,
    mesh_face_graph: list[list[int]] | None = None,
    mesh_roof_height: str | None = None,
) -> str:
    extra_footprints = (
        [cell.footprint for cell in cells[1:]] if method != "experimental" else []
    )
    first = cells[0] if cells else None
    holes: list[list[tuple[Any, Any]]] | None = None
    draw_overhang = 0.0
    draw_footprint: list[tuple[Any, Any]] = []
    if first is not None:
        draw_footprint = first.footprint
        if method != "experimental" and first.use_hole and first.hole:
            holes = [first.hole]
        if first.use_overhang:
            try:
                draw_overhang = float(first.overhang)
            except ValueError:
                draw_overhang = 0.0
    plan_html, solid_html, footprint_html = _draw(
        result,
        draw_footprint,
        holes,
        draw_overhang,
        extra_footprints,
    )
    mesh_fields: dict[str, str] = {}
    if solid_html is not None:
        mesh_fields = _mesh_fields(
            mesh_cells if mesh_cells is not None else cells,
            mesh_dormers if mesh_dormers is not None else dormers,
            set_pitch,
            method=method,
            example=example.slug,
            roof_height=mesh_roof_height,
            face_graph=mesh_face_graph,
        )
    return render_template(
        "page.html",
        example=example,
        groups=groups,
        cells=cells,
        dormers=dormers,
        set_pitch=set_pitch,
        edit_coordinates=edit_coordinates,
        describe=_describe(result),
        plan_html=plan_html,
        solid_html=solid_html,
        footprint_html=footprint_html,
        wall_hints=WALL_HINTS,
        agent_enabled=agent_enabled,
        method=method,
        roof_height=_shown_roof_height(method, cells, result),
        dxf_units=dxf_units,
        dxf_message=dxf_message,
        needs_update=needs_update,
        selected_cell=selected_cell,
        mesh_fields=mesh_fields,
    )


def _run_cells(
    cells: list[Cell],
    dormers: Sequence[Dormer],
) -> Roof | Project | Failure:
    if not cells:
        return Failure(kind="empty", reason="a project needs at least one cell")
    if dormers:
        return project(cells, list(dormers))
    if len(cells) == 1:
        cell = cells[0]
        return roof(
            cell.footprint,
            cell.pitch,
            holes=cell.holes,
            overhang=cell.overhang,
            eave_height=cell.eave_height,
            knee_height=cell.knee_height,
            gambrel=cell.gambrel,
        )
    return project(cells)


def _posted_method(form: Mapping[str, str]) -> str:
    raw = (form.get("method") or "skeleton").strip().lower()
    if raw == "experimental":
        return "experimental"
    return "skeleton"


def _posted_face_graph(form: Mapping[str, str]) -> list[list[int]] | None:
    groups: list[list[int]] = []
    index = 0
    while True:
        raw = form.get(f"face-{index}")
        if raw is None:
            break
        text = raw.strip()
        if text:
            try:
                walls = [int(part.strip()) for part in text.split(",") if part.strip()]
                groups.append(walls)
            except ValueError:
                return []
        index += 1
    return groups or None


def _catalog(
    method: str,
    examples: dict[str, Example],
    experimental_examples: dict[str, Example],
) -> dict[str, Example]:
    if method == "experimental":
        return experimental_examples
    return examples


def _default_example(method: str) -> str:
    if method == "experimental":
        return DEFAULT_EXPERIMENTAL_EXAMPLE
    return DEFAULT_EXAMPLE


def _run_experimental_example(example: Example) -> Roof | Failure:
    cell = example.cells[0]
    graph = _example_face_graph(example)
    return roof_from_face_graph(
        list(cell.footprint),
        graph,
        overhang=cell.overhang,
        eave_height=cell.eave_height,
    )


def _shown_roof_height(
    method: str,
    cells: list[CellView],
    result: Roof | Project | Failure,
) -> str:
    if method != "experimental" or not isinstance(result, Roof):
        return ""
    eave = 0.0
    first = cells[0] if cells else None
    if first is not None and first.use_eave:
        try:
            eave = float(first.eave_height)
        except ValueError:
            eave = 0.0
    rise = result.ridge_height - eave
    return f"{rise:g}"


def _example_face_graph(example: Example) -> list[list[int]] | None:
    if example.face_graph is None:
        return None
    return [list(group) for group in example.face_graph]


def _run_experimental_from_form(
    form: Mapping[str, str],
    face_graph: list[list[int]] | None,
    example: Example,
) -> Roof | Failure:
    posted_outer = _posted_ring(form, "outer")
    if posted_outer is None:
        return Failure(kind="degenerate", reason="a footprint needs an outer ring")
    parsed_outer = _as_xy_ring(posted_outer, "footprint")
    if isinstance(parsed_outer, Failure):
        return parsed_outer
    if form.get("use_overhang"):
        overhang = _posted_overhang(form, 0.0)
        if isinstance(overhang, Failure):
            return overhang
    else:
        overhang = 0.0
    if form.get("use_eave_height"):
        eave_height = _posted_eave_height(form)
        if isinstance(eave_height, Failure):
            return eave_height
    else:
        eave_height = 0.0
    roof_height = _posted_roof_height(form)
    if isinstance(roof_height, Failure):
        return roof_height
    graph = face_graph if face_graph is not None else _example_face_graph(example)
    return roof_from_face_graph(
        parsed_outer,
        graph,
        overhang=overhang,
        eave_height=eave_height,
        roof_height=roof_height,
    )


def _posted_roof_height(form: Mapping[str, str]) -> float | None | Failure:
    raw = form.get("roof_height")
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="roof height must be a finite number of metres above the eaves",
        )


def _default_set_pitch(cell: Cell) -> str:
    if isinstance(cell.pitch, list):
        for item in cell.pitch:
            if not _is_gable(item):
                return str(item)
        return "45"
    return str(cell.pitch)


def _cell_views_from_cells(cells: Sequence[Cell]) -> list[CellView]:
    return [_view_from_cell(i, cell) for i, cell in enumerate(cells)]


def _view_from_cell(index: int, cell: Cell) -> CellView:
    prefix = "" if index == 0 else f"cell-{index}-"
    holes = [list(item) for item in (cell.holes or [])]
    hole = holes[0] if holes else []
    extra = holes[1:]
    n_edges = len(cell.footprint) + sum(len(item) for item in holes)
    pitches = _expand_pitches(cell.pitch, n_edges)
    knees = _expand_knees(cell.knee_height, n_edges)
    return CellView(
        index=index,
        title=f"Cell {index + 1}",
        prefix=prefix,
        walls=_wall_views(
            cell.footprint,
            hole,
            pitches,
            prefix=prefix,
            knees=knees,
            gambrels=cell.gambrel,
            extra_holes=extra,
        ),
        footprint=list(cell.footprint),
        hole=hole,
        overhang=_fmt(cell.overhang),
        eave_height=_fmt(cell.eave_height),
        use_overhang=float(cell.overhang) != 0.0,
        use_eave=float(cell.eave_height) != 0.0,
        use_hole=bool(hole),
        extra_holes=extra,
    )


def _wall_views(
    footprint: list[tuple[Any, Any]],
    hole: list[tuple[Any, Any]],
    pitches: list[Pitch],
    *,
    prefix: str = "",
    knees: list[float] | None = None,
    gambrels: Sequence[tuple[Pitch, Pitch, float] | None] | None = None,
    extra_holes: Sequence[list[tuple[Any, Any]]] | None = None,
) -> list[WallView]:
    rings = [footprint, *([hole] if hole else []), *(extra_holes or [])]
    rows: list[WallView] = []
    for ring in rings:
        count = len(ring)
        for i, start in enumerate(ring):
            end = ring[(i + 1) % count]
            index = len(rows)
            raw = pitches[index] if index < len(pitches) else ""
            knee = 0.0
            if knees is not None and index < len(knees):
                knee = knees[index]
            item = (
                None if gambrels is None or index >= len(gambrels) else gambrels[index]
            )
            kind, pitch, shallow, break_height = _kind_fields(raw, knee, item)
            rows.append(
                WallView(
                    index=index,
                    number=index + 1,
                    start=start,
                    end=end,
                    kind=kind,
                    pitch=pitch,
                    knee=_fmt(knee) if kind == "knee" else "0",
                    shallow=shallow,
                    break_height=break_height,
                    hint=WALL_HINTS[kind],
                    prefix=prefix,
                    type_name=f"{prefix}type-{index}",
                    pitch_name=f"{prefix}pitch-{index}",
                    knee_name=f"{prefix}knee-{index}",
                    shallow_name=f"{prefix}gambrel-shallow-{index}",
                    break_name=f"{prefix}gambrel-break-{index}",
                )
            )
    return rows


def _kind_fields(
    raw: Pitch,
    knee: float,
    item: tuple[Pitch, Pitch, float] | None,
) -> tuple[str, str, str, str]:
    if item is not None:
        steep, shallow_pitch, height = item
        return "gambrel", str(steep), str(shallow_pitch), str(height)
    if _is_gable(raw):
        return "gable", "90", "", "0"
    if knee > 0.0:
        return "knee", str(raw), "", "0"
    return "hip", str(raw), "", "0"


def _fmt(value: Any) -> str:
    return str(value)


def _posted_cells(
    form: Mapping[str, str],
    set_pitch: str,
) -> tuple[list[CellView], list[Cell] | Failure]:
    views: list[CellView] = []
    cells: list[Cell] = []
    index = 0
    while index <= 32:
        prefix = "" if index == 0 else f"cell-{index}-"
        posted_outer = _posted_ring(form, f"{prefix}outer")
        if posted_outer is None:
            if index == 0:
                return views, Failure(
                    kind="degenerate",
                    reason="a cell needs an outer ring",
                )
            break
        posted_hole = _posted_ring(form, f"{prefix}hole")
        extra_posted = _posted_extra_holes(form, prefix)
        use_hole = bool(form.get(f"{prefix}use_hole"))
        hole_display = posted_hole if use_hole and posted_hole else []
        extra_display = extra_posted if use_hole else []
        n_edges = (
            len(posted_outer)
            + len(hole_display)
            + sum(len(item) for item in extra_display)
        )
        spec = _posted_edge_spec(form, n_edges, prefix, set_pitch)
        use_overhang = bool(form.get(f"{prefix}use_overhang"))
        use_eave = bool(form.get(f"{prefix}use_eave_height"))
        raw_overhang = form.get(f"{prefix}overhang") or "0"
        raw_eave = form.get(f"{prefix}eave_height") or "0"
        if isinstance(spec, Failure):
            views.append(
                _cell_view_from_parts(
                    index,
                    prefix,
                    posted_outer,
                    hole_display,
                    [],
                    None,
                    None,
                    raw_overhang,
                    raw_eave,
                    use_overhang,
                    use_eave,
                    use_hole,
                    set_pitch,
                )
            )
            return views, spec
        pitches, knees, gambrels = spec
        parsed_outer = _as_xy_ring(
            posted_outer, "footprint" if index == 0 else f"cell {index} footprint"
        )
        display_outer: list[tuple[Any, Any]] = posted_outer
        display_hole: list[tuple[Any, Any]] = hole_display
        if isinstance(parsed_outer, Failure):
            views.append(
                _cell_view_from_parts(
                    index,
                    prefix,
                    display_outer,
                    display_hole,
                    pitches,
                    knees,
                    gambrels,
                    raw_overhang,
                    raw_eave,
                    use_overhang,
                    use_eave,
                    use_hole,
                    set_pitch,
                )
            )
            return views, parsed_outer
        display_outer = parsed_outer
        parsed_holes: list[list[tuple[float, float]]] | None = None
        parsed_extras: list[list[tuple[float, float]]] = []
        if use_hole and posted_hole:
            parsed_hole = _as_xy_ring(
                posted_hole, "hole" if index == 0 else f"cell {index} hole"
            )
            if isinstance(parsed_hole, Failure):
                views.append(
                    _cell_view_from_parts(
                        index,
                        prefix,
                        display_outer,
                        display_hole,
                        pitches,
                        knees,
                        gambrels,
                        raw_overhang,
                        raw_eave,
                        use_overhang,
                        use_eave,
                        use_hole,
                        set_pitch,
                        extra_holes=extra_display,
                    )
                )
                return views, parsed_hole
            parsed_holes = [parsed_hole]
            display_hole = parsed_hole
            for extra_i, extra_ring in enumerate(extra_display, start=1):
                parsed_extra = _as_xy_ring(
                    extra_ring,
                    f"hole {extra_i}" if index == 0 else f"cell {index} hole {extra_i}",
                )
                if isinstance(parsed_extra, Failure):
                    views.append(
                        _cell_view_from_parts(
                            index,
                            prefix,
                            display_outer,
                            display_hole,
                            pitches,
                            knees,
                            gambrels,
                            raw_overhang,
                            raw_eave,
                            use_overhang,
                            use_eave,
                            use_hole,
                            set_pitch,
                            extra_holes=extra_display,
                        )
                    )
                    return views, parsed_extra
                parsed_extras.append(parsed_extra)
            if parsed_extras:
                parsed_holes.extend(parsed_extras)
        if use_overhang:
            overhang = _posted_overhang(form, 0.0, field=f"{prefix}overhang")
        else:
            overhang = 0.0
        if isinstance(overhang, Failure):
            views.append(
                _cell_view_from_parts(
                    index,
                    prefix,
                    display_outer,
                    display_hole,
                    pitches,
                    knees,
                    gambrels,
                    raw_overhang,
                    raw_eave,
                    use_overhang,
                    use_eave,
                    use_hole,
                    set_pitch,
                )
            )
            return views, overhang
        if use_eave:
            eave_height = _posted_eave_height(form, field=f"{prefix}eave_height")
        else:
            eave_height = 0.0
        if isinstance(eave_height, Failure):
            views.append(
                _cell_view_from_parts(
                    index,
                    prefix,
                    display_outer,
                    display_hole,
                    pitches,
                    knees,
                    gambrels,
                    raw_overhang,
                    raw_eave,
                    use_overhang,
                    use_eave,
                    use_hole,
                    set_pitch,
                )
            )
            return views, eave_height
        views.append(
            CellView(
                index=index,
                title=f"Cell {index + 1}",
                prefix=prefix,
                walls=_wall_views(
                    display_outer,
                    display_hole,
                    pitches,
                    prefix=prefix,
                    knees=knees,
                    gambrels=gambrels,
                    extra_holes=parsed_extras or extra_display,
                ),
                footprint=display_outer,
                hole=display_hole,
                overhang=raw_overhang,
                eave_height=raw_eave,
                use_overhang=use_overhang,
                use_eave=use_eave,
                use_hole=use_hole,
                extra_holes=parsed_extras or extra_display,
            )
        )
        cells.append(
            Cell(
                parsed_outer,
                pitches,
                holes=parsed_holes,
                overhang=overhang,
                eave_height=eave_height,
                knee_height=knees,
                gambrel=_optional_gambrel(gambrels),
            )
        )
        index += 1
    return views, cells


def _cell_view_from_parts(
    index: int,
    prefix: str,
    outer: list[tuple[Any, Any]],
    hole: list[tuple[Any, Any]],
    pitches: list[Pitch],
    knees: list[float] | None,
    gambrels: Sequence[tuple[Pitch, Pitch, float] | None] | None,
    overhang: str,
    eave_height: str,
    use_overhang: bool,
    use_eave: bool,
    use_hole: bool,
    set_pitch: str,
    extra_holes: list[list[tuple[Any, Any]]] | None = None,
) -> CellView:
    extras = extra_holes or []
    if not pitches:
        pitches = [set_pitch] * (
            len(outer) + len(hole) + sum(len(item) for item in extras)
        )
    return CellView(
        index=index,
        title=f"Cell {index + 1}",
        prefix=prefix,
        walls=_wall_views(
            outer,
            hole,
            pitches,
            prefix=prefix,
            knees=knees,
            gambrels=gambrels,
            extra_holes=extras,
        ),
        footprint=outer,
        hole=hole,
        overhang=overhang,
        eave_height=eave_height,
        use_overhang=use_overhang,
        use_eave=use_eave,
        use_hole=use_hole,
        extra_holes=extras,
    )


def _posted_edge_spec(
    form: Mapping[str, str],
    n: int,
    prefix: str,
    set_pitch: str,
) -> (
    tuple[
        list[Pitch],
        list[float],
        list[tuple[Pitch, Pitch, float] | None],
    ]
    | Failure
):
    pitches: list[Pitch] = []
    knees: list[float] = []
    gambrels: list[tuple[Pitch, Pitch, float] | None] = []
    for i in range(n):
        kind = form.get(f"{prefix}type-{i}") or "hip"
        if kind == "gable":
            pitches.append("90")
            knees.append(0.0)
            gambrels.append(None)
            continue
        posted = form.get(f"{prefix}pitch-{i}")
        pitches.append(posted if posted not in (None, "") else set_pitch)
        if kind == "knee":
            parsed_knee = _posted_one_knee(form.get(f"{prefix}knee-{i}"))
            if isinstance(parsed_knee, Failure):
                return parsed_knee
            knees.append(parsed_knee)
            gambrels.append(None)
            continue
        knees.append(0.0)
        if kind == "gambrel":
            parsed_g = _posted_one_gambrel(
                pitches[-1],
                form.get(f"{prefix}gambrel-shallow-{i}"),
                form.get(f"{prefix}gambrel-break-{i}"),
            )
            if isinstance(parsed_g, Failure):
                return parsed_g
            gambrels.append(parsed_g)
        else:
            gambrels.append(None)
    return pitches, knees, gambrels


def _posted_one_knee(raw: str | None) -> float | Failure:
    if raw is None or str(raw).strip() == "":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="knee height must be a finite number of metres, zero or positive",
        )


def _posted_one_gambrel(
    steep: Pitch,
    raw_shallow: str | None,
    raw_break: str | None,
) -> tuple[Pitch, Pitch, float] | Failure | None:
    shallow_blank = raw_shallow is None or str(raw_shallow).strip() == ""
    break_blank = raw_break is None or str(raw_break).strip() == ""
    if shallow_blank or break_blank:
        if not shallow_blank and break_blank:
            return None
        if shallow_blank and not break_blank:
            return Failure(
                kind="degenerate",
                reason="a gambrel needs a shallow pitch and a break height",
            )
        return None
    try:
        height = float(str(raw_break))
    except ValueError:
        return Failure(
            kind="degenerate",
            reason="break height must be a finite number of metres above the eave",
        )
    if not math.isfinite(height) or height <= 0.0:
        return None
    return (steep, str(raw_shallow).strip(), height)


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


def _posted_extra_holes(
    form: Mapping[str, str], prefix: str
) -> list[list[tuple[str, str]]]:
    extras: list[list[tuple[str, str]]] = []
    n = 1
    while True:
        ring = _posted_ring(form, f"{prefix}hole-{n}")
        if ring is None:
            break
        extras.append(ring)
        n += 1
    return extras


def _as_xy_ring(
    points: list[tuple[str, str]],
    name: str,
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


def _posted_dormers(
    form: Mapping[str, str],
) -> tuple[list[DormerView], list[Dormer] | Failure]:
    views: list[DormerView] = []
    items: list[Dormer] = []
    index = 0
    while index < 64:
        if form.get(f"dormer-{index}-x-0") is None:
            break
        ring_display: list[tuple[str, str]] = []
        i = 0
        while True:
            raw_x = form.get(f"dormer-{index}-x-{i}")
            raw_y = form.get(f"dormer-{index}-y-{i}")
            if raw_x is None and raw_y is None:
                break
            ring_display.append((raw_x or "", raw_y or ""))
            i += 1
        while ring_display and ring_display[-1] == ("", ""):
            ring_display.pop()
        n_edges = len(ring_display)
        pitches: list[Pitch] = []
        kinds: list[str] = []
        for j in range(n_edges):
            kind = form.get(f"dormer-{index}-type-{j}") or "hip"
            if kind == "gable" or form.get(f"dormer-{index}-gable-{j}"):
                kinds.append("gable")
                pitches.append("90")
            else:
                kinds.append("hip")
                posted = form.get(f"dormer-{index}-pitch-{j}") or "45"
                pitches.append(posted)
        raw_cell = form.get(f"dormer-{index}-cell") or "0"
        try:
            cell_index = int(raw_cell)
        except ValueError:
            views.append(
                DormerView(
                    index=index,
                    cell_index=0,
                    footprint=ring_display,
                    pitches=[str(p) for p in pitches],
                    kinds=kinds,
                )
            )
            return views, Failure(
                kind="degenerate",
                reason="a dormer names its host cell by integer index",
            )
        views.append(
            DormerView(
                index=index,
                cell_index=cell_index,
                footprint=ring_display,
                pitches=[str(p) for p in pitches],
                kinds=kinds,
            )
        )
        parsed_ring = _as_xy_ring(ring_display, f"dormer {index} ring")
        if isinstance(parsed_ring, Failure):
            return views, parsed_ring
        items.append(Dormer(cell_index, parsed_ring, pitches))
        index += 1
    return views, items


def _dormer_views_from_items(items: Sequence[Dormer]) -> list[DormerView]:
    views: list[DormerView] = []
    for index, item in enumerate(items):
        n = len(item.footprint)
        pitches = _expand_pitches(item.pitch, n)
        kinds = ["gable" if _is_gable(p) else "hip" for p in pitches]
        views.append(
            DormerView(
                index=index,
                cell_index=item.cell_index,
                footprint=list(item.footprint),
                pitches=[
                    "90" if k == "gable" else str(p)
                    for p, k in zip(pitches, kinds, strict=True)
                ],
                kinds=kinds,
            )
        )
    return views


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


def _optional_gambrel(
    items: list[tuple[Pitch, Pitch, float] | None],
) -> list[tuple[Pitch, Pitch, float] | None] | None:
    return items if any(items) else None


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
        lines.append(f"  edge {face.edge_index}: pitch {face.pitch:g}°")
    if not result.validity.is_terrain:
        lines.append("validity.reasons:")
        lines.extend(result.validity.reasons)
    return "\n".join(lines)


def _mesh_fields(
    cells: list[CellView],
    dormers: list[DormerView],
    set_pitch: str,
    *,
    method: str = "skeleton",
    example: str = "",
    roof_height: str | None = None,
    face_graph: list[list[int]] | None = None,
) -> dict[str, str]:
    """Form fields that rebuild the solid currently drawn on the page."""
    fields: dict[str, str] = {"set_pitch": set_pitch, "method": method}
    if example:
        fields["example"] = example
    if method == "experimental" and roof_height:
        fields["roof_height"] = roof_height
    if method == "experimental" and face_graph:
        for index, group in enumerate(face_graph):
            fields[f"face-{index}"] = ",".join(str(wall) for wall in group)
    for cell in cells:
        prefix = cell.prefix
        for i, (x, y) in enumerate(cell.footprint):
            fields[f"{prefix}outer-x-{i}"] = str(x)
            fields[f"{prefix}outer-y-{i}"] = str(y)
        if cell.use_hole:
            fields[f"{prefix}use_hole"] = "on"
            for i, (x, y) in enumerate(cell.hole):
                fields[f"{prefix}hole-x-{i}"] = str(x)
                fields[f"{prefix}hole-y-{i}"] = str(y)
            for n, ring in enumerate(cell.extra_holes, start=1):
                for i, (x, y) in enumerate(ring):
                    fields[f"{prefix}hole-{n}-x-{i}"] = str(x)
                    fields[f"{prefix}hole-{n}-y-{i}"] = str(y)
        if cell.use_overhang:
            fields[f"{prefix}use_overhang"] = "on"
            fields[f"{prefix}overhang"] = cell.overhang
        if cell.use_eave:
            fields[f"{prefix}use_eave_height"] = "on"
            fields[f"{prefix}eave_height"] = cell.eave_height
        for wall in cell.walls:
            fields[wall.type_name] = wall.kind
            fields[wall.pitch_name] = wall.pitch
            if wall.kind == "knee":
                fields[wall.knee_name] = wall.knee
            elif wall.kind == "gambrel":
                fields[wall.shallow_name] = wall.shallow
                fields[wall.break_name] = wall.break_height
    for dormer in dormers:
        fields[f"dormer-{dormer.index}-cell"] = str(dormer.cell_index)
        for i, (x, y) in enumerate(dormer.footprint):
            fields[f"dormer-{dormer.index}-x-{i}"] = str(x)
            fields[f"dormer-{dormer.index}-y-{i}"] = str(y)
        for j, (kind, pitch) in enumerate(
            zip(dormer.kinds, dormer.pitches, strict=True)
        ):
            fields[f"dormer-{dormer.index}-type-{j}"] = kind
            fields[f"dormer-{dormer.index}-pitch-{j}"] = pitch
    return fields


def _shows_solid(result: Roof | Project) -> bool:
    """3D is the terrain branch, plus the documented dormer exception."""
    if result.validity.is_terrain:
        return True
    if not isinstance(result, Project):
        return False
    if not all(item.validity.is_terrain for item in result.roofs):
        return False
    return any("dormer" in reason for reason in result.validity.reasons)


def _draw(
    result: Roof | Project | Failure,
    footprint: list[tuple[Any, Any]],
    holes: list[list[tuple[Any, Any]]] | None,
    overhang: float,
    extra_footprints: list[list[tuple[Any, Any]]] | None = None,
) -> tuple[str | None, str | None, str | None]:
    extras = extra_footprints or []
    numeric_foot = _numeric_ring(footprint)
    numeric_holes = _numeric_holes(holes)
    numeric_extras = [_numeric_ring(ring) for ring in extras]
    if isinstance(result, Failure):
        return (
            None,
            None,
            _embed(
                input_footprint(numeric_foot, numeric_holes, numeric_extras),
                include_js=True,
            ),
        )
    walls: dict[str, Any] = {}
    if overhang != 0.0:
        walls = {"walls": numeric_foot, "wall_holes": numeric_holes}
    if isinstance(result, Project):
        plan_html = _embed(plan_view(result), include_js=True)
        solid_html: str | None = None
        if _shows_solid(result):
            solid_html = _embed(solid_view(result), include_js=False)
        return plan_html, solid_html, None
    plan_html = _embed(plan_view(result, **walls), include_js=True)
    solid_html = None
    if _shows_solid(result):
        solid_html = _embed(solid_view(result, **walls), include_js=False)
    return plan_html, solid_html, None


def _numeric_ring(ring: list[tuple[Any, Any]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for x, y in ring:
        try:
            out.append((float(x), float(y)))
        except (TypeError, ValueError):
            continue
    return out


def _numeric_holes(
    holes: list[list[tuple[Any, Any]]] | None,
) -> list[list[tuple[float, float]]] | None:
    if not holes:
        return None
    return [_numeric_ring(hole) for hole in holes]


def _embed(fig: Any, *, include_js: bool) -> str:
    js: bool | str = "cdn" if include_js else False
    html: str = fig.to_html(full_html=False, include_plotlyjs=js)
    return html
