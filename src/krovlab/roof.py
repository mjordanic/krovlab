"""Public roof value and the one-footprint library entry point.

Call :func:`roof` with a footprint and a pitch. Everything behind that
call — the wavefront, the event queue, the conversion of pitch to weight —
is internal. Composition of several cells is :func:`krovlab.project.project`.
The returned :class:`Roof` is data: faces, arcs, nodes, quantities and a
:class:`Validity` result. It has no rendering concepts and no weight.
Unroofable input is a :class:`Failure` with a ``kind``, never an
exception. Wavefront events are opt-in via ``events=True``;
:func:`topology_hash` hashes incidence, not coordinates. An ``overhang``
is applied by offsetting the footprint before the skeleton runs.
``eave_height`` lifts every node after the terrain is assessed.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, overload

from krovlab._input import Pitch as Pitch
from krovlab._input import (
    check_adjacent_parallel_pitches,
    check_footprint,
    check_holes,
    resolve_gambrels,
    resolve_knee_heights,
    resolve_pitches,
)
from krovlab._offset import apply_overhang
from krovlab._skeleton import skeleton as _skeleton

ArcKind = Literal["ridge", "hip", "eave", "valley", "verge"]
EventKind = Literal["edge", "split"]
FailureKind = Literal[
    "invalid_pitch",
    "pitch_count",
    "self_intersection",
    "degenerate",
    "hole_intersects",
    "unsupported",
    "incomplete",
    "empty",
    "overlap",
    "gable_versus_pitch",
    "unequal_eave_height",
    "gable_versus_knee",
    "gambrel_versus_knee",
    "gambrel_versus_gable",
    "dormer_two_faces",
    "dormer_outside",
    "no_face_graph",
    "unliftable",
]
"""Why :func:`roof`, :func:`krovlab.project.project`, or the experimental
entry point refused.

``invalid_pitch`` — unreadable spelling, or outside ``0 < pitch <= 90``.
``pitch_count`` — a pitch list whose length is not the number of edges.
``self_intersection`` — the footprint crosses itself.
``degenerate`` — a point, a line, coincident consecutive vertices, or no area.
``hole_intersects`` — a hole touches or crosses the outer ring, or another hole.
``unsupported`` — adjacent parallel edges of differing pitch (no unique
    skeleton).
``incomplete`` — the wavefront stopped before the skeleton finished,
    including when every edge is a gable.
``empty`` — ``project`` was given no cells.
``overlap`` — two cells overlap in plan.
``gable_versus_pitch`` — a shared edge is a gable on one cell and pitched
    on the other.
``unequal_eave_height`` — a pitched shared edge sits at two eave heights.
``gable_versus_knee`` — the same edge is a gable and has a knee height.
``gambrel_versus_knee`` — the same edge is a gambrel and has a knee height.
``gambrel_versus_gable`` — the same edge is a gambrel and a gable.
``dormer_two_faces`` — a dormer overlaps two host faces.
``dormer_outside`` — a dormer does not lie on a host face.
``no_face_graph`` — the experimental method was called with neither a
    supplied face graph nor a checkpoint.
