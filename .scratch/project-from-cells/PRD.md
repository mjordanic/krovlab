# PRD: Project from cells

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — cell, project, roof, footprint, wall, eave height, pitch, gable
end, terrain, face, takeoff, Failure — and not loosely. A cell is not a wing. A
project is not required to be one terrain. Respects ADR-0001 (own weighted
straight skeleton) and ADR-0002 (Python form server wraps the core).

Depends on the existing `roof` seam. Does not replace it.

## Problem Statement

An architect's new-build roof is often several simple roofs on one building, not
one skeleton over the outer wall. Two gables concatenated along a party wall,
one half of a facade at 5 m eave height and the other at 7 m, a garage butted to
the house — those are two footprints that share a wall, each with its own pitch
and eave height.

Today the library takes one footprint and one eave plane. Splitting a straight
wall into collinear edges and assigning two pitches is not a terrain and is
refused. Roofing each wing in a separate call works, but the architect then
stitches quantities and drawings by hand, and the page can only edit one ring.

The page is a coordinate table. The architect already thinks in plan: click the
walls, draw the next cell, set that plate height.

## Solution

A project is a list of cells. Each cell is a polygon the architect draws, roofed
by the existing one-footprint call, at that cell's eave height. Shared walls are
coincident edges. The library joins the roofs into one takeoff and one drawing.
The page treats the plan as the editor.

The worked case is two 5 × 6 m gable cells sharing a party wall, plate heights
5 m and 7 m, pitch 45°. Not one rectangle with a split wall.

The one-footprint function stays. An optional eave height on that call lifts a
single roof. A second public function, `project`, takes the list of cells and
returns a project or a named Failure. The wavefront stays internal.

The page keeps a form POST (ADR-0002). The plan is a drawing surface that writes
the same fields: click to place vertices of the active cell, close the ring, add
another cell, click an edge for pitch or gable, set that cell's eave height.
Coordinate tables remain as the millimetre inspector, not the only way in.

## User Stories

**Producing a project**

1. As an architect, I want to give several footprints as cells and get one
   project back, so that concatenated gables and butted wings are one takeoff.
2. As an architect, I want each cell to have its own eave height, so that a 5 m
   plate next to a 7 m plate is sayable.
3. As an architect, I want each cell to have its own pitch list, including
   gables, so that one wing can be a hip and the neighbour a gable.
4. As an architect, I want a shared wall to be the coincident edges of two
   cells, so that I draw two polygons the way the building is, not a cut through
   one outline.
5. As an architect, I want a shared wall that is a gable on both cells to be a
   party wall, so that the 5 m / 7 m example needs no extra stitch.
6. As an architect, I want a shared wall that is pitched on both cells, at the
   same eave height, to meet as a valley, so that an M-roof is two cells facing
   a common inner eave.
7. As an architect, I want the one-footprint call to still roof one cell, so
   that the rectangle, L, courtyard and gable I already have do not change.
8. As an architect, I want an eave height on that one-footprint call to lift a
   single roof, so that a house on a 7 m plate is one argument, not a one-cell
   project.
9. As an architect, I want overlapping cells refused by name, so that I fix the
   drawing instead of double-counting covering.
10. As an architect, I want a shared edge that is gabled on one cell and pitched
    on the other refused by name, so that I do not get a silent hole in the
    covering.
11. As an architect, I want a pitched shared edge with unequal eave heights
    refused by name, so that a step in the gutter is a Failure, not a warped
    valley.
12. As an architect, I want two pitches on collinear segments of one cell still
    refused as unsupported, so that two pitches along one facade stay two cells.
13. As an architect, I want an L drawn as one polygon to stay one cell, so that
    the library never auto-cuts my outline.
14. As an architect, I want two detached rectangles in one project to be two
    cells (two wings), so that a house and a garage on one site are one takeoff
    without sharing a wall.
15. As an architect, I want a cell to still accept a hole, an overhang, and
    either winding, so that a courtyard wing in a project is the same as a
    courtyard roofed alone.
16. As an architect, I want a one-cell project to match that cell roofed and
    lifted alone, so that wrapping a single roof in a project does not change
    numbers.
17. As an architect, I want an empty list of cells refused by name, so that a
    blank drawing is not a zero-area project.

**Reading a project**

18. As an architect, I want the project's total sloped area to be the sum of the
    cells', so that covering is the number I buy.
19. As an architect, I want the project's ridge height to be the highest point
    above datum, so that I can check a height limit on the whole building.
20. As an architect, I want each face to name the cell and the edge it rises
    from, so that I can connect quantities back to a wall.
21. As an architect, I want a party wall not counted twice as eaves in the
    takeoff, so that I do not buy two gutters for one wall.
22. As an architect, I want a valley formed by two pitched shared eaves counted
    once, so that the inner gutter is one run.
