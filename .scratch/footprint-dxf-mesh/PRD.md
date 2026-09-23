# PRD: Footprint DXF and roof mesh

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — "footprint", "hole", "cell", "pitch", "roof", "face",
"overhang", "eave height", "terrain", "project", "dormer", "Failure" — and not
loosely. Do not call the footprint an outline. Respects ADR-0001 (own weighted
straight skeleton, in Python) and ADR-0002 (Python form server wraps the core;
the core does no I/O).

## Problem Statement

The page already roofs a footprint drawn or typed on the form, and it already
shows a 3D solid when that roof is a terrain (and in the documented dormer
case). An architect who has the plan as a DXF still has to retype every vertex.
The solid on the page cannot be taken back to Rhino, Blender, or Archicad.

This is a demo. It does not have to accept every drawing an architect produces.
A file that is one closed straight polyline — the footprint — is enough.

## Solution

On the existing form page, the visitor uploads a DXF and chooses millimetres,
centimetres, or metres (millimetres is the default). The file supplies the
footprint of one cell, in plan. Pitch, hip, gable, knee, gambrel, overhang,
and eave height stay on the form.

Sending the file fills that cell's footprint and resets that cell's edges to
hips at the form's set-pitch. The drawings stay as they were. **Update roof**
rebuilds the plan and the 3D solid, as it does after drawing.

When the 3D solid is on the page, the visitor can download that solid as OBJ
and as glTF (`.glb`). Both are one triangle mesh of the roof faces, in metres.
The download is the solid already shown, including a project of several cells
and a dormer project whose 3D is shown. Edits that have not been updated are
not in the file.

The same worked rectangle used everywhere else (10 × 6 m at 45°) is committed
as a millimetre DXF and written up in the README and in
`notebooks/getting-started.ipynb`, in the same places and the same voice as
the other capabilities.

## User Stories

**Uploading a footprint**

1. As a visitor, I want to choose a DXF on the form page, so that I can bring
   a footprint in without retyping vertices.
2. As a visitor, I want a unit choice of millimetres, centimetres, or metres
   beside that file, defaulting to millimetres, so that a CAD plan becomes
   metres in the editor.
3. As a visitor, I want the DXF header ignored, so that a missing or wrong
   unit header cannot silently scale the building.
4. As a visitor, I want a closed straight polyline in model space to become
   the footprint, so that the plan editor shows that ring in metres.
5. As a visitor, I want a polyline that repeats its first vertex to count as
   closed even when the DXF closed flag is off, so that a geometrically closed
   ring still loads.
6. As a visitor, I want either winding accepted, so that I do not have to
   reverse the polyline in CAD.
7. As a visitor, I want collinear vertices on a straight wall kept, so that
   the ring I drew is the ring on the form.
8. As a visitor, I want only X and Y read, so that a polyline with an unused Z
   is still a plan footprint.
9. As a visitor, I want a closed straight polyline strictly inside the outer
   one to become a hole on that cell, so that a courtyard comes in with the
   footprint.
10. As a visitor, I want several such inner polylines to become several holes,
    so that more than one courtyard can come from one file.
11. As a visitor, I want two outermost closed polylines refused, with the form
    left as it was, so that a title-block border plus a building, or two
    wings, does not become one silent footprint.
12. As a visitor, I want arcs, text, dimensions, hatches, paper space, and
    block inserts ignored, so that a file which also contains a door swing
    still yields the straight footprint.
13. As a visitor, I want a closed polyline that has a bulge skipped, so that a
    curved wall is not treated as a straight ring.
14. As a visitor, I want a clear page message when no closed straight polyline
    remains, so that I know the file did not load.
15. As a visitor, I want that message to tell me to explode the outline when
    the file has block inserts and no model-space polyline, so that I know the
    one fix.
16. As a visitor, I want a self-intersecting ring, a degenerate ring, or a hole
    that touches or crosses another ring refused by the same checks the
    library already uses, form unchanged, so that a bad DXF does not replace a
    good footprint.
17. As a visitor, I want the upload to replace the cell selected on the plan,
    so that a multi-cell project keeps the other cells.
18. As a visitor, I want the first cell filled when none is selected, so that
    a fresh page still accepts a file.
19. As a visitor, I want the other cells' footprints, pitches, and wall types
    left alone, so that a second wing I already entered survives the upload.
