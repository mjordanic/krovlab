"""Curated demo examples. Not the test-corpus folder listing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from krovlab import Cell, Dormer, Pitch

DEFAULT_EXAMPLE = "hip-rectangle"

RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
COURTYARD_HOLE = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]
L_SHAPE = [
    (0.0, 0.0),
    (10.0, 0.0),
    (10.0, 6.0),
    (3.0, 6.0),
    (3.0, 10.0),
    (0.0, 10.0),
]
BOWTIE = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
HOUSE = [(0.0, 0.0), (5.0, 0.0), (5.0, 6.0), (0.0, 6.0)]
GARAGE = [(8.0, 0.0), (13.0, 0.0), (13.0, 6.0), (8.0, 6.0)]
NEIGHBOUR = [(5.0, 0.0), (10.0, 0.0), (10.0, 6.0), (5.0, 6.0)]
GABLES: list[Pitch] = [45.0, 90.0, 45.0, 90.0]
DORMER_RING = [(4.0, 0.5), (6.0, 0.5), (6.0, 2.0), (4.0, 2.0)]
GABLE_DORMER: list[Pitch] = [45.0, 90.0, 45.0, 90.0]
SHED_PITCHES: list[Pitch] = [45.0, 90.0, 90.0, 90.0]
MIXED_PITCHES: list[Pitch] = [60.0, 45.0, 60.0, 45.0]
GAMBREL_BREAK = math.sqrt(3.0)


@dataclass(frozen=True)
class Example:
    """One complete, runnable demo: cells, optional dormers, and copy."""

    slug: str
    label: str
    group: str
    caption: str
    cells: tuple[Cell, ...]
    dormers: tuple[Dormer, ...] = field(default_factory=tuple)


def load_examples() -> dict[str, Example]:
    """Demo catalog in menu order, keyed by slug."""
    items = (
        Example(
            slug="hip-rectangle",
            label="Hip rectangle 10x6",
            group="Walls",
            caption=(
                "A 10x6 m building, every wall a hip, pitch 45°. "
                "The default roof."
            ),
            cells=(Cell(RECTANGLE, 45.0),),
        ),
        Example(
            slug="gable-ends",
            label="Gable ends",
            group="Walls",
            caption=(
                "Same rectangle; the short walls are gables "
                "(vertical, no roof face)."
            ),
            cells=(Cell(RECTANGLE, GABLES),),
        ),
        Example(
            slug="shed",
            label="Shed",
            group="Walls",
            caption="Three gables leave a single sloping face.",
            cells=(Cell(RECTANGLE, SHED_PITCHES),),
        ),
        Example(
            slug="mixed-pitches",
            label="Mixed pitches",
            group="Walls",
            caption="Steeper on two walls, shallower on the others; the ridge moves.",
            cells=(Cell(SQUARE, MIXED_PITCHES),),
        ),
        Example(
            slug="knee",
            label="Knee (gablet)",
            group="Walls",
            caption=(
                "The east wall rises 3 m, then the roof starts. Not a gable."
            ),
            cells=(Cell(RECTANGLE, 45.0, knee_height=[0.0, 3.0, 0.0, 0.0]),),
        ),
        Example(
            slug="gambrel",
            label="Gambrel (barn)",
            group="Walls",
            caption="Long walls break: 60° then 30°.",
            cells=(
                Cell(
                    RECTANGLE,
                    45.0,
                    gambrel=[
                        (60.0, 30.0, GAMBREL_BREAK),
                        None,
                        (60.0, 30.0, GAMBREL_BREAK),
                        None,
                    ],
                ),
            ),
        ),
        Example(
            slug="l-shape",
            label="L-shape",
            group="Plan",
            caption="One cell, a valley from the inside corner.",
            cells=(Cell(L_SHAPE, 45.0),),
        ),
        Example(
            slug="courtyard",
            label="Courtyard",
            group="Plan",
            caption="A hole in one cell — inner eaves, not a second roof.",
            cells=(Cell(SQUARE, 45.0, holes=[COURTYARD_HOLE]),),
        ),
        Example(
            slug="eaves-overhang",
            label="Eaves overhang",
            group="Plan",
            caption="The roof projects 0.5 m past the walls.",
            cells=(Cell(RECTANGLE, 45.0, overhang=0.5),),
        ),
        Example(
            slug="house-and-garage",
            label="House and garage",
            group="Several cells",
            caption="Two detached cells at different plate heights.",
            cells=(
                Cell(HOUSE, 45.0, eave_height=5.0),
                Cell(GARAGE, 45.0, eave_height=7.0),
            ),
        ),
        Example(
            slug="party-wall-gables",
            label="Two gables sharing a wall",
            group="Several cells",
            caption="Party wall, plates 5 m and 7 m.",
            cells=(
                Cell(HOUSE, GABLES, eave_height=5.0),
                Cell(NEIGHBOUR, GABLES, eave_height=7.0),
            ),
        ),
        Example(
            slug="dormer",
            label="Dormer on a hip",
            group="On the slope",
            caption=(
                "A small gable dormer on the south slope. "
                "Not a terrain; 3D still draws."
            ),
            cells=(Cell(RECTANGLE, 45.0),),
            dormers=(Dormer(0, DORMER_RING, GABLE_DORMER),),
        ),
        Example(
            slug="self-intersecting",
            label="Self-intersecting",
            group="Refused",
            caption=(
                "This plan crosses itself. The library returns a named "
                "Failure, not a roof."
            ),
            cells=(Cell(BOWTIE, 45.0),),
        ),
    )
    return {item.slug: item for item in items}


WALL_HINTS = {
    "hip": "Sloping face from this wall. Hips meet at the corners.",
    "gable": (
        "No roof face here. The wall is vertical; neighbours meet it at verges."
    ),
    "knee": (
        "Wall rises vertically by this height, then the roof starts "
        "(a gablet, not a gable)."
    ),
    "gambrel": (
        "Two pitches on this wall: steep below, shallower above, "
        "split at the break."
    ),
}