23. As an architect, I want a project whose cells are all terrains, that does
    not overlap, and whose shared edges agree, to say so plainly, so that I
    trust the numbers.
24. As an architect, I want a cell that fails the terrain check to keep its
    validity reasons, so that I can see which wing broke.
25. As an architect, I want metres and degrees throughout, so that I never
    convert for a second cell.
26. As a developer, I want the project returned as plain data rather than as a
    drawing, so that I can compute with it.
27. As a developer, I want callers who only use the one-footprint function not
    to see a cell index on faces, so that existing roofs do not grow a field
    they never fill.

**Drawing on the page**

28. As an architect, I want to draw a cell by clicking vertices on the plan and
    closing the ring, so that I do not type a coordinate table to start.
29. As an architect, I want to add another cell the same way, so that the second
    gable is a second polygon, not a row inserted in the first.
30. As an architect, I want to select a cell and set its eave height, so that
    the 5 m / 7 m split is a number on that cell.
31. As an architect, I want to click an edge and set its pitch or mark a gable,
    so that the wall I am looking at is the wall I am editing.
32. As an architect, I want the coordinate table to stay in sync with the
    drawing, so that I can type millimetres when a click is too coarse.
33. As an architect, I want editing a table cell to move the corresponding
    vertex on the plan, so that the inspector is not a one-way dump.
34. As an architect, I want to delete a cell I drew by mistake, so that a
    mis-click is not a permanent extra roof.
35. As an architect, I want the first visit to still show the 10 × 6 m rectangle
    at 45°, so that a URL remains a demo.
36. As an architect, I want a corpus preset of two concatenated gables at
    different eave heights, so that the 5 m / 7 m case is one dropdown pick.
37. As an architect, I want choosing that preset to fill both cells' rings,
    pitches, and eave heights, so that I can submit without redrawing.
38. As an architect, I want existing one-ring corpus presets to remain one
    cell, so that the rectangle, L, courtyard, gable, and bowtie still work.
39. As an architect, I want a terrain project to show one plan of every cell and
    one orbitable 3D solid of the lot, so that I judge the whole building.
40. As an architect, I want a Failure or a non-terrain cell to follow the
    existing three result branches (input drawing / plan only / plan and 3D), so
    that I already know how to read the page.
41. As an architect, I want submitting the drawn 5 m / 7 m pair to report the
    same ridge height and sloped area as the library, so that the page is not a
    second geometry.

**Trusting it**

42. As an architect, I want the same cells to always produce the same project,
    so that a change in the output came from a change I made.
43. As a developer, I want failure as a value from `project`, never an
    exception, so that a bad cell does not take down a batch.
44. As a developer, I want the core to stay free of Flask and of I/O, so that
    ADR-0001's exit stays cheap.
45. As a developer, I want the page to remain one form POST, so that ADR-0002 is
    not reversed: the canvas writes fields, submit is still POST.
46. As a developer, I want nothing the form accepts to raise out of the request,
    so that a bad POST is a page with a Failure, not a 500.
47. As a developer, I want the wavefront to stay untested from this spec, so
    that composition does not reopen the skeleton.

## Implementation Decisions

**Two public functions, not a new engine.** The one-footprint function remains
the skeleton seam. The new function takes a list of cells and returns a project
or a Failure. It roofs each cell through the existing function, lifts nodes by
that cell's eave height, and assembles one value. Tests of composition go
through the new function. Tests of one polygon still go through the existing
one.

**A cell is input data.** It carries a footprint, a pitch (one angle or one per
edge of that cell), optional holes, an overhang, and an eave height in metres
above datum. Default eave height is zero. There is no join argument and no
cell-to-cell pointer.

**A project is data, like a roof.** It carries the per-cell roofs (already
lifted), the union of faces and arcs (each face names which cell and which edge
of that cell), total sloped area, ridge height as the maximum above datum, and a
validity result. No rendering concepts. A project is valid when every cell is a
terrain, cells do not overlap in plan, and every coincident edge pair agrees.

**Assess, then lift.** The one-footprint function without an eave height still
builds eaves at height zero and runs the existing terrain checks. Eave height
adds a constant to every node's height afterwards. Validity is not rewritten in
the lifted frame.

**Shared walls are geometry, not a join argument.** Two edges coincide when they
lie on the same segment to the existing vertex tolerance. The architect does not
name a join. If both are gables, they are a party wall and the roofs do not
stitch. If both are pitched and eave height matches, the two eaves are one
valley in the project takeoff — do not count the gutter twice. Any other pairing
is a named Failure.

**Do not auto-decompose an outline.** An L drawn as one polygon is one cell. Two
rectangles that share a wall are two cells. The architect draws the polygons.