20. As a visitor, I want every edge of the new ring, including hole edges, to
    come in as a hip at the set-pitch already on the form, so that the old
    per-edge pitches do not attach to a different polygon.
21. As a visitor, I want overhang and eave height on that cell to stay, so
    that I do not re-enter them after choosing a file.
22. As a visitor, I want dormers already on the form to stay, so that the
    upload does not invent or delete a dormer. The next **Update roof** may
    then report the existing dormer Failure if the new footprint no longer
    hosts them.
23. As a visitor, I want the plan and the 3D solid to stay as they were until
    I click **Update roof**, so that choosing a file works the way drawing
    does.
24. As a visitor, I want **Update roof** highlighted after a successful
    upload, so that I can see the drawings are stale.
25. As a visitor, I want the page's short instructions to mention the DXF and
    the mesh downloads, so that the demo explains itself the way it already
    explains drawing and **Update roof**.

**Downloading the roof**

26. As a visitor, I want to download an OBJ of the 3D solid, so that I can open
    the roof in a modeller that reads OBJ.
27. As a visitor, I want to download a glTF (`.glb`) of that same solid, so
    that I can open it in a viewer that reads glTF.
28. As a visitor, I want both downloads only when the 3D solid is shown, so
    that a Failure or a non-terrain roof does not offer a mesh.
29. As a visitor, I want a dormer project whose 3D is shown to offer the same
    downloads, so that the file matches the exception the page already draws.
30. As a visitor, I want the file to be the solid on the page, so that edits I
    have not updated are absent from the mesh.
31. As a visitor, I want one triangle mesh of the roof faces, in metres, so
    that the file is the covering surface and not a walled building.
32. As a visitor, I want hips, ridges, valleys, eaves, and verges left out of
    the file, so that the download stays a single mesh.
33. As a visitor, I want a project of several cells to download as one mesh,
    so that the file matches the one solid on the page.
34. As a visitor, I want an overhang already baked into that mesh, so that the
    file is the roof of the enlarged footprint, as the solid already shows.
35. As a visitor, I want the OBJ in the same X, Y, and height as the page, Z
    up, so that Rhino stands the roof the way the page does.
36. As a visitor, I want the glTF Y up, with plan X kept, height as Y, and
    plan Y as −Z, so that an ordinary viewer stands the roof the same way.
37. As a visitor, I want the glTF faces double-sided and a single flat grey,
    so that the mesh reads from above without a material sidecar.
38. As a visitor, I want the OBJ to be geometry only, so that a missing
    material file cannot make the import fail.
39. As a visitor, I want the files named `roof.obj` and `roof.glb`, so that
    the download has an obvious name.

**The worked example, in the docs**

40. As a reader of the README, I want the Web demo section to explain the DXF
    upload, the unit choice, what the file may contain, **Update roof**, and
    the two downloads, in the same voice as the rest of that section, so that
    I can try it without reading this PRD.
41. As a reader of the README, I want the Notebooks list to mention that
    walkthrough, so that the index matches the notebook.
42. As a reader of the getting-started notebook, I want a section in the same
    voice as the other web-demo callouts, so that the DXF and the mesh sit
    beside the rectangle, the gable, the knee, the gambrel, and the dormer.
43. As a reader, I want a committed millimetre DXF of the 10 × 6 m rectangle,
    so that I can upload the same footprint the rest of the docs already use.
44. As a reader, I want that file linked from the README and from the notebook
    section, so that I do not have to draw it.
45. As a reader, I want the notebook section to stay runnable with the
    notebooks extra alone, so that documenting the demo does not make the
    notebook import the web stack.

**Boundaries**

46. As a developer, I want the core package to stay free of file formats and
    of I/O, so that DXF and glTF remain a web-boundary adapter as ADR-0002
    requires.
47. As a developer, I want a DXF larger than a modest limit refused with a
    page message, form unchanged, so that a heavy sheet cannot hang the demo.
48. As a visitor, I want a file that is not a DXF refused with a page message,
    form unchanged, so that a wrong file does not wipe the footprint.

## Implementation Decisions

**The page already built is the product.** Upload and download are controls
on the form page. There is no second page, no JSON API, and no client-side
DXF parser.

