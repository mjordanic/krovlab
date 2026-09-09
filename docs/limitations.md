# What this library cannot represent

The roofs this library generates are a strict subset of roofs you can
build. Read this before deciding whether the tool covers a given
building.

Four limits are inherent to the method. They will not go away by
adding features. Other roofs — half-hips, gambrels, dormers — are
simply not produced today; some of those stay reachable later.

## One plane cannot cover several walls

Every roof face rises from exactly one footprint edge. A single plane
that continues across two or more consecutive walls — wrapping a corner
without a hip, or treating a jogged wall as one slope — will not come
out. The library puts a hip or a valley at each corner and gives you
one face per edge.

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

Gable versus hip on an edge is a choice you do have. A Dutch gable, a
barn break, or a different ridge layout on the same plan is not.

## Deferred: roofs that need more than one pitch per wall

These are roofs a builder puts up, and that this library cannot make
today. Half-hips, knee-walls and gablets need the wall to rise
vertically for a stretch before it starts to slope. Gambrels and
mansards need a break in the slope on the same wall — steep, then
shallow. That is later work, not a closed door: the algorithm was
written in-house so these stay reachable. An off-the-shelf skeleton
library would have made them impossible permanently. The reasoning is
in [future work](future-work.md).

- Half-hips
- Knee-walls
- Gablets
- Gambrels
- Mansards

## Not in the model

These are not a later version of the same construction. The model does
not carry them:

- Dormers, chimneys, rooflights, and any other penetration through the roof
  (a courtyard hole is at eave height, with inward faces; a chimney would
  cut the slope above the eaves, which is a different thing)
- Curved walls
- Eaves at more than one height, and split-level buildings
- Several disconnected wings in one call — roof each wing separately

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