``unliftable`` — a supplied face graph could not be lifted into a roof.
"""


@dataclass(frozen=True)
class Validity:
    """Whether the roof is a terrain that satisfies the geometric invariants.

    Checked when the roof is built, so the architect does not have to
    discover a folded or double-covered surface on site. ``is_terrain``
    is true only when every recorded reason is empty.
    """

    is_terrain: bool
    """True when plan areas, planarity, drainage and coverage all hold."""

    reasons: tuple[str, ...]
    """Human-readable failures; empty if and only if ``is_terrain``."""

    @staticmethod
    def assess(
        nodes: tuple[Node, ...],
        faces: tuple[Face, ...],
        arcs: tuple[Arc, ...],
        footprint: list[tuple[float, float]],
        holes: list[list[tuple[float, float]]] | None = None,
    ) -> Validity:
        """Run the terrain invariants on assembled roof data.

        :func:`roof` calls this before returning. A caller holding faces
        that did not come from ``roof`` can ask the same question without
        reaching into the wavefront. ``holes`` are subtracted from the
        footprint area and from terrain sampling.
        """
        from krovlab._validity import assess as assess_geometry

        return assess_geometry(nodes, faces, arcs, footprint, holes)


@dataclass(frozen=True)
class Failure:
    """Why a roof could not be produced.

    Exceptions are reserved for programmer error. Unroofable input comes
    back as a value so a caller processing many footprints can keep going.
    Branch on ``kind``; show ``reason`` to a person.
    """

    kind: FailureKind
    """Machine-readable class of the refusal, so a caller can branch."""

    reason: str
    """Human-readable explanation, suitable to show the architect."""


@dataclass(frozen=True)
class Node:
    """A vertex of the roof, in metres.

    Footprint corners sit at the eave height (zero by default). Skeleton
    nodes (ridge ends, the apex of a hip roof) carry that eave height
    plus the wavefront time at which they were created.
    """

    x: float
    """Plan x, metres."""

    y: float
    """Plan y, metres."""

    height: float
    """Height above datum, metres."""


@dataclass(frozen=True)
class Face:
    """One planar piece of the roof.

    The skeleton's face rises from one footprint edge. An experimental
    face may span several walls.
    """

    edge_index: int
    """Index of the caller's footprint edge this face rises from.

    Edge ``i`` runs from ``footprint[i]`` to ``footprint[(i + 1) % n]``
    on the outer ring, then continues through each hole in order, even
    if a ring was reversed internally to put the roofed region on the left.
    """

    pitch: float
    """Angle from horizontal, in degrees."""

    plan_area: float
    """Area of the face projected onto the horizontal, square metres."""

    sloped_area: float
    """True surface area (``plan_area / cos(pitch)``), square metres.

    This is what covering material is bought by.
    """

    node_indices: tuple[int, ...]
    """``Roof.nodes`` indices walking the face boundary, eave first."""

    eave_indices: tuple[int, ...] = ()
    """Caller-edge indices this face drains to. Empty means ``(edge_index,)``."""


@dataclass(frozen=True)
class Arc:
    """A named edge of the roof: an eave, a hip, a valley, or a ridge."""

    start: int
    """Index into ``Roof.nodes``."""

    end: int
    """Index into ``Roof.nodes``."""

    kind: ArcKind
    """``"eave"``, ``"hip"`` (rising from a convex corner), ``"valley"``
    (rising from a reflex corner), ``"ridge"`` (horizontal, both ends
    above the eave), or ``"verge"`` (the roof meeting a gable wall)."""

    length: float
    """True 3D length in metres — the figure that is priced per metre."""


@dataclass(frozen=True)
class Event:
    """One wavefront event the algorithm processed, in order.

    Time is height in metres, so the log can be read against the finished
    roof. ``edges`` are the caller's footprint-edge indices; ``vertices``
    are indices into ``Roof.nodes``. Not part of a roof's meaning — only
    returned when :func:`roof` is asked for ``events=True``.
    """

    kind: EventKind
    """``"edge"``: a wavefront edge vanished. ``"split"``: a reflex
    vertex hit an opposite edge and the wavefront divided, or two
    wavefronts merged (a hole meeting the outer ring)."""

    time: float
    """Height at which the event occurred, metres above the eave plane."""

    edges: tuple[int, ...]
    """Caller footprint-edge indices involved.

    Edge events: left support, vanishing edge, right support. Split
    events: the reflex vertex's two supports and the opposite edge.
    """

    vertices: tuple[int, ...]
    """``Roof.nodes`` indices of the tracing sources, then the resulting node."""


@dataclass(frozen=True)
class Roof:
    """A roof as data: faces, arcs, nodes, quantities and a validity result."""

    nodes: tuple[Node, ...]
    """Every vertex, including the original footprint corners at eave height."""

    faces: tuple[Face, ...]
    """One face per non-gabled footprint edge, in the caller's edge order.

    A gambrel edge contributes two faces, steep then shallow.
    """

    arcs: tuple[Arc, ...]
    """Eaves, hips, valleys, ridges and verges, each with a 3D length."""

    ridge_height: float
    """Highest node on the roof, metres above datum."""

    total_sloped_area: float
    """Sum of every face's sloped area — the covering-cost driver."""

    validity: Validity
    """Result of checking this roof against the terrain invariants."""


