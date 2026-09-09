"""Roof geometry from a building footprint.

The public seams are :func:`roof` and :func:`project`. ``roof`` takes one
footprint and a pitch — degrees, rise:run, or a percentage, one value or
one per edge — and returns a :class:`Roof` or a :class:`Failure`.
``project`` takes a list of :class:`Cell` values and returns a
:class:`Project` or a Failure. A footprint may include holes.
``pitch = 90`` on an edge is a gable. ``overhang`` offsets the eaves
outward in metres. ``eave_height`` is metres above datum, added to every
node after the roof is assessed. ``knee_height`` is metres of vertical
wall on an edge before that edge's pitch begins. ``wrap`` marks
consecutive edges as one plane. Every roof carries a
:class:`Validity` result. Units are metres and degrees throughout. Pass
``events=True`` on ``roof`` to inspect the wavefront events that produced it.
"""

from krovlab.project import Cell, Project, ProjectFace, project
from krovlab.roof import (
    Arc,
    Event,
    Face,
    Failure,
    FailureKind,
    Node,
    Pitch,
    Roof,
    Validity,
    roof,
    topology_hash,
)

__all__ = [
    "Arc",
    "Cell",
    "Event",
    "Face",
    "Failure",
    "FailureKind",
    "Node",
    "Pitch",
    "Project",
    "ProjectFace",
    "Roof",
    "Validity",
    "project",
    "roof",
    "topology_hash",
]
