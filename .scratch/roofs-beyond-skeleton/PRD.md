# PRD: Roofs beyond the skeleton

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — cell, project, roof, face, pitch, eave, gable end, terrain,
additive weight, Failure — and not loosely. Respects ADR-0001 (own skeleton, so
additive weights stay reachable) and ADR-0002 (form POST wraps the core).

Blocked by the project-from-cells spec. That seam — cell, `project`, plan as
editor — is the surface these types are added to. Do not invent a parallel entry
point.

## Problem Statement

A straight skeleton of a cell, even composed into a project, still emits one
sloping face per footprint edge, from a uniform eave. That misses roofs an
architect actually specifies on a new-build or a renovation wing:

- A half-hip, Dutch, or gablet: the wall rises vertically for a stretch, then a
  small hip closes. Additive weight (a delay), not a second cell.
- A gambrel or mansard: the same wall is steep, then shallow. Two pitches
  stacked up the slope, not along the facade.
- A dormer: a small roof that sits on a host face and cuts it. Not a cell at
  eave height.
- A wrap-around plane: one face covering two or more consecutive walls, no hip
  at the corner. The skeleton cannot do this. A roof graph can.

Each of these is rarer than concatenated gables. Together they are the rest of
the pitched jobs this tool should eventually take. They are also the expensive
20%: new geometry, not another cell in the list.

The page must keep speaking in walls, plate heights, and pitches. The architect
does not type a dual graph or an additive weight.

## Solution

Keep the one-footprint function and `project`. Add four operations an architect
can name, each a small piece of data on a cell or on the project:

1. **Knee height** on an edge — the wall rises vertically this many metres, then
   the edge's pitch begins. Half-hip, gablet, Dutch. Internally an additive
   weight; the architect never sees a weight.
2. **Gambrel** on an edge — two pitches and the height where the break happens.
   Steep then shallow up that wall.
3. **Dormer** — a small footprint drawn on a host face, with its own pitch
   (usually a gable or a shed). A child roof, clipped to the host. The host
   face's sloped area shrinks by the opening; the dormer faces add.
4. **Wrap** — consecutive edges of one cell marked as one plane. That cell is
   embedded with a roof graph, not a skeleton. Pitch is one value for the merged
   face.

The page: select an edge for knee or gambrel; draw a small rectangle on a host
face for a dormer; select consecutive walls and "one plane" for a wrap. Submit
is still POST. The core still returns data, never drawings.

RoofDiT and any learned graph prior stay out. There is no general dual-graph
editor. Wrap is the one graph operation; alternate ridge layouts that are not
"these walls are one plane" stay out.

## User Stories

**Knee, gablet, Dutch**

1. As an architect, I want to set a knee height on an edge in metres, so that
   the wall stands vertical to that height and then the hip begins.
2. As an architect, I want a zero knee height to be the same roof as today, so
   that ordinary hips do not need a new argument.
3. As an architect, I want a gable (pitch 90) with a knee height refused by
   name, so that I do not combine two ways of saying vertical.
4. As an architect, I want a half-hip, a Dutch gable, and a gablet to be the
   same knob at different heights, so that I am not learning three tools for one
   delay.
5. As an architect, I want a knee on one edge of a two-cell project to affect
   only that cell, so that a half-hip on the house does not change the garage.

**Gambrel and mansard**

6. As an architect, I want to give an edge a steep pitch, a shallow pitch, and a
   break height, so that a barn break is three numbers on that wall.
7. As an architect, I want the takeoff to report two faces on that wall (steep
   then shallow), so that I buy two coverings or see the extra area.
8. As an architect, I want a gambrel and a knee on the same edge refused by
   name, so that one wall has one story.
9. As an architect, I want a gambrel and a gable on the same edge refused by
   name, so that a vertical wall is not also a two-pitch slope.
10. As an architect, I want break height measured above that cell's eave, so
    that I am not converting from a paper's delay units.

**Dormers**

11. As an architect, I want to place a dormer by drawing a small footprint on a
    host face, so that a bedroom window roof is a polygon on the slope, not a
    new cell at eave height.
12. As an architect, I want that dormer to have its own pitch and gables, so
    that a gable dormer and a shed dormer are the same tool.
13. As an architect, I want the host face's sloped area to lose the opening and
    the dormer faces to add, so that covering is not double-counted.
14. As an architect, I want a dormer that does not sit on a single host face
    refused by name, so that a dormer over a hip is a drawing error, not a
    folded surface.
15. As an architect, I want a dormer outside the host face refused by name, so
    that a floating box is not clipped onto the wrong slope.
16. As an architect, I want several dormers on one project, so that a street
    facade with three dormers is three placements, not a new engine.
17. As an architect, I want a dormer on a wrapped face to still clip that one
    plane, so that wrap and dormer compose.
