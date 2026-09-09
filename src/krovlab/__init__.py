"""Roof geometry from a building footprint.

The public seam is :func:`roof`. Pass a list of ``(x, y)`` metres and a
pitch (degrees, rise:run, or a percentage) — one value, or one per
footprint edge — and get back a :class:`Roof` you can read quantities
off, or a :class:`Failure` with a ``kind`` you can branch on. A
footprint may include holes. ``pitch = 90`` on an edge is a gable.
``overhang`` offsets the eaves outward in metres. ``eave_height`` is
metres above datum, added to every node after the roof is assessed.
Every roof carries a :class:`Validity` result: the terrain invariants
have been checked. Units are metres and degrees throughout. Pass
``events=True`` to inspect the wavefront events that produced it.
"""

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
    "Event",
    "Face",
    "Failure",
    "FailureKind",
    "Node",
    "Pitch",
    "Roof",
    "Validity",
    "roof",
    "topology_hash",
]
