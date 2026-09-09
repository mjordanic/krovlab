# Context

The shared vocabulary for this project. Glossary only — no implementation
details, no specs, no decisions. Decisions live in `docs/adr/`.

When a term here has a precise meaning, use it. Where the domain has several
words for the same thing, the preferred term is given and the synonyms are
listed as "not:" so we don't drift.

## The building

**Footprint** — the closed, planar polygon the roof must cover, given in plan.
Always counter-clockwise, always in metres. A footprint may have holes.
_Not: outline, boundary, plan, slab._

**Wall** — one straight run of facade between corners. The skeleton's unit is
a footprint edge; a straight wall is one edge. Two collinear edges on the
same wall are still two edges, not one wall with two pitches.
_Not: outline wall._

**Hole** — an interior ring of a footprint that the roof does not cover: a
courtyard, light well or atrium. A footprint with a hole is still one footprint,
not two.

**Wing** — a footprint that does not share a wall with another in the same
project. Two detached masses are two wings. A single L-shaped building is
one footprint, not two wings.
_Not: cell._

**Cell** — one footprint roofed by a single straight skeleton, with one eave
height. Two gable roofs that meet at a party wall are two cells. An L-shaped
building drawn as one polygon is one cell.
_Not: wing, zone, part, massing._

**Project** — the roofs of one building, made of one or more cells. Takeoff
sums across cells. A project need not be a single terrain: cells may sit at
different eave heights.
_Not: site, file, model._

**Eave height** — the height above project datum of a cell's footprint plane,
i.e. where that cell's roof meets the wall. Uniform across a cell. A project
may give each cell its own eave height.

## The roof surface

**Roof** — the set of planar faces covering one footprint. A roof is a
*terrain*: exactly one height for every point inside the footprint, so it never
folds back over itself. A geometry that violates this is not a roof, and saying
so is how we reject bad output.

**Face** — one planar piece of the roof, rising from exactly one footprint edge
at that edge's pitch. Every face is a plane, never curved, never warped.

**Pitch** — the angle of a face from horizontal, in degrees, `0 < pitch < 90`.
The single most important design variable. _Not: slope, inclination, fall, rise
over run._ Where the trade uses "rise:run" or a percentage, convert on input and
store degrees.

**Plan area** — the area of a face projected onto the horizontal. Sums to the
footprint area.

**Sloped area** — the true surface area of a face, `plan area / cos(pitch)`.
This is what covering material is bought by, and the distinction from plan area
is the reason the whole tool exists. Never say just "area".

## The lines of the roof

Each is a linear quantity that costs money, so each is counted separately.

**Eave** — the bottom edge of a face, coincident with a footprint edge (or its
overhang offset). Where the gutter goes.

**Ridge** — a horizontal top edge where two faces meet, both sloping away from
it.

**Hip** — a sloping edge where two faces meet convexly, rising from an outside
corner of the footprint.

**Valley** — a sloping edge where two faces meet concavely, rising from a
reflex (inside) corner. Costlier per metre than a hip: it carries water.

**Verge** — the sloping edge at the top of a gable wall, where the roof stops
rather than turning a corner. _Not: rake (US), barge._

**Overhang** — the horizontal distance the roof projects beyond the footprint.
Applied by offsetting the footprint outward before the roof is generated, so the
roof of a footprint with overhang is the roof of a larger footprint.

## Roof types

Named configurations, all expressible as choices on the footprint's edges rather
than as separate algorithms:

**Hip end** — the edge carries a normal sloping face. The default.

**Gable end** — the edge carries no face; the wall rises to meet two adjacent
faces at a verge. The alternative to a hip end, and the main discrete design
variable.

**Shed** — every face but one suppressed; the roof slopes one way only.

**Flat** — pitch at the practical minimum, not literally zero.

Gambrel, mansard and butterfly roofs are out of scope; they need two pitches per
edge, which the model does not carry.

## The algorithm

**Straight skeleton** — the plan-view diagram traced by the footprint edges
moving inward at constant speed. Its edges are exactly the ridges, hips and
valleys. _Not: medial axis_, which is a different construction that produces
curves.

**Weighted straight skeleton** — the same, with each footprint edge moving at
its own speed. Speed corresponds to pitch, so this is what allows a different
pitch per edge. The weighting is what makes the construction fragile; see the
ADRs.

**Weight** — an edge's wavefront speed. Always *multiplicative* unless stated,
and related to pitch by `weight = cot(pitch)`. A larger weight is a flatter
face. Weights must be strictly positive: at zero or below, the skeleton stops
being a tree and the roof stops being a terrain.

Pitch is the design variable and weight is its internal representation. Store
and expose pitch; convert at the boundary. Weight is unbounded as pitch
approaches zero, so no optimizer should ever see one.

**Vertical face** — the degenerate `weight = 0` case: the edge does not move,
so the wall rises straight up and the neighbouring faces close over it. This is
how a gable end is expressed, and it is the only degenerate weight the model
permits.

**Additive weight** — a delay before an edge starts moving, so the wall rises
vertically to some height and only then slopes. Would give half-hips and
knee-walls. Not part of this model, but not foreclosed either; see
`docs/future-work.md`.

**Time** — how far the wavefront has propagated. Because the wavefront rises at
unit rate as it moves in, the time at which a skeleton node is created *is* the
height of that node on the roof. This is why a 2D algorithm produces a 3D roof,
and why there is no separate "make it 3D" step.

**Wavefront** — the shrinking polygon at one instant of the propagation.

**Event** — a moment when the wavefront changes combinatorially: an edge
vanishes, or the wavefront splits in two. Events are where the skeleton's
topology is decided, and where implementations break.

## Quantities and cost

**Takeoff** — the full list of measured quantities derived from a roof: sloped
areas by face, linear metres by line type, counts. Physical and objective;
carries no prices. The takeoff is the tool's primary output and is meaningful
with no price data entered at all.

**Price book** — the user-supplied mapping from takeoff line items to unit
rates. Separable from the takeoff, swappable, and regional. _Not: cost model._

**Cost** — a takeoff priced by a price book. Derived, never measured.

**Covering** — the outer material (clay tile, concrete tile, standing-seam
metal, shingle). Each covering carries a minimum pitch, which is usually the
binding constraint on the whole design.

## Optimization

**Design variable** — a quantity the optimizer may change: per-edge pitch
(continuous) and per-edge hip/gable (discrete).

**Constraint** — a bound a design must satisfy to be admissible at all: minimum
pitch from the covering, maximum ridge height, any pitch range the user locks.
Distinct from cost: a design that violates a constraint is not expensive, it is
invalid.

**Binding constraint** — the constraint actually stopping the optimizer from
going further. Naming it is more useful to the architect than the optimum
itself, because it tells him what to change.
