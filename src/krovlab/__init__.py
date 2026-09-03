"""Roof geometry from a building footprint.

The public seam is :func:`roof`. Pass a list of ``(x, y)`` metres and a
pitch (degrees, rise:run, or a percentage); get back a :class:`Roof` you
can read quantities off, or a :class:`Failure` with a ``kind`` you can
branch on. Every roof carries a :class:`Validity` result: the terrain
invariants have been checked. Units are metres and degrees throughout.
"""

from krovlab.roof import (
    Arc,
    Face,
    Failure,
    FailureKind,
    Node,
    Pitch,
    Roof,
    Validity,
    roof,
)

__all__ = [
    "Arc",
    "Face",
    "Failure",
    "FailureKind",
    "Node",
    "Pitch",
    "Roof",
    "Validity",
    "roof",
]