18. As an architect, I want a project with dormers to say it is not a single
    terrain, so that I am not told a hole in the covering is a valid terrain.
19. As an architect, I want that same project to still show an orbitable 3D
    solid, so that a deliberate dormer is not hidden the way a broken
    plus-shape is.

**Wrap-around plane**

20. As an architect, I want to mark consecutive edges of a cell as one plane, so
    that a face can wrap a corner without a hip.
21. As an architect, I want one pitch for that wrapped face, so that I am not
    asked for a pitch per wall when I just said they are one slope.
22. As an architect, I want a wrap that cannot be a planar terrain refused by
    name, so that an impossible corner is a Failure, not a warped face.
23. As an architect, I want a wrap of non-consecutive edges refused by name, so
    that I cannot skip a wall and call the rest one plane.
24. As an architect, I want wrapped edges with disagreeing pitches refused by
    name, so that one plane is not two slopes.
25. As an architect, I want a cell with no wrap groups to be the existing
    skeleton, so that wrap is opt-in.

**On the page**

26. As an architect, I want to click an edge and set knee height or a gambrel
    break, so that the wall I see is the wall I edit.
27. As an architect, I want to draw a dormer on the 3D solid or the plan as a
    rectangle on a face, so that I do not type the dormer in a table first.
28. As an architect, I want to select consecutive edges and choose one plane, so
    that wrap is a selection, not a graph editor.
29. As an architect, I want the existing cell drawing, eave heights, and project
    takeoff to keep working, so that a half-hip on one wing of a two-cell
    project is a property of that cell, not a new page.
30. As an architect, I want millimetre tables for knee, break height, and dormer
    rings, so that a click that is too coarse can still be typed.
31. As an architect, I want a plus-shape or other documented non-terrain still
    to hide 3D, so that the dormer exception does not silently weaken the
    broken-skeleton branch.

**Trusting it**

32. As an architect, I want each new type to still say whether the result is a
    terrain, so that I never unknowingly work from an impossible roof.
33. As an architect, I want the same input to always produce the same project,
    so that a change in the output came from a change I made.
34. As a developer, I want additive weight, two-stage pitch, clipping, and graph
    embedding to stay behind `roof` and `project`, so that there is still no
    third engine on the public seam besides those two functions plus the small
    data on a cell and a dormer.
35. As a developer, I want the architect never to see a weight, so that delay
    stays metres of wall.
36. As a developer, I want the page to remain a form POST, so that ADR-0002
    holds.
37. As a developer, I want failure as a value, never an exception, so that a
    bad wrap or dormer does not take down a batch.
38. As a developer, I want the core to stay free of Flask and of I/O, so that
    ADR-0001's exit stays cheap.

## Implementation Decisions

**Architect words on the seam; weights inside.** Knee height is metres of
vertical wall. Break height is metres above that cell's eave. Additive weight
and wavefront delay are converted at the boundary, the same way pitch becomes
cotangent today. No weight on a cell, a dormer, or the returned roof.

**Same two functions.** A cell grows optional knee, gambrel, and wrap data. A
dormer is extra input to `project`: which cell, a plan footprint sitting on one
host face, and a pitch. There is no public from-graph function the architect
must call.

**A wrap group is two or more consecutive edges of that cell.** Those edges must
share one pitch (or one gambrel); they become one face. That cell is not run
through the existing wavefront. It is embedded with a roof graph in the sense of
Ren et al. 2021: outline vertices, merged outline edges as one face, planarity
as the objective. If the embedding is not planar to the existing planarity
tolerance, return a Failure.

**Dormers after the host exists.** `project` roofs every cell first, including
knee, gambrel, and wrap. Then each dormer is located onto a host face by plan
overlap: the dormer's footprint must lie in the plan projection of exactly one
face of that cell. The child is the one-footprint function on the dormer ring,
lifted onto the host plane — the dormer's eave is the intersection with the
host, not the building eave. Clip. Quantities: subtract the opening's sloped
area from the host face; add the dormer faces. Prefer not inventing a new arc
kind until a test needs it; dormer eaves can stay eaves.

**A project with dormers is not a single terrain.** Validity records that.
Quantities remain usable. 3D still draws: host with a hole, dormer solid on
top. The "no 3D unless terrain" rule from the form-server spec is relaxed for
this case only: a project that is valid except for dormer openings still gets a
3D solid, with the describe block saying it is not a terrain. A plus-shape or
other broken skeleton still does not.

**Knee is a delay, not a second cell.** Do not ask the architect to draw a
vertical strip as its own polygon. The wavefront starts that edge after time
equals knee height (unit rise). Gablet, Dutch, and half-hip are the same knob
at different heights, plus a gable or a small remaining hip as the pitch on
that edge.