def topology_hash(roof: Roof) -> str:
    """Stable hash of which faces meet which arcs at which nodes.

    Coordinates, lengths, areas, heights and arc classification are
    ignored, so a small perturbation that does not change incidence
    leaves the hash unchanged. Uses SHA-256, so the same roof hashes
    the same across processes.
    """
    incident: dict[int, set[int]] = {}
    for face in roof.faces:
        for idx in face.node_indices:
            incident.setdefault(idx, set()).add(face.edge_index)

    def node_id(index: int) -> tuple[int, ...]:
        return tuple(sorted(incident.get(index, ())))

    faces: list[tuple[int, tuple[tuple[int, ...], ...]]] = []
    for face in sorted(roof.faces, key=lambda item: item.edge_index):
        ids = [node_id(idx) for idx in face.node_indices]
        faces.append((face.edge_index, _canonical_cycle(ids)))

    arcs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for arc in roof.arcs:
        left, right = node_id(arc.start), node_id(arc.end)
        if left > right:
            left, right = right, left
        arcs.append((left, right))
    arcs.sort()

    payload = repr((tuple(faces), tuple(arcs))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_cycle(
    ids: list[tuple[int, ...]],
) -> tuple[tuple[int, ...], ...]:
    """Rotate a face cycle so it starts at its lexicographically least node."""
    start = min(range(len(ids)), key=lambda i: ids[i])
    return tuple(ids[start:] + ids[:start])


@overload
def roof(
    footprint: list[tuple[float, float]],
    pitch: Pitch | list[Pitch],
    holes: list[list[tuple[float, float]]] | None = None,
    overhang: float = 0.0,
    eave_height: float = 0.0,
    knee_height: float | list[float] = 0.0,
    gambrel: Sequence[tuple[Pitch, Pitch, float] | None] | None = None,
    *,
    events: Literal[False] = False,
) -> Roof | Failure: ...


@overload
def roof(
    footprint: list[tuple[float, float]],
    pitch: Pitch | list[Pitch],
    holes: list[list[tuple[float, float]]] | None = None,
    overhang: float = 0.0,
    eave_height: float = 0.0,
    knee_height: float | list[float] = 0.0,
    gambrel: Sequence[tuple[Pitch, Pitch, float] | None] | None = None,
    *,
    events: Literal[True],
) -> tuple[Roof, tuple[Event, ...]] | Failure: ...


def roof(
    footprint: list[tuple[float, float]],
    pitch: Pitch | list[Pitch],
    holes: list[list[tuple[float, float]]] | None = None,
    overhang: float = 0.0,
    eave_height: float = 0.0,
    knee_height: float | list[float] = 0.0,
    gambrel: Sequence[tuple[Pitch, Pitch, float] | None] | None = None,
    *,
    events: bool = False,
) -> Roof | Failure | tuple[Roof, tuple[Event, ...]]:
    """Build a roof over a footprint, including any holes.

    Parameters
    ----------
    footprint
        Plan vertices ``(x, y)`` in metres. Either winding is accepted;
        a closing duplicate of the first point is ignored. Mid-ring
        coincident vertices, a ring with no area, and a self-intersecting
        ring are refused. Collinear vertices that still enclose area are
        kept — they are the same building with an extra point on an eave.
    pitch
        One slope for every face, or a list with one value per edge.
        Each value is degrees, a ``(rise, run)`` pair, ``"4:12"``, or
        ``"100%"``. After conversion the angle must satisfy
        ``0 < pitch <= 90``. ``pitch = 90`` is a gable: that edge
        produces no face, and the neighbouring faces meet the wall at
        verges. A list of mixed spellings of the same slope is the same
        as a single value. Differing pitches weight the wavefront;
        adjacent parallel edges of differing pitch are refused (no
        unique skeleton). Gabling every edge, or enough that the roof
        cannot close, is ``incomplete``.
    holes
        Interior rings the roof does not cover, or ``None``. Either
        winding is accepted. A hole that touches or crosses the outer
        ring, or another hole, is refused by name. Pitch lists are one
        value per edge of the outer ring then each hole in order.
    overhang
        Eaves projection in metres. The footprint is offset outward (holes
        inward) and the roof of that larger footprint is generated. Zero
        is the same as omitting the argument. A value that closes a hole
        or folds the footprint is a named ``Failure``.
    eave_height
        Plate height in metres above datum, added to every node after the
        roof is built and assessed at the eave plane. Zero is the same as
        omitting the argument.
    knee_height
        Metres of vertical wall on an edge before that edge's pitch
        begins. One value for every edge, or a list with one value per
        edge. Zero on every edge is the same as omitting the argument.
        A gable (pitch 90) with a non-zero knee on the same edge is
        ``gable_versus_knee``.
    gambrel
        One optional barn break per footprint edge: ``(steep, shallow,
        break_height)`` or ``None``. Break height is metres above that
        cell's eave. Omitting it, or ``None`` on every edge, is a
        single pitch per wall. A gambrel with a knee on the same edge
        is ``gambrel_versus_knee``. A gambrel with a gable on the same
        edge is ``gambrel_versus_gable``.
    events
        If true, return ``(Roof, events)`` so the processed wavefront
        events can be inspected in order. The roof itself is unchanged;
        callers that omit this flag are not handed debugging state.

    Returns
    -------
    Roof
        Faces, arcs, nodes, quantities, and a :class:`Validity` result
        that records whether the roof is a terrain. Every length is
        metres; every angle is degrees. Reflex corners produce valleys.
        A gabled edge (``pitch = 90``) produces no face and two verges.
    tuple[Roof, tuple[Event, ...]]
        The same roof, plus the event log, when ``events=True``.
    Failure
        Named refusal. Branch on ``kind``; show ``reason`` to a person.
        Nothing this function accepts as input raises.

    Examples
    --------
    >>> from krovlab import Failure, Roof, roof
    >>> result = roof([(0, 0), (10, 0), (10, 10), (0, 10)], 45)
    >>> isinstance(result, Roof)
    True
    >>> result.validity.is_terrain
    True
    >>> round(result.ridge_height, 6)
    5.0
    >>> roof([(0, 0), (10, 10), (10, 0), (0, 10)], 45).kind
    'self_intersection'
    """
    cleaned = check_footprint(footprint)
    if isinstance(cleaned, Failure):
        return cleaned
    cleaned_holes = check_holes(holes, cleaned)
    if isinstance(cleaned_holes, Failure):
        return cleaned_holes
    if isinstance(overhang, bool) or not isinstance(overhang, (int, float)):
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )
    if not math.isfinite(overhang) or overhang < 0.0:
        return Failure(
            kind="degenerate",
            reason="overhang must be a finite number of metres, zero or positive",
        )
    if isinstance(eave_height, bool) or not isinstance(eave_height, (int, float)):
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )
    if not math.isfinite(eave_height):
        return Failure(
            kind="degenerate",
            reason="eave height must be a finite number of metres above datum",
        )
    n_edges = len(cleaned) + sum(len(h) for h in cleaned_holes)
    parsed = resolve_pitches(pitch, n_edges)
    if isinstance(parsed, Failure):
        return parsed
    knees = resolve_knee_heights(knee_height, n_edges)
    if isinstance(knees, Failure):
        return knees
    for pitch_deg, knee in zip(parsed, knees, strict=True):
        if pitch_deg >= 90.0 and knee > 0.0:
            return Failure(
                kind="gable_versus_knee",
                reason="a gable cannot also have a knee height",
            )
    gambrels = resolve_gambrels(gambrel, n_edges)
    if isinstance(gambrels, Failure):
        return gambrels
    for i, item in enumerate(gambrels):
        if item is None:
            continue
        steep, shallow, _break_height = item
        if knees[i] > 0.0:
            return Failure(
                kind="gambrel_versus_knee",
                reason="a gambrel cannot also have a knee height",
            )
        if parsed[i] >= 90.0 or steep >= 90.0 or shallow >= 90.0:
            return Failure(
                kind="gambrel_versus_gable",
                reason="a gambrel cannot also be a gable",
            )
        parsed[i] = steep
    expanded = apply_overhang(cleaned, cleaned_holes, float(overhang))
    if isinstance(expanded, Failure):
        return expanded
    cleaned, cleaned_holes = expanded
    rings, edge_map = _oriented_rings(cleaned, cleaned_holes)
    # Caller pitches, permuted onto the oriented rings. Weight is the
    # wavefront's plan speed: cot(pitch) so a steeper face moves inward
    # more slowly. Converted here and nowhere else.
    ring_pitches = [parsed[edge_map[i]] for i in range(len(edge_map))]
    ring_knees = [knees[edge_map[i]] for i in range(len(edge_map))]
    ring_gambrels = [gambrels[edge_map[i]] for i in range(len(edge_map))]
    offset = 0
    for ring in rings:
        m = len(ring)
        conflict = check_adjacent_parallel_pitches(
            ring, ring_pitches[offset : offset + m]
        )
        if conflict is not None:
            return conflict
        offset += m
    weights = [_pitch_to_weight(p) for p in ring_pitches]
    if all(w == 0.0 for w in weights):
        return Failure(
            kind="incomplete",
            reason="every edge is a gable (pitch = 90); no roof can close",
        )
    seconds = [
        _pitch_to_weight(item[1]) if item is not None else w
        for item, w in zip(ring_gambrels, weights, strict=True)
    ]
    break_times = [item[2] if item is not None else math.inf for item in ring_gambrels]
    use_motion = any(k > 0.0 for k in ring_knees) or any(
        item is not None for item in ring_gambrels
    )
    raw = (
        _skeleton(
            rings,
            weights,
            delays=ring_knees,
            second_weights=seconds,
            breaks=break_times,
        )
        if use_motion
        else _skeleton(rings, weights)
    )
    if not raw.complete:
        return Failure(
            kind="incomplete",
            reason="the wavefront did not finish; the roof could not be produced",
        )
    built = _roof_from_skeleton(
        rings,
        ring_pitches,
        ring_knees,
        raw.nodes,
        raw.arcs,
        raw.activations,
        edge_map,
        cleaned,
        cleaned_holes,
        float(eave_height),
        gambrels=ring_gambrels,
        breaks=raw.breaks,
    )
    if not events:
        return built
    log = tuple(
        Event(
            kind="split" if ev.kind == "split" else "edge",
            time=ev.time,
            edges=tuple(edge_map[i] for i in ev.edges),
            vertices=ev.vertices,
        )
        for ev in raw.events
    )
    return built, log