**Upload is a submit that does not rebuild the drawings.** The POST carries
the current form plus the file and the unit choice. On success the response
is the same page: the selected cell's footprint and hole fields are the new
rings in metres, that cell's edges are hips at set-pitch, overhang and eave
height and any dormers are unchanged, other cells are unchanged, and the
describe block, plan, and 3D solid are still the result of the fields as they
were before the file was applied. **Update roof** is marked as needing a
click, the same way the help box already marks it after writing the form.
The next **Update roof** posts those new fields and is the ordinary rebuild.

**Which cell.** The plan's selected cell. When nothing is selected, the first
cell. The selection is submitted with the file.

**Units.** A control with three values: millimetres (default), centimetres,
metres. Divide by 1000, by 100, or by 1. Do not read `$INSUNITS`.

**What is read.** Model space only. Closed `LWPOLYLINE` and 2D/3D `POLYLINE`
entities with straight segments. A polyline whose first vertex repeats its
last is closed. Z is discarded. Paper space, `LINE`, `ARC`, `SPLINE`,
`ELLIPSE`, `TEXT`, `MTEXT`, dimensions, hatches, and `INSERT` are ignored. A
polyline with a non-zero bulge is skipped. The outermost remaining ring is
the footprint. Rings strictly inside it are holes. More than one outermost
ring is a refusal.

**Refusal leaves the form.** Any of: no closed straight polyline; inserts
present and no model-space polyline (say to explode it); two outermost rings;
the library's footprint or hole check returns a Failure (`self_intersection`,
`degenerate`, `hole_intersects`, and the other geometry kinds those checks
already return); the file is not a DXF; the file exceeds the size limit. The
response is the page as submitted, plus a short message a visitor can read
next to the file control. Do not add a Failure kind to the library for a bad
file.

**Size limit.** Refuse above 2 MB. A footprint polyline is far smaller. This
is a demo fuse, not a streaming parser.

**Libraries live on the web extra.** Read DXF with `ezdxf`. Write OBJ as
plain text in this app. Write `.glb` with `pygltflib`. The core package does
not import them. `uv sync --extra web` is how they install. The notebooks
extra does not gain them.

**The mesh is the solid's triangles.** Use the same triangulation the 3D
solid already uses, including a project and a dormer project. Do not scrape
a Plotly figure and do not write a second mesher. Encode those triangles at
the web boundary. Roof faces only: no arc linework, no wall solids.

**Download is a snapshot of the shown solid.** Rendered only when the page
shows the 3D solid. Each download posts the inputs that produced that solid,
not whatever the visitor has since typed into the editable fields. The
response is the file, `roof.obj` or `roof.glb`, not a new HTML page.

**Coordinates.** Metres. OBJ vertex lines are page X, page Y, height (Z up).
glTF positions are `(x, height, −y)`. One mesh primitive. glTF material is
one flat grey, double-sided, so winding does not have to be hunted. OBJ has
no `mtllib`.

**Worked file.** `notebooks/hip-rectangle-mm.dxf` is an ASCII DXF: one closed
straight polyline in model space, vertices `(0,0)`, `(10000,0)`,
`(10000,6000)`, `(0,6000)` in millimetres. Uploaded with millimetres selected,
it is the 10 × 6 m rectangle the rest of the docs use. At set-pitch 45° and
**Update roof**, it is the roof whose ridge runs from `(3, 3, 3)` to
`(7, 3, 3)`.

**Docs, same homes as the other capabilities.**

- `README.md` — the Web demo section gains the upload, the unit choice, what
  a file must contain, the ignored junk, the explode hint, **Update roof**,
  and the two downloads. The Notebooks list mentions the new walkthrough.
  Link `notebooks/hip-rectangle-mm.dxf`. Do not add a core function or an
  example under the Python Examples heading.
- `notebooks/getting-started.ipynb` — one new markdown section, in the same
  voice as the existing web-demo callouts, covering that file and the
  downloads. The opening list of topics includes it. No code cell imports
  the web stack or `ezdxf`. The section may point at the rectangle the
  notebook already roofs.
- This spec is `.scratch/footprint-dxf-mesh/PRD.md`.

None of these paths is gitignored.

**Page copy.** The header instructions gain one bullet for the DXF and one
for the downloads, beside the bullets that already explain drawing and
**Update roof**.

## Testing Decisions

**A good test asserts what the visitor gets back from the form, not how the
parser walks entities.** Status, the page message, which cell's coordinate
fields changed, that the describe block and the 3D branch are still the
pre-upload roof, and the bytes of `roof.obj` / `roof.glb`. Do not assert CSS,
template names, or DXF group codes.

