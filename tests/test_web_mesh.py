"""HTTP round-trip for roof mesh download.

The seam is GET of the form page and POST of the snapshot fields that
produced the shown solid, through Flask's test client. Assert what a
visitor gets: download controls, instruction copy, and the bytes of
roof.obj / roof.glb. Not CSS or template names.
"""

from __future__ import annotations

import struct
from html.parser import HTMLParser

from flask.testing import FlaskClient
from pygltflib import GLTF2  # type: ignore[import-untyped]
from web.app import create_app
from web.examples import DORMER_RING, GABLE_DORMER, GARAGE, HOUSE, L_SHAPE, RECTANGLE

from krovlab import Cell, Dormer, Project, Roof, project, roof
from krovlab.experimental import roof_from_face_graph
from krovlab.viz import solid_view

_Point = tuple[float, float, float]
_Triangle = tuple[_Point, _Point, _Point]

PLUS = [
    (2.0, 0.0),
    (4.0, 0.0),
    (4.0, 2.0),
    (6.0, 2.0),
    (6.0, 4.0),
    (4.0, 4.0),
    (4.0, 6.0),
    (2.0, 6.0),
    (2.0, 4.0),
    (0.0, 4.0),
    (0.0, 2.0),
    (2.0, 2.0),
]


def _client() -> FlaskClient:
    return create_app().test_client()


def _rect_post(**overrides: str) -> dict[str, str]:
    data: dict[str, str] = {
        "example": "hip-rectangle",
        "set_pitch": "45",
        "outer-x-0": "0",
        "outer-y-0": "0",
        "outer-x-1": "10",
        "outer-y-1": "0",
        "outer-x-2": "10",
        "outer-y-2": "6",
        "outer-x-3": "0",
        "outer-y-3": "6",
        "type-0": "hip",
        "pitch-0": "45",
        "type-1": "hip",
        "pitch-1": "45",
        "type-2": "hip",
        "pitch-2": "45",
        "type-3": "hip",
        "pitch-3": "45",
    }
    data.update(overrides)
    return data


def _ring_fields(
    ring: list[tuple[float, float]],
    *,
    prefix: str = "",
    pitch: str = "45",
    kind: str = "hip",
) -> dict[str, str]:
    data: dict[str, str] = {}
    for i, (x, y) in enumerate(ring):
        data[f"{prefix}outer-x-{i}"] = str(x)
        data[f"{prefix}outer-y-{i}"] = str(y)
        data[f"{prefix}type-{i}"] = kind
        data[f"{prefix}pitch-{i}"] = pitch
    return data


def _obj_vertices(body: str) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for line in body.splitlines():
        if not line.startswith("v "):
            continue
        parts = line.split()
        points.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return points


def _has_point(
    points: list[tuple[float, float, float]],
    expected: tuple[float, float, float],
) -> bool:
    return any(
        abs(x - expected[0]) < 1e-6
        and abs(y - expected[1]) < 1e-6
        and abs(z - expected[2]) < 1e-6
        for x, y, z in points
    )


def test_default_page_offers_obj_and_glb_downloads() -> None:
    page = _client().get("/").get_data(as_text=True)
    assert "<h2>3D solid</h2>" in page
    assert 'formaction="/roof.obj"' in page
    assert 'formaction="/roof.glb"' in page


def test_failure_page_offers_neither_download() -> None:
    page = _client().get("/?example=self-intersecting").get_data(as_text=True)
    assert "<h2>3D solid</h2>" not in page
    assert 'formaction="/roof.obj"' not in page
    assert 'formaction="/roof.glb"' not in page


def test_non_terrain_page_offers_neither_download() -> None:
    data: dict[str, str] = {"example": "hip-rectangle", "set_pitch": "45"}
    for i, (x, y) in enumerate(PLUS):
        data[f"outer-x-{i}"] = str(x)
        data[f"outer-y-{i}"] = str(y)
        data[f"type-{i}"] = "hip"
        data[f"pitch-{i}"] = "45"
    page = _client().post("/", data=data).get_data(as_text=True)
    assert "<h2>3D solid</h2>" not in page
    assert 'formaction="/roof.obj"' not in page
    assert 'formaction="/roof.glb"' not in page


def test_header_instructions_mention_the_downloads() -> None:
    page = _client().get("/").get_data(as_text=True)
    header = page.split("<form", 1)[0]
    assert "download" in header.lower()
    assert "roof.obj" in header
    assert "roof.glb" in header


def test_dormer_example_offers_both_downloads() -> None:
    page = _client().get("/?example=dormer").get_data(as_text=True)
    assert "<h2>3D solid</h2>" in page
    assert 'formaction="/roof.obj"' in page
    assert 'formaction="/roof.glb"' in page