def _pitch_to_weight(pitch: float) -> float:
    """Return ``cot(pitch)``, the multiplicative wavefront speed.

    ``pitch == 90`` is the vertical-face case: the edge does not move
    (weight 0). ``tan(90°)`` is undefined, so that bound is special-cased.
    """
    if pitch >= 90.0:
        return 0.0
    return 1.0 / math.tan(math.radians(pitch))


def _oriented_ring(
    footprint: list[tuple[float, float]], *, clockwise: bool
) -> tuple[list[tuple[float, float]], list[int]]:
    """Orient a ring and map skeleton edges back to the caller's order.

    The skeleton walks with the roofed region on the left: outer rings
    counter-clockwise, holes clockwise. If the input winding disagrees
    we reverse it, but ``edge_map[i]`` still names the caller's original
    edge so ``Face.edge_index`` matches the list they passed in.
    """
    pts = list(footprint)
    n = len(pts)
    edge_map = list(range(n))
    area = _signed_area(pts)
    needs_reverse = (area > 0.0) if clockwise else (area < 0.0)
    if needs_reverse:
        pts = [pts[0], *reversed(pts[1:])]
        edge_map = [(n - 1 - i) % n for i in range(n)]
    return pts, edge_map


def _oriented_rings(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> tuple[list[list[tuple[float, float]]], list[int]]:
    """Outer CCW then holes CW, with a concatenated caller edge map."""
    rings: list[list[tuple[float, float]]] = []
    edge_map: list[int] = []
    caller_offset = 0
    ring, emap = _oriented_ring(outer, clockwise=False)
    rings.append(ring)
    edge_map.extend(caller_offset + i for i in emap)
    caller_offset += len(outer)
    for hole in holes:
        ring, emap = _oriented_ring(hole, clockwise=True)
        rings.append(ring)
        edge_map.extend(caller_offset + i for i in emap)
        caller_offset += len(hole)
    return rings, edge_map


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area. Positive means counter-clockwise."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return 0.5 * total


def _next_indices(rings: list[list[tuple[float, float]]]) -> list[int]:
    """Concatenated next-vertex index, wrapping inside each ring."""
    next_idx: list[int] = []
    for ring in rings:
        origin = len(next_idx)
        m = len(ring)
        next_idx.extend(origin + (j + 1) % m for j in range(m))
    return next_idx


def _roof_from_skeleton(
    rings: list[list[tuple[float, float]]],
    pitches: list[float],
    delays: list[float],
    raw_nodes: tuple[tuple[float, float, float], ...],
    raw_arcs: tuple[tuple[int, int, int, int], ...],
    activations: tuple[tuple[int, int, int], ...],
    edge_map: list[int],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    eave_height: float,
    gambrels: list[tuple[float, float, float] | None] | None = None,
    breaks: tuple[tuple[int, int, int], ...] = (),
) -> Roof:
    """Assemble a :class:`Roof` from the raw skeleton graph."""
    if all(d == 0.0 for d in delays):
        built = _roof_from_plain_skeleton(
            rings,
            pitches,
            raw_nodes,
            raw_arcs,
            edge_map,
            footprint,
            holes,
            eave_height,
            gambrels=gambrels,
            breaks=breaks,
        )
        return built
    return _roof_from_kneed_skeleton(
        rings,
        pitches,
        delays,
        raw_nodes,
        raw_arcs,
        activations,
        edge_map,
        footprint,
        holes,
        eave_height,
    )


def _roof_from_plain_skeleton(
    rings: list[list[tuple[float, float]]],
    pitches: list[float],
    raw_nodes: tuple[tuple[float, float, float], ...],
    raw_arcs: tuple[tuple[int, int, int, int], ...],
    edge_map: list[int],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    eave_height: float,
    gambrels: list[tuple[float, float, float] | None] | None = None,
    breaks: tuple[tuple[int, int, int], ...] = (),
) -> Roof:
    """Assemble a roof when every knee height is zero."""
    nodes = tuple(Node(x, y, h) for x, y, h in raw_nodes)
    next_idx = _next_indices(rings)
    n = len(next_idx)
    gabled = [p >= 90.0 for p in pitches]
    adj: list[dict[int, list[int]]] = [{} for _ in range(n)]

    def _link(face: int, a: int, b: int) -> None:
        nbrs = adj[face].setdefault(a, [])
        if b not in nbrs:
            nbrs.append(b)
        nbrs_b = adj[face].setdefault(b, [])
        if a not in nbrs_b:
            nbrs_b.append(a)

    arcs: list[Arc] = []
    for i in range(n):
        a, b = i, next_idx[i]
        if gabled[i]:
            continue
        _link(i, a, b)
        arcs.append(
            Arc(start=a, end=b, kind="eave", length=_node_distance(nodes[a], nodes[b]))
        )

    height_tol = 1e-9
    for a, b, face_a, face_b in raw_arcs:
        if gabled[face_a] and gabled[face_b]:
            continue
        if not gabled[face_a]:
            _link(face_a, a, b)
        if not gabled[face_b]:
            _link(face_b, a, b)
        if gabled[face_a] or gabled[face_b]:
            kind: ArcKind = "verge"
        else:
            kind = _classify_arc(nodes[a], nodes[b], rings, height_tol)
        arcs.append(
            Arc(start=a, end=b, kind=kind, length=_node_distance(nodes[a], nodes[b]))
        )

    faces: list[Face] = []
    for i in range(n):
        if gabled[i]:
            continue
        cycle = _walk_cycle(adj[i], i, next_idx[i])
        plan_area = abs(_signed_area([(nodes[j].x, nodes[j].y) for j in cycle]))
        cos_pitch = math.cos(math.radians(pitches[i]))
        sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
        faces.append(
            Face(
                edge_index=edge_map[i],
                pitch=pitches[i],
                plan_area=plan_area,
                sloped_area=sloped_area,
                node_indices=tuple(cycle),
            )
        )
    if gambrels is not None and any(item is not None for item in gambrels):
        faces = _split_gambrel_faces(faces, nodes, gambrels, breaks, edge_map)
    return _finish_roof(nodes, faces, arcs, footprint, holes, eave_height)


def _roof_from_kneed_skeleton(
    rings: list[list[tuple[float, float]]],
    pitches: list[float],
    delays: list[float],
    raw_nodes: tuple[tuple[float, float, float], ...],
    raw_arcs: tuple[tuple[int, int, int, int], ...],
    activations: tuple[tuple[int, int, int], ...],
    edge_map: list[int],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    eave_height: float,
) -> Roof:
    nodes = tuple(Node(x, y, h) for x, y, h in raw_nodes)
    next_idx = _next_indices(rings)
    n = len(next_idx)
    gabled = [p >= 90.0 for p in pitches]
    knee_eave = {edge: (a, b) for edge, a, b in activations}
    no_face = [gabled[i] or (delays[i] > 0.0 and i not in knee_eave) for i in range(n)]
    # Per-face adjacency of node indices, used to walk each face cycle.
    adj: list[dict[int, list[int]]] = [{} for _ in range(n)]

    def _link(face: int, a: int, b: int) -> None:
        nbrs = adj[face].setdefault(a, [])
        if b not in nbrs:
            nbrs.append(b)
        nbrs_b = adj[face].setdefault(b, [])
        if a not in nbrs_b:
            nbrs_b.append(a)

    eave_from: list[int] = list(range(n))
    eave_to: list[int] = list(next_idx)
    arcs: list[Arc] = []
    for i in range(n):
        if no_face[i]:
            continue
        if i in knee_eave:
            a, b = knee_eave[i]
            eave_from[i] = a
            eave_to[i] = b
        else:
            a, b = i, next_idx[i]
        _link(i, a, b)
        arcs.append(
            Arc(start=a, end=b, kind="eave", length=_node_distance(nodes[a], nodes[b]))
        )

    height_tol = 1e-9
    for a, b, face_a, face_b in raw_arcs:
        if no_face[face_a] and no_face[face_b]:
            continue
        on_knee_wall = _arc_on_knee_wall(
            nodes[a], nodes[b], face_a, face_b, delays, rings, next_idx
        )
        if no_face[face_a] or no_face[face_b] or on_knee_wall:
            kind: ArcKind = "verge"
        else:
            kind = _classify_arc(nodes[a], nodes[b], rings, height_tol)
        for face in (face_a, face_b):
            if no_face[face]:
                continue
            if delays[face] > 0.0 and _nodes_on_oriented_edge(
                nodes[a], nodes[b], face, rings, next_idx
            ):
                continue
            _link(face, a, b)
        arcs.append(
            Arc(start=a, end=b, kind=kind, length=_node_distance(nodes[a], nodes[b]))
        )

    faces: list[Face] = []
    for i in range(n):
        if no_face[i]:
            continue
        cycle = _walk_cycle(adj[i], eave_from[i], eave_to[i])
        plan_area = abs(_signed_area([(nodes[j].x, nodes[j].y) for j in cycle]))
        cos_pitch = math.cos(math.radians(pitches[i]))
        sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
        faces.append(
            Face(
                edge_index=edge_map[i],
                pitch=pitches[i],
                plan_area=plan_area,
                sloped_area=sloped_area,
                node_indices=tuple(cycle),
            )
        )

    return _finish_roof(nodes, faces, arcs, footprint, holes, eave_height)


def _plan_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    tol: float,
) -> bool:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-24:
        return math.hypot(apx, apy) <= tol
    along = (apx * abx + apy * aby) / ab2
    if along < -1e-9 or along > 1.0 + 1e-9:
        return False
    dist = abs(apx * aby - apy * abx) / math.sqrt(ab2)
    return dist <= tol