**One seam: the HTTP round-trip.** Flask's test client against the app, the
same seam as the web demo tests. Tickets 01 and 02 build tiny DXFs in the
test with `ezdxf` rather than committing a fixture for each case. Ticket 02
downloads the roof already on the page; the default 10 × 6 m rectangle at 45°
is that roof. The committed `notebooks/hip-rectangle-mm.dxf` is created in
ticket 03 and asserted once there: upload it, **Update roof**, and both
downloads match that solid.

Prior art: the web demo HTTP tests (GET/POST of the form, worked numbers for
the 10 × 6 m rectangle at 45°, the dormer case where 3D is shown though the
project is not a terrain). Prior art for "the figure built" is the solid-view
smoke test. Do not re-assert terrain invariants.

**Required cases**

- Upload an in-memory millimetre polyline `(0,0) (10000,0) (10000,6000)
  (0,6000)` onto the default page: 200, the first cell's footprint fields are
  `(0,0)`, `(10,0)`, `(10,6)`, `(0,6)`, four hips at the page's set-pitch, the
  3D solid is still the roof that was already shown, and **Update roof** is
  marked as needing a click. Ticket 03 repeats this with the committed file,
  then **Update roof**, and checks both downloads.
- The same polyline in centimetres (0, 1000, 600) and in metres (0, 10, 6)
  yields that same 10 × 6 m ring. A unitless header does not change the
  dropdown's scale.
- A second closed polyline strictly inside becomes a hole. Two outermost
  polylines: message, fields unchanged.
- An arc beside a straight closed polyline is ignored. A polyline with a
  bulge is skipped. A file whose only geometry is an `INSERT`: the explode
  message, fields unchanged. Not-a-DXF and a body over 2 MB: message, fields
  unchanged.
- A self-intersecting closed polyline: the library's refusal, fields
  unchanged.
- Two cells on the form, the second selected: the file replaces the second
  cell's footprint and edge list; the first cell's fields stay.
- After **Update roof** on the millimetre rectangle at 45°: the solid is
  shown, both downloads are offered, OBJ contains the ridge endpoints
  `(3, 3, 3)` and `(7, 3, 3)` and the eave corners at height 0, and the glTF
  positions use `(x, height, −y)` — the ridge point `(7, 3, 3)` is
  `(7, 3, −3)`.
- A Failure page and a non-terrain page offer neither download.
- A dormer example whose 3D is shown offers both downloads, and the mesh has
  the triangles of that solid.
- A download post uses the snapshot inputs. Changing a coordinate field in
  that post away from the snapshot is out of the download's contract; the
  test posts the snapshot and gets the shown rectangle, not a roof of the
  edited ring.
- OBJ has no `mtllib`. The glTF is a single `.glb` mesh.

## Out of Scope

Joining loose `LINE` entities into a ring. Exploding blocks. Reading
`$INSUNITS`. A layer picker. Imperial units. SVG, IFC, and `.3dm`. Materials
beyond the one flat glTF grey, MTL sidecars, hip/ridge/valley curves, and
wall solids.

Parsing DXF in the browser. A core function that reads or writes files.
Teaching the help agent to upload or download. Auto-running **Update roof**
as part of a successful upload. Deleting or moving dormers to fit the new
footprint.

A new notebook file. A Python example under the README Examples heading.

## Story coverage

| Stories | Ticket |
|---|---|
| 1–24, 25 (DXF bullet), 46–48 | 01 Upload a DXF footprint onto the selected cell |
| 25 (download bullet), 26–39 | 02 Download the solid on the page as OBJ and glTF |
| 40–45 | 03 Document the DXF and the mesh |

## Further Notes

**Demo, not a CAD importer.** The useful file is one straight footprint,
optionally with holes, exported from model space. A full sheet will often
refuse on two outermost polylines, and that refusal is the demo working.
Future work already ranks DXF in and glTF/OBJ out, and ranks `.3dm` and IFC
as later; this spec does not start those.

**The split POST is deliberate.** Drawing updates the form in the browser and
leaves the solid until **Update roof**. A file has to reach the server, so
the upload POST returns the new fields and the old drawings together. Folding
the rebuild into that same response would drop story 23.

**Seam.** One seam, the existing form HTTP round-trip. It is the highest seam
that already wraps `roof` / `project` and the solid. A lower parser unit test
would duplicate it.