def test_obj_download_is_the_shown_rectangle() -> None:
    response = _client().post("/roof.obj", data=_rect_post())
    assert response.status_code == 200
    disposition = response.headers.get("Content-Disposition", "")
    assert "roof.obj" in disposition
    body = response.get_data(as_text=True)
    assert "mtllib" not in body
    points = _obj_vertices(body)
    assert _has_point(points, (3.0, 3.0, 3.0))
    assert _has_point(points, (7.0, 3.0, 3.0))
    assert _has_point(points, (0.0, 0.0, 0.0))
    assert _has_point(points, (10.0, 0.0, 0.0))
    assert _has_point(points, (10.0, 6.0, 0.0))
    assert _has_point(points, (0.0, 6.0, 0.0))


def test_glb_download_is_y_up_grey_and_double_sided() -> None:
    response = _client().post("/roof.glb", data=_rect_post())
    assert response.status_code == 200
    disposition = response.headers.get("Content-Disposition", "")
    assert "roof.glb" in disposition
    data = response.get_data()
    assert data[:4] == b"glTF"
    gltf = GLTF2.load_from_bytes(data)
    assert gltf is not None
    assert len(gltf.meshes) == 1
    assert len(gltf.meshes[0].primitives) == 1
    assert len(gltf.materials) == 1
    material = gltf.materials[0]
    assert material.doubleSided is True
    colour = material.pbrMetallicRoughness.baseColorFactor
    assert colour is not None
    assert abs(colour[0] - colour[1]) < 0.05
    assert abs(colour[1] - colour[2]) < 0.05
    points = _glb_positions(gltf)
    assert _has_point(points, (7.0, 3.0, -3.0))
    assert _has_point(points, (3.0, 3.0, -3.0))


def test_download_posts_the_snapshot_of_the_shown_solid() -> None:
    page = _client().get("/").get_data(as_text=True)
    snapshot = _mesh_snapshot(page)
    assert snapshot["outer-y-2"] in {"6", "6.0"}
    response = _client().post("/roof.obj", data=snapshot)
    assert response.status_code == 200
    points = _obj_vertices(response.get_data(as_text=True))
    assert _has_point(points, (3.0, 3.0, 3.0))
    assert _has_point(points, (7.0, 3.0, 3.0))
    assert _has_point(points, (0.0, 6.0, 0.0))


def test_failure_and_non_terrain_downloads_are_not_files() -> None:
    bowtie = {
        "example": "self-intersecting",
        "set_pitch": "45",
        **_ring_fields([(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]),
    }
    plus: dict[str, str] = {"example": "hip-rectangle", "set_pitch": "45"}
    plus.update(_ring_fields(PLUS))
    for path in ("/roof.obj", "/roof.glb"):
        assert _client().post(path, data=bowtie).status_code == 404
        assert _client().post(path, data=plus).status_code == 404


ONE_FACE = ((0,), (1,), (2, 3), (4,), (5,))


def test_experimental_download_is_the_shown_solid() -> None:
    built = roof_from_face_graph(L_SHAPE, ONE_FACE)
    skeleton = roof(L_SHAPE, 45.0)
    assert isinstance(built, Roof)
    assert isinstance(skeleton, Roof)
    page = _client().get("/?method=experimental&example=l-one-face").get_data(
        as_text=True
    )
    snapshot = _mesh_snapshot(page)
    response = _client().post("/roof.obj", data=snapshot)
    assert response.status_code == 200
    downloaded = _triangle_set(_obj_triangles(response.get_data(as_text=True)))
    assert downloaded == _solid_triangles(built)
    assert downloaded != _solid_triangles(skeleton)


def test_experimental_download_keeps_the_posted_roof_height() -> None:
    built = roof_from_face_graph(RECTANGLE, roof_height=2.0)
    skeleton = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)
    assert isinstance(skeleton, Roof)
    data = {**_rect_post(), "method": "experimental", "roof_height": "2"}
    page = _client().post("/", data=data).get_data(as_text=True)
    snapshot = _mesh_snapshot(page)
    response = _client().post("/roof.obj", data=snapshot)
    assert response.status_code == 200
    downloaded = _triangle_set(_obj_triangles(response.get_data(as_text=True)))
    assert downloaded == _solid_triangles(built)
    assert downloaded != _solid_triangles(skeleton)