def _nodes_on_oriented_edge(
    a: Node,
    b: Node,
    edge_i: int,
    rings: list[list[tuple[float, float]]],
    next_idx: list[int],
    tol: float = 1e-6,
) -> bool:
    pts: list[tuple[float, float]] = []
    for ring in rings:
        pts.extend(ring)
    start = pts[edge_i]
    end = pts[next_idx[edge_i]]
    return _plan_on_segment(a.x, a.y, *start, *end, tol) and _plan_on_segment(
        b.x, b.y, *start, *end, tol
    )


def _arc_on_knee_wall(
    a: Node,
    b: Node,
    face_a: int,
    face_b: int,
    delays: list[float],
    rings: list[list[tuple[float, float]]],
    next_idx: list[int],
) -> bool:
    for face in (face_a, face_b):
        if delays[face] > 0.0 and _nodes_on_oriented_edge(a, b, face, rings, next_idx):
            return True
    return False


def _split_gambrel_faces(
    faces: list[Face],
    nodes: tuple[Node, ...],
    gambrels: list[tuple[float, float, float] | None],
    breaks: tuple[tuple[int, int, int], ...],
    edge_map: list[int],
) -> list[Face]:
    """Split each gambrel wall into a steep band then a shallow band."""
    break_of = {edge: (start, end) for edge, start, end in breaks}
    caller_to_ring = {caller: ring for ring, caller in enumerate(edge_map)}
    split: list[Face] = []
    for face in faces:
        ring_i = caller_to_ring.get(face.edge_index)
        if ring_i is None:
            split.append(face)
            continue
        item = gambrels[ring_i] if ring_i < len(gambrels) else None
        pair = break_of.get(ring_i)
        if item is None or pair is None:
            split.append(face)
            continue
        steep, shallow, _height = item
        steep_cycle, shallow_cycle = _gambrel_cycles(face.node_indices, pair)
        if steep_cycle is None or shallow_cycle is None:
            split.append(
                Face(
                    edge_index=face.edge_index,
                    pitch=steep,
                    plan_area=face.plan_area,
                    sloped_area=face.sloped_area,
                    node_indices=face.node_indices,
                    eave_indices=face.eave_indices,
                )
            )
            continue
        split.append(_face_from_cycle(face.edge_index, steep, steep_cycle, nodes))
        split.append(_face_from_cycle(face.edge_index, shallow, shallow_cycle, nodes))
    return split


