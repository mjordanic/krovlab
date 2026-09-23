# 02: Download the solid on the page as OBJ and glTF

**What to build:** When the 3D solid is on the page, the visitor can download
it as `roof.obj` and as `roof.glb`. Both are one triangle mesh of the roof
faces, in metres — the same triangles the solid already draws, including a
project of several cells and a dormer project whose 3D is shown. Hips, ridges,
valleys, eaves, verges, and walls are not in the file. An overhang is already
in the mesh, because the solid is the roof of the enlarged footprint.

The download is that shown solid. Edits typed since **Update roof** are not in
the file. A Failure page and a non-terrain page offer neither download.

OBJ is page X, page Y, height, Z up, geometry only, no material sidecar. glTF
is Y up: position `(x, height, −y)`, one mesh, one flat grey double-sided
material. The page's short instructions gain a bullet for the downloads.

The default 10 × 6 m rectangle at 45° is the worked mesh: ridge endpoints
`(3, 3, 3)` and `(7, 3, 3)` in the OBJ, and `(7, 3, 3)` as `(7, 3, −3)` in the
glTF. This ticket does not read a DXF. The committed example file and the
upload-then-download round trip are ticket 03.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Stories:** 25 (download bullet), 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39

**Prior art:** ADR-0002. PRD "The mesh is the solid's triangles", "Download is
a snapshot of the shown solid", "Coordinates". Solid view of a Roof and of a
Project, including the dormer case where 3D is shown though the project is not
a terrain (`test_solid_view_builds_from_a_roof` and the web demo's dormer
example). Worked numbers: 10 × 6 m at 45°, ridge from `(3, 3, 3)` to
`(7, 3, 3)`. Web demo HTTP tests for the Failure page (bowtie) and a
non-terrain page (plus-shape).

- [ ] The default terrain page offers `roof.obj` and `roof.glb`; a Failure page and a non-terrain page offer neither
- [ ] The dormer example whose 3D is shown offers both, and the mesh is that solid's triangles
- [ ] OBJ contains the ridge endpoints `(3, 3, 3)` and `(7, 3, 3)` and the eave corners at height 0, and has no `mtllib`
- [ ] The glTF is one `.glb` mesh; the ridge point `(7, 3, 3)` is stored as `(7, 3, −3)`; the material is one flat grey and double-sided
- [ ] The download posts the inputs that produced the shown solid, so a coordinate edited after **Update roof** is not the ring in the file
- [ ] A multi-cell project downloads as one mesh of roof faces, with no arc linework and no wall solid
- [ ] The header instructions mention the two downloads
- [ ] The core package does not import the glTF writer
- [ ] Flask test client covers these cases; nothing asserts on CSS
