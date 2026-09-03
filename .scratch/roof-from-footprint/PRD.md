# PRD: Roof from footprint

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — "roof", "face", "pitch", "sloped area", "hip", "valley",
"terrain", "weight", "event" — and not loosely. Respects ADR-0001 (own weighted
straight skeleton, in Python, no CGAL).

## Problem Statement

An architect designs roofs by hand, repeatedly. Given a building footprint he
must work out where the ridges, hips and valleys fall, how high the roof gets,
and how much surface there is to cover. Today he does this in Rhino with a
straight-skeleton script he wrote, and it takes a large share of his time.

Three things make it slow. The geometry is fiddly and easy to get subtly wrong
on anything more complex than a rectangle. It has to be redone from scratch
every time the footprint, the pitch, or the client changes. And getting
quantities out of it — how many square metres of covering, how many metres of
ridge — means measuring the result by hand afterwards.

Underneath that is a correctness problem he may not be able to see. A roof must
be a terrain: exactly one height at every point in plan, with water draining to
the eaves from anywhere on the surface. A script that produces plausible-looking
geometry can silently violate this, and the error surfaces on site.

## Solution

A library that turns a footprint and a set of pitches into a roof, and can show
it.

The user gives a footprint as a list of coordinates and either one pitch for the
whole roof or one pitch per edge. They get back a roof: its faces, each with its
pitch and its plan and sloped areas; its arcs, each classified as ridge, hip,
valley, eave or verge, with its length; and every node's height. From that they
can see the roof in plan, watch the wavefront propagate if they want to
understand why it came out that way, and view the finished solid in 3D.

The roof is checked against the terrain property rather than assumed to satisfy
it. When the geometry cannot be produced the library says so and says why,
rather than returning something that looks like a roof and isn't.

The whole thing runs locally with no server. The 3D view is a self-contained
HTML file that opens in a browser from disk.

## User Stories

**Producing a roof**

1. As an architect, I want to give a footprint as a plain list of `(x, y)`
   coordinates, so that I can get started without learning a file format.
2. As an architect, I want to give one pitch for the whole roof, so that the
   common case takes one argument.
3. As an architect, I want to give a different pitch for each footprint edge, so
   that I can model a roof whose sides aren't all the same slope.
4. As an architect, I want a footprint with reflex corners — L-shapes, T-shapes,
   U-shapes — to work, so that the tool handles the buildings I actually draw
   rather than only rectangles.
5. As an architect, I want a footprint with a hole to work, so that I can roof a
   building around a courtyard or light well.
6. As an architect, I want to declare an edge to be a gable end, so that I can
   model the most common alternative to a fully hipped roof.
7. As an architect, I want to apply an eaves overhang, so that the roof projects
   beyond the walls as a real roof does.
8. As an architect, I want the coordinate order of my footprint not to matter,
   so that I don't have to know which way round the library wants it.
9. As an architect, I want to work in metres and degrees throughout, so that I
   never have to think about the internal representation.
10. As an architect, I want to express pitch as a rise:run ratio or a percentage
    and have it converted, so that I can use whichever convention the drawing
    uses.

**Understanding the result**

11. As an architect, I want each roof face labelled with the footprint edge it
    rises from, so that I can connect the model back to the building.
12. As an architect, I want each face's plan area and sloped area reported
    separately, so that I can see how much extra material the pitch is costing
    me.
13. As an architect, I want every arc classified as a ridge, hip, valley, eave
    or verge, so that I can count the items that are priced per metre.
14. As an architect, I want the length of every arc, so that I can total
    ridge, hip and valley runs without measuring the drawing.
15. As an architect, I want the height of every node and the overall ridge
    height, so that I can check the roof against a height limit.
16. As an architect, I want the total sloped area of the roof, so that I have
    the single number that drives covering cost.
17. As a developer, I want the roof returned as plain data rather than as a
    drawing, so that I can compute with it.

**Seeing it**

18. As an architect, I want a plan view showing the footprint with the skeleton
    drawn over it, arcs coloured by type, so that I can read the roof's layout
    at a glance.
19. As an architect, I want node heights annotated on the plan view, so that I
    can understand the roof's third dimension without leaving 2D.
20. As an architect, I want an interactive 3D view of the roof solid that I can
    orbit, so that I can judge whether it looks right.
21. As an architect, I want to save any view as a single HTML file that opens
    from my desktop, so that I can look at it and send it to someone without
    running a server.
22. As a developer, I want to render the wavefront at a chosen time, so that I
    can see the propagation that produced the skeleton.
23. As a developer, I want to step through the wavefront at successive times, so
    that I can find the exact event where a bad roof went wrong.

**Trusting it**

24. As an architect, I want to be told when the result is not a valid terrain,
    so that I never unknowingly work from an impossible roof.
25. As an architect, I want to be told when a footprint can't be roofed at all,
    with the reason, so that I can fix my input instead of guessing.