def _gambrel_cycles(
    cycle: tuple[int, ...],
    pair: tuple[int, int],
) -> tuple[list[int], list[int]] | tuple[None, None]:
    """Split a face cycle at the two break nodes into steep then shallow rings."""
    nodes = list(cycle)
    if pair[0] not in nodes or pair[1] not in nodes:
        return None, None
    i = nodes.index(pair[0])
    j = nodes.index(pair[1])
    if i == j:
        return None, None
    if i > j:
        i, j = j, i
    steep_cycle = nodes[: i + 1] + nodes[j:]
    shallow_cycle = nodes[i : j + 1]
    if len(steep_cycle) < 3 or len(shallow_cycle) < 3:
        return None, None
    return steep_cycle, shallow_cycle


def _face_from_cycle(
    edge_index: int,
    pitch: float,
    cycle: list[int],
    nodes: tuple[Node, ...],
) -> Face:
    plan_area = abs(_signed_area([(nodes[j].x, nodes[j].y) for j in cycle]))
    cos_pitch = math.cos(math.radians(pitch))
    sloped_area = plan_area / cos_pitch if cos_pitch != 0.0 else plan_area
    return Face(
        edge_index=edge_index,
        pitch=pitch,
        plan_area=plan_area,
        sloped_area=sloped_area,
        node_indices=tuple(cycle),
    )


