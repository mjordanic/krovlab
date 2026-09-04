# 10: Eaves overhang as an outward offset

**What to build:** The architect applies an eaves overhang in metres and the
roof projects beyond his walls the way a real roof does — eaves past the
footprint edge, and areas and lengths that reflect the roof actually built
rather than the slab beneath it.

The mechanism is deliberately dull: offset the footprint outward by the overhang
and generate the roof of the enlarged footprint. No overhang logic exists inside
the algorithm at all. A hole is offset inward, since an overhang into a
courtyard makes the courtyard smaller.

That leaves offsetting itself as the whole of the work, and it is where the
awkward cases are: a reflex corner offsets outward into a gap that has to be
closed, and a narrow hole or a thin wing can close up entirely under a large
overhang. That last case is a stated failure, not a crash.

**Blocked by:** 03, 08

**Status:** done

**Prior art:** The feature PRD's "Overhang is an offset, not a special case"
decision is the constraint to hold to — if overhang handling starts appearing
inside the wavefront, something has gone wrong. `CONTEXT.md` defines `overhang`
and says plainly that the roof of a footprint with overhang is the roof of a
larger footprint, and defines `eave` as coincident with a footprint edge or its
overhang offset. Ticket 03 owns input validation and the failure taxonomy, so an
overhang that destroys the footprint belongs in that taxonomy rather than a new
mechanism. Ticket 08 established multi-ring footprints, which is why this ticket
waits for it: the offset must handle holes from the start rather than be
retrofitted. `shapely` is available in tests as an independent second opinion on
the offset geometry, and must not be imported by the core.

- [x] A rectangle with an overhang produces a roof whose eaves sit the overhang
      distance outside the footprint, with plan area matching the enlarged
      footprint
- [x] An overhang of zero produces exactly the roof produced with no overhang
      argument at all
- [x] A reflex footprint with an overhang produces a valid roof
- [x] A footprint with a hole and an overhang offsets the hole inward
- [x] An overhang large enough to close a hole or collapse the footprint returns
      a stated failure with the reason
- [x] No part of the wavefront or event handling refers to overhang
- [x] The invariant harness's generator applies overhangs and every property
      from ticket 02 still holds

## Comments

Overhang is a mitered offset at the entry-point boundary (`_offset.py`); the
wavefront never sees it. Outer rings expand, holes shrink. A U-slot whose
inner walls cross is `self_intersection`; an inset past a hole's inradius
(a simple inverted leftover) is `degenerate`. Both kinds are ticket 03's.
Zero overhang short-circuits to the same roof as omitting the argument.
The generator draws 0 m or 0.1–0.6 m. Offset vertices use the miter
formula so axis-aligned edges stay bit-identical.

