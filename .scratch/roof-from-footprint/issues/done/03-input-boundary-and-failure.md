# 03: Input boundary — winding, pitch formats, validation, failure as a value

**What to build:** The architect stops having to know what the library wants.
He types his footprint in whichever direction he drew it and it works. He gives
pitch as degrees, or as a rise:run ratio, or as a percentage, and it is
converted for him. When his input cannot be roofed he is told so, and told why,
in terms he can act on — rather than getting an exception or, worse, a
plausible-looking roof.

Failure is a returned value carrying a reason, not a raised exception.
Exceptions stay reserved for programmer error. This matters beyond tidiness: a
caller processing a folder of footprints must not be derailed by one bad one,
and the optimizer this library is eventually for will generate degenerate
configurations by the thousand and has to keep going.

The refusals to cover: a self-intersecting footprint; a degenerate one (a single
point, a line, coincident vertices, collinear edges that leave no area); a hole
touching or crossing the outer ring; a pitch outside `0 < pitch <= 90`; a pitch
list whose length does not match the number of footprint edges. Each has a
defined outcome — a roof or a stated failure — and never an exception and never
a silently wrong result. Collinear edges and coincident vertices may well be
roofable rather than refusable; whichever it is, decide it and assert it.

Units are metres and degrees throughout, at the boundary and in the returned
roof, so the internal representation never surfaces.

**Blocked by:** 01

**Status:** done

**Prior art:** The "Failure is a return value" decision in the feature PRD gives
the reasoning, and the "Degenerate inputs are tests, not edge cases to handle
later" passage lists the cases. Ticket 01 already refuses a pitch outside the
valid range at the entry point; fold that into the taxonomy built here rather
than leaving two mechanisms. `CONTEXT.md` says a footprint is always
counter-clockwise and always in metres — that is the normalised form this
boundary produces — and defines `pitch` as degrees with rise:run and percentage
named as trade conventions to convert on input.

- [x] A footprint given clockwise and the same footprint given
      counter-clockwise produce the same roof
- [x] Pitch accepts degrees, a rise:run ratio and a percentage, and the three
      spellings of the same slope produce the same roof
- [x] Every value in the returned roof is in metres and degrees
- [x] A self-intersecting footprint returns a failure naming self-intersection
- [x] Each degenerate input in the list above has a test asserting its decided
      outcome, whether that is a roof or a named failure
- [x] A pitch list of the wrong length returns a failure saying so
- [x] No input, however malformed, raises out of the entry point
- [x] The failure value carries a reason a person can read, and enough
      structure that a caller can branch on the kind of failure

## Comments

Decided outcomes at the boundary:

- A closing duplicate of the first vertex is a closed-ring spelling and is stripped.
- Mid-ring coincident consecutive vertices are `degenerate`.
- Collinear vertices that still enclose area are roofed (same building, extra eave point).
- A zero-area ring (point, line, cancelled bowtie area) is `degenerate`, except a crossing bowtie is `self_intersection` first.
- A matching-length pitch list of the same slope (any spelling) produces a roof.
- Differing per-edge pitches, and a geometrically valid hole, are `unsupported` until those tickets.
