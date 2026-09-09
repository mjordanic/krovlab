"""Named footprints from the project's committed corpus.

The dropdown is these files, not a second hand-copied geometry list.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from krovlab import Cell, Pitch

CORPUS_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "footprints"
DEFAULT_PRESET = "rectangle-10x6"


@dataclass(frozen=True)
class Preset:
    """One corpus footprint, ready to pass to ``roof`` or ``project``."""

    name: str
    footprint: list[tuple[float, float]]
    pitch: Pitch | list[Pitch]
    holes: list[list[tuple[float, float]]] | None
    overhang: float
    eave_height: float = 0.0
    extra_cells: tuple[Cell, ...] = ()


def load_presets() -> dict[str, Preset]:
    """Every ``*.toml`` in the corpus directory, keyed by stem."""
    presets: dict[str, Preset] = {}
    for path in sorted(CORPUS_DIR.glob("*.toml")):
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        presets[path.stem] = _preset_from_data(path.stem, data)
    return presets


def _preset_from_data(name: str, data: dict[str, Any]) -> Preset:
    cells_raw = data.get("cells")
    if isinstance(cells_raw, list) and cells_raw:
        parsed = [_cell_from_raw(item) for item in cells_raw]
        first, rest = parsed[0], parsed[1:]
        return Preset(
            name=name,
            footprint=first.footprint,
            pitch=first.pitch,
            holes=first.holes,
            overhang=first.overhang,
            eave_height=first.eave_height,
            extra_cells=tuple(rest),
        )
    holes_raw = data.get("holes")
    holes: list[list[tuple[float, float]]] | None
    if holes_raw is None:
        holes = None
    elif isinstance(holes_raw, list):
        holes = [_as_ring(ring) for ring in holes_raw]
    else:
        raise TypeError(f"holes must be a list of rings, got {holes_raw!r}")
    return Preset(
        name=name,
        footprint=_as_ring(data["footprint"]),
        pitch=_as_pitch(data["pitch"]),
        holes=holes,
        overhang=float(data.get("overhang", 0.0)),
        eave_height=float(data.get("eave_height", 0.0)),
    )


def _cell_from_raw(raw: object) -> Cell:
    if not isinstance(raw, dict):
        raise TypeError(f"cell must be a table, got {raw!r}")
    data = cast(dict[str, Any], raw)
    holes_raw = data.get("holes")
    holes: list[list[tuple[float, float]]] | None
    if holes_raw is None:
        holes = None
    elif isinstance(holes_raw, list):
        holes = [_as_ring(ring) for ring in holes_raw]
    else:
        raise TypeError(f"holes must be a list of rings, got {holes_raw!r}")
    return Cell(
        _as_ring(data["footprint"]),
        _as_pitch(data["pitch"]),
        holes=holes,
        overhang=float(data.get("overhang", 0.0)),
        eave_height=float(data.get("eave_height", 0.0)),
    )


def _as_ring(raw: object) -> list[tuple[float, float]]:
    if not isinstance(raw, list):
        raise TypeError(f"ring must be a list of [x, y] pairs, got {raw!r}")
    ring: list[tuple[float, float]] = []
    for point in raw:
        if not isinstance(point, list) or len(point) != 2:
            raise TypeError(f"point must be [x, y], got {point!r}")
        ring.append((float(point[0]), float(point[1])))
    return ring


def _as_pitch(raw: object) -> Pitch | list[Pitch]:
    if isinstance(raw, list):
        values: list[Pitch] = [float(item) for item in raw]
        return values
    if isinstance(raw, int | float):
        return float(raw)
    raise TypeError(f"pitch must be a number or a list of numbers, got {raw!r}")