def test_dormer_mesh_is_the_shown_solid_triangles() -> None:
    built = project([Cell(RECTANGLE, 45.0)], [Dormer(0, DORMER_RING, GABLE_DORMER)])
    assert isinstance(built, Project)
    page = _client().get("/?example=dormer").get_data(as_text=True)
    snapshot = _mesh_snapshot(page)
    response = _client().post("/roof.obj", data=snapshot)
    assert response.status_code == 200
    obj_tris = _triangle_set(_obj_triangles(response.get_data(as_text=True)))
    from krovlab.viz import solid_view

    mesh = next(trace for trace in solid_view(built).data if trace.type == "mesh3d")
    xs = [float(x) for x in mesh.x]
    ys = [float(y) for y in mesh.y]
    zs = [float(z) for z in mesh.z]
    drawn = [
        (
            (xs[i], ys[i], zs[i]),
            (xs[j], ys[j], zs[j]),
            (xs[k], ys[k], zs[k]),
        )
        for i, j, k in zip(mesh.i, mesh.j, mesh.k, strict=True)
    ]
    assert obj_tris == _triangle_set(drawn)


def test_multi_cell_download_is_one_roof_mesh() -> None:
    built = project(
        [
            Cell(HOUSE, 45.0, eave_height=5.0),
            Cell(GARAGE, 45.0, eave_height=7.0),
        ]
    )
    assert isinstance(built, Project)
    page = _client().get("/?example=house-and-garage").get_data(as_text=True)
    snapshot = _mesh_snapshot(page)
    response = _client().post("/roof.obj", data=snapshot)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert not any(line.startswith("l ") for line in body.splitlines())
    points = _obj_vertices(body)
    assert _has_point(points, (0.0, 0.0, 5.0))
    assert _has_point(points, (8.0, 0.0, 7.0))
    assert sum(1 for line in body.splitlines() if line.startswith("o ")) <= 1


def test_overhang_is_baked_in_and_walls_are_absent() -> None:
    data = _rect_post(use_overhang="on", overhang="0.5")
    response = _client().post("/roof.obj", data=data)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert not any(line.startswith("l ") for line in body.splitlines())
    points = _obj_vertices(body)
    assert _has_point(points, (-0.5, -0.5, 0.0))
    assert not _has_point(points, (0.0, 0.0, 0.0))


class _MeshFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = dict(attrs)
        if tag == "form" and mapping.get("id") == "mesh-download":
            self._in_form = True
            return
        if tag == "form":
            self._in_form = False
            return
        if self._in_form and tag == "input":
            name = mapping.get("name")
            if name:
                self.fields[name] = mapping.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_form = False


def _mesh_snapshot(page: str) -> dict[str, str]:
    parser = _MeshFormParser()
    parser.feed(page)
    assert parser.fields
    return parser.fields


def _obj_triangles(body: str) -> list[_Triangle]:
    verts = _obj_vertices(body)
    triangles: list[_Triangle] = []
    for line in body.splitlines():
        if not line.startswith("f "):
            continue
        idxs = [int(part.split("/")[0]) - 1 for part in line.split()[1:]]
        triangles.append((verts[idxs[0]], verts[idxs[1]], verts[idxs[2]]))
    return triangles


def _solid_triangles(solid: Roof | Project) -> set[frozenset[_Point]]:
    mesh = next(trace for trace in solid_view(solid).data if trace.type == "mesh3d")
    xs = [float(x) for x in mesh.x]
    ys = [float(y) for y in mesh.y]
    zs = [float(z) for z in mesh.z]
    drawn = [
        (
            (xs[i], ys[i], zs[i]),
            (xs[j], ys[j], zs[j]),
            (xs[k], ys[k], zs[k]),
        )
        for i, j, k in zip(mesh.i, mesh.j, mesh.k, strict=True)
    ]
    return _triangle_set(drawn)


def _triangle_set(triangles: list[_Triangle]) -> set[frozenset[_Point]]:
    out: set[frozenset[_Point]] = set()
    for tri in triangles:
        rounded = ((round(p[0], 6), round(p[1], 6), round(p[2], 6)) for p in tri)
        out.add(frozenset(rounded))
    return out


def _glb_positions(gltf: GLTF2) -> list[tuple[float, float, float]]:
    primitive = gltf.meshes[0].primitives[0]
    index = primitive.attributes.POSITION
    assert index is not None
    accessor = gltf.accessors[index]
    view = gltf.bufferViews[accessor.bufferView]
    blob = gltf.binary_blob()
    assert blob is not None
    offset = (view.byteOffset or 0) + (accessor.byteOffset or 0)
    count = accessor.count
    points: list[tuple[float, float, float]] = []
    for i in range(count):
        start = offset + i * 12
        x, y, z = struct.unpack_from("<fff", blob, start)
        points.append((x, y, z))
    return points
