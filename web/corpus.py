"""Named footprints from the project's committed corpus.

The dropdown is these files, not a second hand-copied geometry list.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from krovlab import Pitch

CORPUS_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "footprints"
DEFAULT_PRESET = "rectangle-10x6"


@dataclass(frozen=True)
class Preset:
    """One corpus footprint, ready to pass to ``roof``."""

    name: str
    footprint: list[tuple[float, float]]
    pitch: Pitch | list[Pitch]
    holes: list[list[tuple[float, float]]] | None
    overhang: float


def load_presets() -> dict[str, Preset]:
    """Every ``*.toml`` in the corpus directory, keyed by stem."""
    presets: dict[str, Preset] = {}
    for path in sorted(CORPUS_DIR.glob("*.toml")):
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        holes_raw = data.get("holes")
        holes: list[list[tuple[float, float]]] | None
        if holes_raw is None:
            holes = None
        elif isinstance(holes_raw, list):
            holes = [_as_ring(ring) for ring in holes_raw]
        else:
            raise TypeError(f"holes must be a list of rings, got {holes_raw!r}")
        presets[path.stem] = Preset(
            name=path.stem,
            footprint=_as_ring(data["footprint"]),
            pitch=_as_pitch(data["pitch"]),
            holes=holes,
            overhang=float(data.get("overhang", 0.0)),
        )
    return presets


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
