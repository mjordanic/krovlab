# 01: Roof from a convex footprint at uniform pitch

**What to build:** The architect hands over a convex footprint as a list of
`(x, y)` coordinates in metres and one pitch in degrees, and gets back a roof he
can read quantities off. The roof names its faces, each tied to the footprint
edge it rises from and carrying its pitch, its plan area and its sloped area
separately. It names its arcs, each classified as a ridge, hip or eave and
carrying its length. It gives every node's height, the overall ridge height, and
the total sloped area of the whole roof.

This is the tracer bullet and it establishes the project's single seam: one
entry point taking a footprint and pitches, returning a roof value. The
wavefront, the bisectors and the event queue live behind it and are exercised
only through it. The roof is data — faces, arcs, nodes, quantities — with no
rendering concepts in it at all.

Scope this to the case with no reflex corners, so the only events are edges
vanishing. Later tickets add split events, per-edge pitch, holes, gables and
overhang; validation and the failure taxonomy are ticket 03, so here it is
enough to convert pitch to weight at the boundary and reject a pitch outside
`0 < pitch <= 90`.

Tie-breaking between simultaneous or co-located events must be decided by a
fixed rule and that rule written down, not left to whatever the queue happens to
do. A symmetric footprint — a square is the smallest — reaches this on the first
run, and an ambiguous choice here would later read as noise rather than as the
bug it is.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Prior art:** No code prior art — this is the first feature in the repo. Read
the "Implementation Decisions" and "Testing Decisions" sections of the feature
PRD for the entry point's shape and the reasoning behind the seam, ADR-0001 for
the Felkel–Obdržálek wavefront formulation this must follow, and `CONTEXT.md`
for every term used above. Faces, arcs, nodes, pitch, weight, plan area, sloped
area, ridge, hip, eave and terrain all have exact glossary meanings; use them as
the names in the returned value.

- [ ] A square at uniform pitch returns a roof whose apex height and four faces
      match values computed by hand
- [ ] A rectangle at uniform pitch returns a roof with one ridge, of the length
      and position computed by hand
- [ ] Every skeleton node is equidistant from its defining footprint edges —
      the independent oracle available in the uniform-pitch case, asserted
      directly rather than through our own geometry
- [ ] Face plan areas sum to the footprint area
- [ ] Each face reports its sloped area as its plan area over the cosine of its
      pitch, and knows which footprint edge it rises from
- [ ] Each arc is classified ridge, hip or eave, and reports its length
- [ ] The roof reports every node's height, the overall ridge height, and the
      total sloped area
- [ ] Node heights come from event times directly — there is no separate lifting
      step to build
- [ ] Pitch is converted to weight at the entry point and nowhere else; no
      weight appears anywhere in the returned roof
- [ ] A pitch outside `0 < pitch <= 90` is refused
- [ ] The tie-breaking rule for simultaneous and co-located events is documented
      alongside the code that applies it
- [ ] A test asserts the core imports nothing outside the standard library, so
      the dependency-free promise is enforced rather than hoped for
- [ ] `shapely` may be used in assertions as a second opinion, never imported by
      the core
