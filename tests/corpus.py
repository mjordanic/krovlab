"""Load and run the footprint corpus.

A fixture is a TOML file. Adding one to the corpus is dropping a file
in the fixtures directory — no new test function. Each file is fed
through ``roof`` and the named invariant checks; passing files record a
topology hash; unroofable files record an expected ``Failure.kind``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from shapely.geometry import JOIN_STYLE, Polygon  # type: ignore[import-untyped]

from invariants import (
    arc_classification_matches_geometry,
    drainage_runs_to_each_faces_own_eave,
    every_face_is_planar,
    plan_areas_sum_to_footprint_area,
    roof_is_a_terrain,
    sloped_area_is_at_least_plan_area,
)
from krovlab import Failure, Pitch, Roof, roof, topology_hash

Outcome = Literal[
    "pass",
    "invariant_failure",
    "expected_failure",
    "unexpected_failure",
    "hash_mismatch",
]


@dataclass(frozen=True)
class Fixture:
    """One footprint as committed in the corpus directory."""

    name: str
    footprint: list[tuple[float, float]]
    pitch: float | list[float]
    holes: list[list[tuple[float, float]]] | None
    overhang: float
    expected_failure: str | None
    topology_hash: str | None


def load_fixtures(directory: Path) -> list[Fixture]:
    """Every single-footprint ``*.toml`` in ``directory``, sorted by name.

    Multi-cell project fixtures (a ``cells`` table, no top-level
    ``footprint``) live in the same directory for the page dropdown but
    are not fed through ``roof``.
    """
    fixtures: list[Fixture] = []
    for path in sorted(directory.glob("*.toml")):
        loaded = _load_fixture(path)
        if loaded is not None:
            fixtures.append(loaded)
    return fixtures


def _load_fixture(path: Path) -> Fixture | None:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if "cells" in data and "footprint" not in data:
        return None
    holes_raw = data.get("holes")
    holes: list[list[tuple[float, float]]] | None
    if holes_raw is None:
        holes = None
    elif isinstance(holes_raw, list):
        holes = [_as_ring(ring) for ring in holes_raw]
    else:
        raise TypeError(f"holes must be a list of rings, got {holes_raw!r}")
    return Fixture(
        name=path.stem,
        footprint=_as_ring(data["footprint"]),
        pitch=_as_pitch(data["pitch"]),
        holes=holes,
        overhang=float(data.get("overhang", 0.0)),
        expected_failure=_optional_str(data.get("expected_failure")),
        topology_hash=_optional_str(data.get("topology_hash")),
    )


@dataclass(frozen=True)
class FixtureResult:
    """How one fixture fared against ``roof`` and the invariant harness."""

    name: str
    outcome: Outcome
    property: str | None
    topology_hash: str | None
    detail: str


def run_fixture(fixture: Fixture) -> FixtureResult:
    """Feed one fixture through ``roof`` and the named invariant checks."""
    produced = roof(
        fixture.footprint,
        cast(float | list[Pitch], fixture.pitch),
        holes=fixture.holes,
        overhang=fixture.overhang,
    )
    if isinstance(produced, Failure):
        if fixture.expected_failure is None:
            return FixtureResult(
                name=fixture.name,
                outcome="unexpected_failure",
                property=produced.kind,
                topology_hash=None,
                detail=produced.reason,
            )
        if produced.kind == fixture.expected_failure:
            return FixtureResult(
                name=fixture.name,
                outcome="expected_failure",
                property=produced.kind,
                topology_hash=None,
                detail=produced.reason,
            )
        return FixtureResult(
            name=fixture.name,
            outcome="unexpected_failure",
            property=produced.kind,
            topology_hash=None,
            detail=(
                f"expected {fixture.expected_failure}, got {produced.kind}: "
                f"{produced.reason}"
            ),
        )
    if fixture.expected_failure is not None:
        return FixtureResult(
            name=fixture.name,
            outcome="unexpected_failure",
            property=None,
            topology_hash=None,
            detail=f"expected {fixture.expected_failure}, got a roof",
        )
    return _check_invariants(fixture, produced)


def _check_invariants(fixture: Fixture, built: Roof) -> FixtureResult:
    roofed, roofed_holes = _roofed_rings(
        fixture.footprint, fixture.holes or [], fixture.overhang
    )
    try:
        plan_areas_sum_to_footprint_area(built, roofed, roofed_holes)
        every_face_is_planar(built)
        sloped_area_is_at_least_plan_area(built)
        roof_is_a_terrain(built, roofed, roofed_holes)
        drainage_runs_to_each_faces_own_eave(built, roofed, roofed_holes)
        arc_classification_matches_geometry(built, roofed, roofed_holes)
    except AssertionError as exc:
        message = str(exc)
        property_name = message.split(":", 1)[0]
        return FixtureResult(
            name=fixture.name,
            outcome="invariant_failure",
            property=property_name,
            topology_hash=None,
            detail=message,
        )
    digest = topology_hash(built)
    if fixture.topology_hash is not None and digest != fixture.topology_hash:
        return FixtureResult(
            name=fixture.name,
            outcome="hash_mismatch",
            property="topology hash",
            topology_hash=digest,
            detail=f"recorded {fixture.topology_hash}, got {digest}",
        )
    return FixtureResult(
        name=fixture.name,
        outcome="pass",
        property=None,
        topology_hash=digest,
        detail="",
    )


def _roofed_rings(
    footprint: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
    overhang: float,
) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    """The polygon the roof covers, matching ticket 02's overhang offset."""
    if overhang == 0.0:
        return footprint, holes
    buffered = Polygon(footprint, holes).buffer(
        overhang, join_style=JOIN_STYLE.mitre, mitre_limit=1000.0
    )
    exterior = _align_ring(footprint, list(buffered.exterior.coords)[:-1])
    interiors = [
        _align_ring(hole, list(ring.coords)[:-1])
        for hole, ring in zip(holes, buffered.interiors, strict=True)
    ]
    return exterior, interiors