**Do not assign two pitches to collinear segments of one cell.** That stays
unsupported. Two pitches along one facade are two cells.

**The plan is the editor; the table is the inspector.** Page script draws on the
plan and writes the same posted fields the server already reads, extended for
more than one cell and for eave height. Submit remains a POST of the existing
page. No JSON API, no fetch of roofs (ADR-0002). Extra page script is expected;
a second frontend stack is not.

**Presets stay the corpus.** Add one committed fixture that is two cells: the
5 m / 7 m concatenated gables. Choosing it fills both cells. The default GET is
still the single-cell 10 × 6 m rectangle.

**Face edge index stays the index in that cell's ring.** The project adds a cell
index. Callers who only use the one-footprint function do not see a cell index.

**Pitch remains the parameter; weight stays internal.** Gable remains pitch 90.
Per-cell pitch spellings are whatever the one-footprint function already parses.

## Testing Decisions

**A good test here asserts a property of the project the architect can see, not
a step of assembly.** Overlap, shared-edge agreement, summed takeoff, and lifted
ridge height are behaviour. How cells are stored in the form, how coincidence is
detected internally, and the wavefront are not. Tests of composition go through
`project`. Tests of one polygon still go through `roof`. Web tests hit GET and
POST of the page.

**Worked example, hand-computed.** Two 5 × 6 m gable cells, party wall, plate
heights 5 m and 7 m, pitch 45°. Each cell's ridge height above its eave is 2.5 m
on the 5 m span; absolute ridges are 7.5 m and 9.5 m. Project ridge height is
9.5 m. Plan areas sum to 60 m². Both cells are terrains. No overlap.

**Invariants on a project.** For generated non-overlapping cells:

- Sum of cell plan areas equals the union area.
- Total sloped area equals the sum of cell sloped areas.
- Ridge height equals the max lifted node height.
- Same input, byte-identical project.

**Refusals are tests.** Overlap; shared edge gable versus pitch; pitched shared
edge with unequal eave height; empty cell list; two pitches on collinear edges
of one cell (still unsupported).

**Page tests.** Drawing a second cell and posting it produces the same describe
numbers as `project` in Python. The concatenated-gables preset shows terrain and
3D. A Failure still shows the input drawing and no 3D. Default GET is still the
10 × 6 m rectangle at 45° with ridge height 3 m.

**Visualisation is smoke-tested.** The combined solid builds. No pixel asserts.

**Prior art.** The one-footprint entry point and its Failure kinds; validity
assessment; adjacent parallel pitches still unsupported; Flask test client
against the form page; three result branches from the form-server spec; corpus
presets by name; worked numbers on the 10 × 6 m rectangle at 45°; same-pitch
collinear vertices already a terrain (two coplanar faces) — do not reopen that
as a composition substitute. Do not re-assert the terrain invariants the
library tests already own for a single cell.

## Out of Scope

Half-hips, knee-walls, gablets, gambrels, mansards. Dormers. A roof graph (one
face wrapping several walls, alternate duals). Those belong in the roofs-beyond-
skeleton spec.

RoofDiT and any learned prior over roof graphs. Reconstruction from imagery.

Auto-cutting one outline into cells. Cut-lines as a drawing tool.

A JSON API, a SPA, or a second web stack. DXF or `.3dm` import. Cost, price
books, optimization.

Fixing every non-terrain T or plus-shape. Composition does not wait on those.
They remain documented limitations.

Undo, accounts, saved designs, and snapping beyond the existing vertex
tolerance.

## Story coverage

| Stories | Ticket |
|---|---|
| 7 (one-footprint call plus optional height), 8, 25 (metres), 27, 35 | 01 eave height on a single roof |
| 1–3, 7, 9, 13–20, 23 (starts: terrains and no overlap), 24–26, 38–40, 42–44, 45 (starts: POST of more than one cell via tables), 46, 47 | 02 project of cells |
| 4–6, 10–12, 21, 22, 23 (finishes: shared edges agree), 36, 37, 41 | 03 shared walls and concatenated gables |
| 28–34, 45 (finishes: canvas writes fields) | 04 plan as the cell editor |

## Further Notes

**This is the 80%.** National LoD2 models already store mixed roofs as several
building parts, each with one simple type. The architect's 5 m / 7 m wall is
that pattern. One skeleton over the outer 4-gon cannot say it.

**Usability is the API test.** If the 5 m / 7 m roof takes more than two cells
and one project call, the seam is wrong. If the page requires typing twelve
numbers before the second cell exists, the editor is wrong.

**Same-pitch extra vertices are already a terrain.** Two coplanar faces on one
cell are not composition. Differing pitches on collinear edges of one cell stay
unsupported.

**The 20% spec is blocked by this one.** Knee, gambrel, wrap, and dormer are
data on a cell or arguments to `project`, not a third public engine.
