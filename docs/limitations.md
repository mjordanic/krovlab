# What this library cannot represent

The roofs this library generates are a strict subset of roofs you can
build. Read this before deciding whether the tool covers a given
building.

Three limits are inherent to the method. They will not go away by
adding features. Other roofs — half-hips, gambrels, dormers — are
simply not produced today; some of those stay reachable later.

## One plane cannot cover several walls

Every roof face rises from exactly one wall. A single plane that
continues across two or more consecutive walls — wrapping a corner
without a hip, or treating a jogged wall as one slope — will not come
out. The library puts a hip or a valley at each corner and gives you
one face per wall.

If two consecutive walls are collinear (the same wall, with a vertex in
the middle), you still get two faces, not one plane spanning both.

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
- Curved walls
- Eaves at more than one height, and split-level buildings
- Several disconnected wings in one call — roof each wing separately

## What a passing fixture means

The [footprint corpus](footprint-corpus.md) reports which committed
footprints currently produce a valid terrain. A pass means the library
roofed that building correctly as a terrain. It does not mean every
roof you might want on that building is representable, and it does not
mean every building you draw will come out.
