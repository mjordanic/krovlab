# 08: Holes

**What to build:** The architect roofs a building around a courtyard or a light
well. He passes the hole as a second ring of coordinates and gets a roof that
covers the footprint and not the hole, with the arcs around the courtyard
classified and measured like any others — the eaves facing inward, the valleys
where the wavefront from the hole meets the wavefront from the outer ring.

A footprint with a hole is still one footprint, not two. Plan areas sum to the
footprint's area with the hole excluded, so the area invariant needs the hole
subtracted rather than a new rule.

The wavefront now starts from more than one ring, which means two wavefronts can
meet and merge — the mirror image of the split events from ticket 06.

**Blocked by:** 07

**Status:** done

**Prior art:** `CONTEXT.md` defines `hole` as an interior ring the roof does not
cover and is explicit that a footprint with a hole is one footprint. Ticket 02's
area invariant needs the hole's area subtracted from the target; that is an edit
to the harness, not an exception to it. Ticket 06's split-event work is the
closest prior art for the topology change, and ticket 04's event log is again
the tool for finding where a merge went wrong. Ticket 03 already refuses a hole
that touches or crosses the outer ring, so this ticket can assume disjoint
rings; if that refusal turns out to be wrong, say so rather than working around
it. The feature PRD's degenerate-input list names a hole touching the outline.

- [x] A rectangular footprint with a rectangular hole produces a valid roof
- [x] Plan areas sum to the footprint area less the hole area
- [x] Arcs around the hole are classified and measured like any others
- [x] Multiple holes work
- [x] The invariant harness's generator produces footprints with holes and every
      property from ticket 02 still holds, drainage included — water in a
      courtyard roof drains to the courtyard's own eaves
- [x] A hole large enough that the roof cannot close produces a stated failure,
      not an exception
- [x] Holes work together with per-edge pitch from ticket 07

## Comments

Hole rings are oriented clockwise so the roofed region stays on the left of
every edge. A merge is the same pointer surgery as a split (logged as
`split`); leftover wavefront vertices on a multi-ring skeleton are
`incomplete`. Pitch lists are concatenated: outer edges, then each hole in
order. Ticket 03's `hole_intersects` refusal still holds, and now also
covers holes that touch each other.

A 1 cm courtyard strip in a 10 m square still roofs (ridge 5 mm, plan area
matches). `incomplete` is reserved for a wavefront that stalls with leftover
vertices on a multi-ring skeleton. Nested holes that do not touch are
`degenerate`.
