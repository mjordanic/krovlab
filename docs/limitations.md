# What this library cannot represent

The roofs this library generates are a strict subset of roofs you can
build. Read this before deciding whether the tool covers a given
building.

Four limits are inherent to the method. They will not go away by
adding features. Other roofs — a butterfly, a mansard as a four-wall
break — are simply not produced today; some of those stay reachable later.

## One plane can cover several walls only as a wrap

Every roof face still rises from footprint edges. Marking consecutive
edges of a cell as one plane — wrapping a corner without a hip — is the
one graph edit: those edges share a pitch and become one face. The cell
is then embedded from a roof graph rather than the wavefront. Alternate
ridge layouts that are not "these walls are one plane" stay out; use a
gable mask or a project of several cells.

A wrap of non-consecutive edges, wrapped edges with disagreeing pitches,
or a wrap that cannot embed as a planar terrain is a named Failure.

## A dormer sits on a host face

A dormer is a small footprint drawn on one host face, not a cell at eave
height. `project` roofs every cell first, then locates each dormer by
plan overlap onto exactly one face of that cell. The child is the
one-footprint function on the dormer ring, lifted onto the host plane —
the dormer's eave is the intersection with the host. Host sloped area
loses the opening; dormer faces add. A project with dormers is not a
single terrain; quantities remain usable and 3D still draws. A plus-shape
or other broken skeleton still hides 3D. A dormer that overlaps two
faces, or that lies outside the host, is a named Failure.

## One straight wall cannot carry two pitches

The dual of the limit above. Two collinear eaves share one supporting
line at eave height. Two planes that contain that line and dip at
different pitches only meet on the wall; inland they give two heights
to the same plan point, so the surface is not a terrain.

The weighted skeleton has no unique answer either: adjacent parallel
edges of differing weight never meet (Biedl et al., 2015). Their
suggested resolution is not two faces — the faster edge takes over and
the slower face has zero area. The library refuses that input as
`unsupported`. Give the wall one pitch, or make a corner in the
footprint so the two eaves are no longer collinear.

A midpoint on an otherwise straight eave, both halves the same pitch,
is a different case: one geometric plane, two combinatorial faces. The
extra vertex traces inland perpendicular to the wall. That roof is a
terrain; it is still not one face spanning both halves. Leave a
straight wall as two endpoints unless you want that split.

## Extra vertices that are not on the building

On some footprints the drawing grows vertices that do not sit on a wall
corner and are not a ridge a carpenter would draw. They are artefacts of
the construction. The covering still meets; the geometry is busier than
the building requires.

## One style among several that would stand

The same walls admit more than one valid roof. This library produces
one of them: a fully hipped roof at the pitches you gave, or a mixed
hip-and-gable roof when you make an edge a gable. A different
arrangement of hips and ridges on the same footprint — one a builder
could equally well put up — is not generated.

Gable versus hip on an edge is a choice you do have. A Dutch gable
(knee height) and a barn break (gambrel) are also choices on an edge.
A different ridge layout on the same plan is not.

## Deferred: roofs that need more than one pitch per wall

These are roofs a builder puts up, and that this library cannot make
today. An off-the-shelf skeleton library would have made them
impossible permanently. The reasoning is in [future work](future-work.md).

- Mansards
- Butterfly roofs

## Not in the model

These are not a later version of the same construction. The model does
not carry them:

- Chimneys, rooflights, and any other penetration that is not a dormer
  (a courtyard hole is at eave height, with inward faces; a chimney would
  cut the slope above the eaves, which is a different thing)
- Curved walls
- Split-level eaves on one cell — each cell has one eave height; two
  eave heights are two cells in a `project`. A pitched shared wall at
  two heights, or a gable against a pitch, is a named Failure.

## A returned `Roof` can still be wrong

`roof` reports input it cannot even start on as a `Failure` (a bowtie,
pitch 0, every edge gabled). Some plans it *does* start on still come
back as a `Roof` whose `validity.is_terrain` is false. The quantities
are then unusable. Check that flag; `validity.reasons` names what broke.

Cases that currently do this, rather than raising or returning
`Failure`:

- A plus-shaped plan, where several split events collide at once
- Some T-shapes at some pitches (the same T at 45° can pass and at 30°
  fail)
- Mixed pitch on some L-shapes, especially a large gap between a
  shallow face and a steep neighbour
- A gable on some edges of an L or a U — not every gable, only some

Simple convex rectangles, L and U at one pitch, rectangular courtyards,
and a gable on a rectangle are the shapes the tests exercise hardest.
Those are the ones to trust first.

Runnable examples of both the method limits and these cases are in
[`notebooks/limitations.ipynb`](../notebooks/limitations.ipynb).

## What a passing fixture means

The [footprint corpus](footprint-corpus.md) reports which committed
footprints currently produce a valid terrain. A pass means the library
roofed that building correctly as a terrain. It does not mean every
roof you might want on that building is representable, and it does not
mean every building you draw will come out.
