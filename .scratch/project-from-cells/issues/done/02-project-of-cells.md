# 02: Project of cells

**What to build:** The architect gives one or more cells and gets one project
back. Each cell is a footprint with its own pitch list (including gables),
optional holes and overhang, and its own eave height. `project` roofs each cell
through the existing one-footprint function, lifts by that cell's eave height,
and returns a project: per-cell roofs, faces that name cell and edge, total
sloped area as the sum, ridge height as the highest point above datum, and a
validity result.

Shared-wall agreement is ticket 03. This ticket still refuses overlapping cells
and an empty list, treats an L drawn as one polygon as one cell (no
auto-decompose), and allows two detached rectangles as two cells (two wings). A
one-cell project matches that cell roofed and lifted alone. A cell that is not a
terrain keeps its validity reasons. Failure is a value. The same cells always
produce the same project.

On the page, the millimetre tables can describe a second cell and submit is
still one form POST. A terrain project shows one plan of every cell and one 3D
solid of the lot. Failure and non-terrain follow the existing three result
branches. One-ring corpus presets stay one cell. Drawing on the plan is ticket
04; typing a second ring is enough to demo this slice.

The core still imports no Flask and no I/O. Tests of composition go through
`project`; tests of one polygon still go through `roof`. The wavefront stays
behind those seams.

**Blocked by:** 01 eave height on a single roof

**Status:** done

**Complexity:** high

**Stories:** 1, 2, 3, 7, 9, 13, 14, 15, 16, 17, 18, 19, 20, 23 (starts: all
terrains and no overlap; shared-edge agreement in 03), 24, 25, 26, 38, 39, 40,
42, 43, 44, 45 (starts: POST of more than one cell via tables; canvas in 04),
46, 47

**Prior art:** Feature PRD "Two public functions, not a new engine", "A cell is
input data", "A project is data, like a roof", "Do not auto-decompose". Ticket
01 for lift. `roof` Failure kinds and validity assessment. Flask test client;
three result branches from the form-server spec. Corpus one-ring presets
(`rectangle-10x6`, `l-shape`, `courtyard`, `rectangle-gabled`, `bowtie`). Do not
re-assert single-cell terrain invariants already owned by the library tests.

- [x] `project` of one cell equals that cell passed through `roof` with the same
      eave height (quantities, terrain flag, no extra faces)
- [x] Two detached 5 × 6 m rectangles at eave heights 5 m and 7 m, both 45°
      hips, return a project whose plan areas sum to 60 m², total sloped area is
      the sum of the cells, and ridge height is the max lifted node
- [x] Each face names the cell index and that cell's edge index
- [x] Overlapping cells return a named Failure, not a double-counted takeoff
- [x] An empty list of cells returns a named Failure
- [x] An L as one polygon is one cell; the library does not cut it into two
- [x] A cell with a hole, an overhang, or the opposite winding still roofs
- [x] A non-terrain cell keeps `validity.reasons` on the project
- [x] Same input, byte-identical project; Failure is a value, never an exception
- [x] POST of two cell tables (detached) shows combined plan and 3D when both
      are terrains, and does not 500
- [x] Existing one-ring presets still POST as one cell
- [x] Core package still imports no Flask and no I/O
- [x] Tests do not open the event queue

## Comments

`project` roofs each cell through `roof`, then refuses overlapping plan
regions (`overlap`) and an empty list (`empty`). Faces on a `Project` carry
`cell_index`; `Face` from the one-footprint call does not. Shared-wall
agreement is ticket 03 — coincident edges that only share a wall are not
an overlap. The form keeps cell 0 on the existing field names; further
cells post as `cell-N-*` when Edit vertices is checked. `plan_view` and
`solid_view` consume a `Project` as one plan of every cell and one solid.