26. As an architect, I want a self-intersecting or degenerate footprint rejected
    with a clear message, so that bad input fails immediately rather than
    producing nonsense.
27. As an architect, I want the same input to always produce exactly the same
    roof, so that I can trust that a change in the output came from a change I
    made.
28. As a developer, I want failure reported as a value rather than an exception,
    so that a caller processing many footprints isn't derailed by one bad one.
29. As a developer, I want a verifiable guarantee that the faces' plan areas sum
    to the footprint area, so that I know no part of the building is unroofed or
    double-covered.
30. As a developer, I want a verifiable guarantee that every face is planar, so
    that reported areas mean what they say.
31. As a developer, I want a verifiable guarantee that water drains from every
    face to that face's own eave, so that the roof is correct in the sense that
    makes straight skeletons the right algorithm.

**Working on it**

32. As a developer, I want the core to have no third-party dependencies, so that
    it can later be embedded in a server, a notebook or a browser without
    dragging anything with it.
33. As a developer, I want to inspect the sequence of events the algorithm
    processed, so that I can diagnose an incorrect skeleton.
34. As a developer, I want a stable hash of the roof's combinatorial structure,
    so that I can tell whether a change in input changed the topology or only
    the geometry.
35. As a developer, I want a corpus of real footprints as regression fixtures,
    so that robustness is measured against real buildings rather than my
    imagination.

## Implementation Decisions

**One seam.** The library exposes a single entry point that takes a footprint
and pitches and returns a roof. Everything else — bisectors, the event queue,
the wavefront, event handling — is internal and is tested through that entry
point, not around it. Visualisation, export and the future takeoff are
consumers of the returned roof and never reach past it. This is the highest seam
available and there is deliberately only one.

**The returned roof is a value, not a drawing.** It carries faces, arcs, nodes
and a validity result. Faces know their defining footprint edge, pitch, plan
area and sloped area. Arcs know their classification and length. Nodes know
their height. No rendering concepts appear in it.

The shape of the entry point, which encodes several decisions at once:

```python
roof(
    footprint,          # [(x, y), ...] in metres, either winding accepted
    pitch,              # one angle in degrees, or one per footprint edge
    holes=None,         # [[(x, y), ...], ...]
    overhang=0.0,       # metres, applied by offsetting before generating
) -> Roof | Failure
```

**Pitch is the parameter; weight is internal.** The user supplies degrees. The
conversion to `weight = cot(pitch)` happens at the boundary and nowhere else.
This is not cosmetic: weight is unbounded as pitch approaches zero, and keeping
it out of the interface is what makes the values well-scaled for the future
optimizer.

**A gable is `pitch = 90`, not a separate flag.** A vertical face is the
`weight = 0` case: the edge doesn't move, and the neighbouring faces close over
it. Expressing it through the existing parameter avoids a parallel gable-mask
argument that would have to be kept consistent with the pitch list.

**Strictly positive weights only.** Pitch is constrained to `0 < pitch <= 90`.
This keeps us in the regime where weighted skeletons behave like unweighted
ones; negative weights are what make them non-planar, cyclic and non-terrain.
The constraint is enforced at the boundary, so the interior of the algorithm
never has to consider the pathological cases.

This deliberately widens the glossary's `0 < pitch < 90` at the top end: `CONTEXT.md`
describes the range of a sloping face, and 90 is admitted here solely as the
vertical-face (gable) case the glossary already defines. It is the only pitch
value that produces no face.

**Wavefront simulation, not motorcycle graphs.** A priority queue of events over
a circular list of active vertices, in the Felkel–Obdržálek shape. The
sub-quadratic algorithms win asymptotically and lose on implementation risk at
the polygon sizes an architect draws.

**Overhang is an offset, not a special case.** The footprint is offset outward
first and the roof of the enlarged footprint is generated. No overhang logic
exists inside the algorithm.

**Failure is a return value.** Unroofable input, a skeleton that fails to
complete, and a result that isn't a terrain are all reported as values carrying
a reason. Exceptions are reserved for programmer error. This matters more than
it looks: the future optimizer will generate degenerate configurations by the
thousand and must be able to keep going.

**Tie-breaking is deterministic.** Simultaneous and co-located events are
resolved by a fixed, documented rule. Ambiguity here is well known in the
literature, and a non-deterministic choice would later present to an optimizer
as objective noise while actually being a bug.

**Build order is by geometric difficulty, not by feature list.** Uniform pitch
on a convex footprint; then reflex corners, which introduce split events; then
per-edge pitch, which is what removes the equidistance oracle; then holes; then
gables; then overhang. Each stage is correct before the next begins, because
each later stage removes a check the earlier stage relied on.

**Visualisation uses Plotly and is a separate, optional module.** It consumes a
roof and returns figures. It is an optional extra so the core stays
dependency-free. Plotly is chosen over a 3D engine because it emits a
self-contained HTML file that opens over `file://` with no server, and because
the views that matter while building this are 2D.

