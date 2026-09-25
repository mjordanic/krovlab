# 01: Upload a DXF footprint onto the selected cell

**What to build:** On the form page, the visitor chooses a DXF and millimetres,
centimetres, or metres (millimetres is the default). A closed straight
polyline in model space becomes one cell's footprint, in metres. A closed
polyline strictly inside it becomes a hole. That cell's edges come in as hips
at the set-pitch already on the form. Overhang, eave height, dormers, and
every other cell stay as they were.

The plan and the 3D solid stay the roof from before the file. **Update roof**
is marked as needing a click, the same way the help box marks it after writing
the form. The next **Update roof** is the ordinary rebuild.

The file fills the cell selected on the plan, or the first cell when none is
selected. The header unit is ignored. Z is discarded. Either winding is
accepted. A polyline that repeats its first vertex counts as closed. Collinear
vertices stay. Arcs, text, dimensions, hatches, paper space, and block inserts
are ignored. A polyline with a bulge is skipped.

A bad file leaves the form as submitted and shows a short message beside the
file control: nothing straight and closed left; block inserts and no
model-space polyline (say to explode it); two outermost rings; the library's
footprint or hole check refuses the rings; the body is not a DXF; the body is
over 2 MB. Do not add a Failure kind for a bad file.

The page's short instructions gain a bullet for the DXF, beside the bullets
that already explain drawing and **Update roof**. The core package still does
no I/O and does not import the DXF reader. Tests build tiny DXFs in memory.
The committed example file is ticket 03.

**Blocked by:** None (can start immediately)

**Status:** done

**Stories:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25 (DXF bullet), 46, 47, 48

**Prior art:** ADR-0002 (core does no I/O; the web extra wraps the form).
PRD "Upload is a submit that does not rebuild the drawings", "Which cell",
"Units", "What is read", "Refusal leaves the form", "Size limit". Footprint
and hole checks on the roof entry point (`self_intersection`, `degenerate`,
`hole_intersects`). Web demo HTTP tests, including a two-cell post. Help box
marks **Update roof** after it writes the form. Worked rectangle: 10 × 6 m.

- [x] A millimetre polyline `(0,0) (10000,0) (10000,6000) (0,6000)` fills the first cell as `(0,0) (10,0) (10,6) (0,6)`, hips at the page's set-pitch
- [x] Centimetres `(0, 1000, 600)` and metres `(0, 10, 6)` yield that same ring; a unitless header does not change the chosen scale
- [x] The default unit is millimetres
- [x] A repeated first vertex counts as closed; either winding is kept; collinear vertices stay; Z is discarded
- [x] An inner closed polyline becomes a hole; several inner polylines become several holes
- [x] The selected cell is the one replaced; with none selected, the first cell; other cells' footprints, pitches, and wall types stay
- [x] Overhang, eave height, and posted dormers on that cell stay
- [x] The describe block, plan, and 3D solid are still the pre-upload roof, and **Update roof** is marked as needing a click
- [x] An arc beside a straight polyline is ignored; a bulged polyline is skipped
- [x] Two outermost rings, a self-intersecting ring, a non-DXF, a body over 2 MB, and an INSERT with no model-space polyline each leave the fields unchanged and show a message; the INSERT message says to explode it
- [x] The header instructions mention the DXF upload
- [x] `import krovlab` still pulls in no third-party dependencies, and the core does not import the DXF reader
- [x] Flask test client covers these cases with DXFs built in the test; nothing asserts on CSS or DXF group codes