**One story per edge.** An edge may be a hip, a gable, a knee-then-hip, or a
gambrel. Combinations on one edge are named failures.

**No dual-graph editor.** Wrap is the only graph edit. There is no UI for
picking another dual of this outline. Alternate styles that are not wrap remain
the existing gable mask and a project of several cells.

**Page fields.** Knee, gambrel, wrap, and dormer rings are extra form fields
written by the plan and solid clicks, same POST as cells. The core does not
import Flask.

**If wrap or dormers seem to need a third public function besides the two
existing ones, stop.** Revisit this spec rather than growing a from-graph the
architect has to call.

## Testing Decisions

**Seams stay `roof` and `project`.** Knee, gambrel, and wrap live on a cell and
are visible only through those functions. Dormers through `project`. Web tests
hit GET and POST of the page. Tests do not open the event queue or a graph
data structure.

**A good test asserts the architect-visible roof, not the delay conversion.**
Face count, planarity, takeoff, named Failure, and whether 3D is present are
behaviour. Additive weight values, clip-mesh internals, and the graph embedding
steps are not.

**Worked examples, hand-computed.**

- Rectangle, one short edge knee height equal to the would-be ridge of a full
  hip: that edge is a vertical gablet; neighbouring faces close over it as
  verges above the knee. Ridge height matches the un-kneed rectangle.
- Rectangle, long edges gambrel 60° then 30° with a known break: two faces per
  long wall; plan areas sum to the footprint; sloped area is the sum of the two
  bands.
- Rectangle plus one gable dormer whose plan is a 2 × 1.5 m rectangle on a long
  slope: host sloped area decreases by the opening; dormer adds two or three
  faces; project is not a terrain; 3D still builds.
- L-shape with the inner corner's two walls wrapped to one plane: one face, no
  valley at that corner; planarity holds; the result is a terrain if the rest of
  the cell is a normal hip.

**Invariants.** Where the result is still a terrain (knee, gambrel, wrap, no
dormer): existing plan-area, planarity, and drainage-to-own-eave checks hold,
with "own eave" for a wrapped face being the union of the wrapped edges. Dormer
projects: plan areas of host-plus-dormer still cover the host footprint; no
double-count of the opening.

**Refusals.** Gable plus knee; gambrel plus knee; gambrel plus gable; wrap of
non-consecutive edges; wrap with disagreeing pitches; dormer overlapping two
faces; dormer outside the host.

**Page tests.** Setting a knee on an edge via POST matches a cell with that knee
height. Drawing a dormer rectangle and posting matches a dormer on that cell.
Wrap of two edges shows one face in the describe block. A plus-shape POST still
shows plan, validity reasons, and no 3D.

**Prior art.** ADR-0001 (additive weights reachable); the limitations note's
deferred list; Ren et al. 2021 on faces with several outline edges; Held and
Palfrader on additive weights; existing gable as pitch 90; existing planarity
tolerance; three result branches from the form-server spec, with the dormer
exception above; `project` and cell from the project-from-cells spec.

## Out of Scope

RoofDiT, image-guided reconstruction, and any sampled graph prior.

A general roof-graph editor (arbitrary duals, snapping interior vertices by
hand). Wrap is the one operation.

Chimneys, rooflights, and other penetrations that are not dormers. Curved walls.
Split-level inside one cell (that is still two cells).

Cost, price books, optimization. DXF or `.3dm`. A SPA. A JSON API.

Changing the 80% cell and project model.

## Story coverage

| Stories | Ticket |
|---|---|
| 1–5, 26 (starts: click edge for knee), 29, 32–38 | 01 knee height |
| 6–10, 26 (finishes: click edge for gambrel) | 02 gambrel |
| 20–25, 28 | 03 wrap consecutive edges |
| 11–19, 27, 30, 31 | 04 dormers |

The whole folder waits on project-from-cells (cells, `project`, plan as editor).
That wait is a prerequisite on each ticket, not a same-folder Blocked by line.

## Further Notes

**This is the 20%.** It is larger code per job than composing two cells. Ship
cells first. Additive weights were the reason ADR-0001 owns the wavefront; knee
height is that bill coming due. Gambrel is a second wavefront or a weight that
changes at a height — related, not the same knob. Dormers are constructive
solid geometry. Wrap is Ren's constructor behind one operation.

**Usability is the API test.** A half-hip is a knee height on an edge, not a
delay in a paper's units. A wrap is "these walls are one plane", not an
adjacency matrix. A dormer is a small footprint on a face, not a clip mesh the
architect builds.

**Dormers and terrain.** The form-server spec hid 3D when the result is not a
terrain because a broken skeleton is a hole in the covering. A dormer is a
deliberate hole. The describe block must still say it is not a terrain; the
solid must still draw. That is a documented exception, not a quiet weakening of
the plus-shape case.