def _align_ring(
    original: list[tuple[float, float]],
    buffered: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    if len(original) != len(buffered):
        return buffered
    used: set[int] = set()
    aligned: list[tuple[float, float]] = []
    for ox, oy in original:
        best = min(
            (i for i in range(len(buffered)) if i not in used),
            key=lambda i: (buffered[i][0] - ox) ** 2 + (buffered[i][1] - oy) ** 2,
        )
        used.add(best)
        aligned.append(buffered[best])
    return aligned


def _optional_str(raw: object) -> str | None:
    if raw is None:
        return None
    return str(raw)


CORPUS_DIR = Path(__file__).resolve().parent / "fixtures" / "footprints"
REPORT_PATH = Path(__file__).resolve().parents[1] / "docs" / "footprint-corpus.md"

SOURCE_NOTE = (
    "These fixtures are stand-ins from the library's worked examples, "
    "not yet sourced from the architect's recent projects."
)


def render_report(results: list[FixtureResult]) -> str:
    """Pass rate, named failures, and expected-unroofable fixtures."""
    expected = [item for item in results if item.outcome == "expected_failure"]
    roofable = [item for item in results if item.outcome != "expected_failure"]
    passed = [item for item in roofable if item.outcome == "pass"]
    failed = [item for item in roofable if item.outcome != "pass"]
    n_pass = len(passed)
    n_roofable = len(roofable)
    percent = 0.0 if n_roofable == 0 else 100.0 * n_pass / n_roofable
    lines = [
        "# Footprint corpus",
        "",
        SOURCE_NOTE,
        "",
        f"The corpus covers {len(results)} footprint"
        f"{'' if len(results) == 1 else 's'}.",
        "",
        f"**Pass rate: {n_pass}/{n_roofable}** ({percent:.0f}%) of fixtures "
        "expected to produce a roof produced a valid terrain.",
        "",
        f"{len(expected)} fixture"
        f"{'' if len(expected) == 1 else 's'} recorded as unroofable "
        "(expected failure), counted separately from an invariant failure.",
        "",
        "| Fixture | Outcome | Detail |",
        "| --- | --- | --- |",
    ]
    for item in results:
        detail = item.property or item.detail or "—"
        if item.outcome == "pass" and item.topology_hash is not None:
            detail = f"topology hash `{item.topology_hash}`"
        lines.append(f"| `{item.name}` | {_outcome_label(item.outcome)} | {detail} |")
    lines.append("")
    if failed:
        lines.append("## Failures")
        lines.append("")
        for item in failed:
            lines.append(
                f"- `{item.name}` failed on **{item.property}**: {item.detail}"
            )
        lines.append("")
    if expected:
        lines.append("## Expected unroofable")
        lines.append("")
        for item in expected:
            lines.append(f"- `{item.name}`: `{item.property}` — {item.detail}")
        lines.append("")
    return "\n".join(lines)


def _outcome_label(outcome: Outcome) -> str:
    labels: dict[Outcome, str] = {
        "pass": "pass",
        "invariant_failure": "invariant failure",
        "expected_failure": "expected failure",
        "unexpected_failure": "unexpected failure",
        "hash_mismatch": "topology hash mismatch",
    }
    return labels[outcome]


def _as_ring(raw: object) -> list[tuple[float, float]]:
    if not isinstance(raw, list):
        raise TypeError(f"ring must be a list of [x, y] pairs, got {raw!r}")
    ring: list[tuple[float, float]] = []
    for point in raw:
        if not isinstance(point, list) or len(point) != 2:
            raise TypeError(f"point must be [x, y], got {point!r}")
        ring.append((float(point[0]), float(point[1])))
    return ring


def _as_pitch(raw: object) -> float | list[float]:
    if isinstance(raw, list):
        return [float(item) for item in raw]
    if isinstance(raw, int | float):
        return float(raw)
    raise TypeError(f"pitch must be a number or a list of numbers, got {raw!r}")
