"""Roof geometry from a building footprint.

The public seam is :func:`roof`. Pass a list of ``(x, y)`` metres and a
pitch in degrees; get back a :class:`Roof` you can read quantities off, or
a :class:`Failure` if the pitch is out of range. Every roof carries a
:class:`Validity` result: the terrain invariants have been checked.
"""

from krovlab.roof import Arc, Face, Failure, Node, Roof, Validity, roof

__all__ = ["Arc", "Face", "Failure", "Node", "Roof", "Validity", "roof"]
