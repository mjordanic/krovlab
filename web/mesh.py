"""Encode the shown roof solid as OBJ or glTF at the web boundary.

Triangles come from the same ear-clip the 3D solid already uses.
The core package does not import this module.
"""

from __future__ import annotations

import struct

from krovlab.project import Project
from krovlab.roof import Roof
from krovlab.viz import _triangulate

try:
    from pygltflib import (  # type: ignore[import-untyped]
        ARRAY_BUFFER,
        ELEMENT_ARRAY_BUFFER,
        FLOAT,
        GLTF2,
        SCALAR,
        UNSIGNED_INT,
        VEC3,
        Accessor,
        Attributes,
        Buffer,
        BufferView,
        Material,
        Mesh,
        Node,
        PbrMetallicRoughness,
        Primitive,
        Scene,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "the web extra requires pygltflib. Install with: uv sync --extra web"
    ) from exc

# Same grey as the page's Mesh3d (#d1d5db), double-sided so winding is free.
_GREY = [209 / 255, 213 / 255, 219 / 255, 1.0]


def obj_bytes(solid: Roof | Project) -> bytes:
    """Wavefront OBJ: page X, page Y, height; Z up; geometry only."""
    xs, ys, zs, faces = _mesh(solid)
    lines: list[str] = []
    for x, y, z in zip(xs, ys, zs, strict=True):
        lines.append(f"v {x:g} {y:g} {z:g}")
    for i, j, k in faces:
        lines.append(f"f {i + 1} {j + 1} {k + 1}")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def glb_bytes(solid: Roof | Project) -> bytes:
    """Binary glTF: (x, height, -y), one mesh, one flat grey double-sided material."""
    xs, ys, zs, faces = _mesh(solid)
    n = len(xs)
    positions = bytearray()
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for x, y, z in zip(xs, ys, zs, strict=True):
        px, py, pz = float(x), float(z), float(-y)
        positions.extend(struct.pack("<fff", px, py, pz))
        mins[0] = min(mins[0], px)
        mins[1] = min(mins[1], py)
        mins[2] = min(mins[2], pz)
        maxs[0] = max(maxs[0], px)
        maxs[1] = max(maxs[1], py)
        maxs[2] = max(maxs[2], pz)
    indices = bytearray()
    for i, j, k in faces:
        indices.extend(struct.pack("<III", i, j, k))
    blob = bytes(positions) + bytes(indices)
    gltf = GLTF2(
        scene=0,
        scenes=[Scene(nodes=[0])],
        nodes=[Node(mesh=0)],
        meshes=[
            Mesh(
                primitives=[
                    Primitive(
                        attributes=Attributes(POSITION=0),
                        indices=1,
                        material=0,
                    )
                ]
            )
        ],
        materials=[
            Material(
                doubleSided=True,
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorFactor=_GREY,
                    metallicFactor=0.0,
                    roughnessFactor=1.0,
                ),
            )
        ],
        accessors=[
            Accessor(
                bufferView=0,
                componentType=FLOAT,
                count=n,
                type=VEC3,
                min=mins,
                max=maxs,
            ),
            Accessor(
                bufferView=1,
                componentType=UNSIGNED_INT,
                count=len(faces) * 3,
                type=SCALAR,
            ),
        ],
        bufferViews=[
            BufferView(
                buffer=0,
                byteOffset=0,
                byteLength=len(positions),
                target=ARRAY_BUFFER,
            ),
            BufferView(
                buffer=0,
                byteOffset=len(positions),
                byteLength=len(indices),
                target=ELEMENT_ARRAY_BUFFER,
            ),
        ],
        buffers=[Buffer(byteLength=len(blob))],
    )
    gltf.set_binary_blob(blob)
    return b"".join(gltf.save_to_bytes())


def _mesh(
    solid: Roof | Project,
) -> tuple[list[float], list[float], list[float], list[tuple[int, int, int]]]:
    xs = [node.x for node in solid.nodes]
    ys = [node.y for node in solid.nodes]
    zs = [node.height for node in solid.nodes]
    faces: list[tuple[int, int, int]] = []
    for face in solid.faces:
        faces.extend(_triangulate(face.node_indices, xs, ys))
    return xs, ys, zs, faces