**The third dimension is not a separate step.** The wavefront rises at unit rate
as it propagates, so a node's time is its height. There is no lifting stage to
build or to get wrong.

## Testing Decisions

**A good test here asserts a property of the roof, not a step of the
algorithm.** The event queue, the bisector maths and the wavefront are
implementation; the terrain property, the areas and the drainage direction are
behaviour. Tests go through the single entry point. A test that reaches into the
event queue is testing the thing most likely to be rewritten and least likely to
be wrong in a way that matters.

**Invariants are the primary tests, and they are property-based.** Generated
footprints, with the following required to hold for every roof produced:

- Face plan areas sum to the footprint area — nothing unroofed, nothing covered
  twice.
- Every face is planar.
- Every face's sloped area is at least its plan area, with equality only in the
  limit.
- The roof is a terrain: sampled points in plan have exactly one height.
- Steepest descent on every face points toward that face's own eave. This is the
  drainage property, and it is the reason the straight skeleton is the right
  algorithm — so it is the test that most deserves to exist.
- Every arc classification is consistent with its geometry: ridges horizontal,
  hips rising from convex corners, valleys from reflex corners.
- The same input yields a byte-identical roof across runs.

**Oracles, where an independent one exists.** For uniform pitch, every skeleton
node is equidistant from its defining edges — an exact, cheap check that does
not depend on our implementation being right. This is why the unweighted case is
built first: it is the only stage with a strong independent oracle, so it is
where the machinery gets shaken out. `shapely` is a dev dependency used solely
as a second opinion on areas and containment in assertions; the core must never
import it.

**Worked examples with hand-computed answers.** A square with uniform pitch has
a known apex height and four known faces. A rectangle has a ridge of known
length and position. An L-shape has exactly one valley. These are small enough
to verify by hand and are the tests that catch a systematically wrong constant.

**A corpus of real footprints as regression fixtures.** Sourced from the
architect's own recent projects, and committed to the repo under
`tests/fixtures/footprints/` — `.scratch/` is git-ignored, so fixtures and the
pass-rate report cannot live beside this PRD. Each is asserted to produce a valid terrain.
This is the robustness measure that matters, since robustness is the risk
ADR-0001 accepted, and it should be reported as a pass rate rather than
pass/fail so that progress is visible.

**Degenerate inputs are tests, not edge cases to handle later.** Collinear
edges, coincident vertices, a footprint that is a single point or line, a
self-intersecting footprint, a hole touching the outer ring, and simultaneous events
from symmetric footprints. Each has a defined outcome — a roof or a stated
failure — and never an exception or a silently wrong result.

**Visualisation is smoke-tested only.** That the figure builds without error.
Asserting on pixels would be brittle and would test Plotly.

There is no prior art in this repo; this is the first feature.

## Out of Scope

Cost, quantities beyond raw geometric measures, price books, and every form of
optimization. The reasoning and the research behind these are recorded in
`docs/future-work.md`; the deciding fact is that a pitch-only cost objective is
monotone and therefore degenerate.

Half-hips, knee-walls, gablets, gambrels and mansards. All need additive
weights. ADR-0001 keeps them reachable but they are not in this scope.

Dormers, chimneys, rooflights and any other roof penetration. Curved footprint
edges. Non-uniform eave heights and split-level buildings. Multiple disjoint
wings in a single call — roof them one at a time.

The web application. The core must not assume whether one will exist.

DXF, GeoJSON, IFC and `.3dm` import or export. The entry point takes coordinate
tuples, which is the smallest input that works and keeps every format an
adapter written later against a stable seam.

Structural sizing, snow and wind loading, and building-code checking beyond the
geometric bounds already stated.

## Further Notes

**The risk is robustness, and it is the whole risk.** ADR-0001 chose to own the
algorithm knowing this. The literature is explicit that weighted straight
skeletons are ambiguous at parallel adjacent edges of differing weight, and that
weighted skeletons of simple polygons can contain cycles and crossings.
Restricting to positive weights avoids the worst of it, but degenerate inputs
will still find bugs. This is why the corpus of real footprints is a deliverable
and not a nicety, and why the milestone is "correct on real footprints" rather
than a feature count.

**Two requirements exist for a consumer that isn't built yet.** Deterministic
tie-breaking and failure-as-a-value are both cheap now and expensive to
retrofit, and `docs/future-work.md` records why the optimizer needs them. They
are the only concessions to future work in this scope, and both are good
practice regardless.

**A limitation to document rather than hide.** The straight skeleton cannot
represent a roof face spanning several footprint edges, and produces spurious
vertices near certain footprints. Roofs with the same footprint can have different
valid styles. What this library generates is a strict subset of buildable roofs,
and the documentation should say so plainly rather than implying completeness.