def _finish_roof(
    nodes: tuple[Node, ...],
    faces: list[Face],
    arcs: list[Arc],
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    eave_height: float,
) -> Roof:
    built_faces = tuple(faces)
    built_arcs = tuple(arcs)
    validity = Validity.assess(nodes, built_faces, built_arcs, footprint, holes)
    if eave_height != 0.0:
        nodes = tuple(Node(node.x, node.y, node.height + eave_height) for node in nodes)
    return Roof(
        nodes=nodes,
        faces=built_faces,
        arcs=built_arcs,
        ridge_height=max(node.height for node in nodes),
        total_sloped_area=sum(face.sloped_area for face in faces),
        validity=validity,
    )


def _classify_arc(
    a: Node,
    b: Node,
    rings: list[list[tuple[float, float]]],
    height_tol: float,
) -> ArcKind:
    """Ridge if level and above the eave; hip/valley from the eave-end corner."""
    if min(a.height, b.height) > height_tol and abs(a.height - b.height) <= height_tol:
        return "ridge"
    for end in (a, b):
        if end.height > height_tol:
            continue
        best_ring = rings[0]
        best_corner = 0
        best_dist = float("inf")
        for ring in rings:
            for i, (x, y) in enumerate(ring):
                dist = math.hypot(x - end.x, y - end.y)
                if dist < best_dist:
                    best_dist = dist
                    best_ring = ring
                    best_corner = i
        return "hip" if _ring_vertex_is_convex(best_ring, best_corner) else "valley"
    return "hip"


def _ring_vertex_is_convex(ring: list[tuple[float, float]], index: int) -> bool:
    """True if the ring turns toward the roofed region (left) at ``index``."""
    n = len(ring)
    ax, ay = ring[(index - 1) % n]
    bx, by = ring[index]
    cx, cy = ring[(index + 1) % n]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0.0


def _walk_cycle(adj: dict[int, list[int]], start: int, second: int) -> list[int]:
    """Walk the face polygon starting along the eave ``start -> second``."""
    cycle = [start]
    prev, cur = start, second
    seen = {start}
    while cur != start:
        cycle.append(cur)
        if cur in seen:
            break
        seen.add(cur)
        nxts = [n for n in adj.get(cur, []) if n != prev]
        if not nxts:
            break
        prev, cur = cur, nxts[0]
    return cycle


def _node_distance(a: Node, b: Node) -> float:
    """3D Euclidean distance between two nodes, in metres."""
    return math.hypot(a.x - b.x, a.y - b.y, a.height - b.height)
