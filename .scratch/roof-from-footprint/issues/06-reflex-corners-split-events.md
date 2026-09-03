# 06: Reflex corners — split events and valleys

**What to build:** The architect's L-shaped, T-shaped and U-shaped buildings get
roofed. These are the buildings he actually draws; up to now only convex
footprints worked, which is to say only the shapes he rarely builds. The roof
comes back with valleys in it, classified as valleys and measured, because a
reflex corner is where water collects and a valley costs more per metre than a
hip.

This is where the wavefront gains split events: a reflex vertex reaching an
opposing edge divides the shrinking polygon in two. Split events are, by
ADR-0001's own admission, where implementations break — so this ticket is
finished when the invariant harness passes on reflex footprints, not when an
L-shape looks right.

**Blocked by:** 02, 04

**Status:** ready-for-agent

**Prior art:** Ticket 02's invariant harness is the correctness gate: widen its
generator to produce reflex footprints and keep every property passing,
especially drainage and the terrain property, which is where a mishandled split
shows up. Ticket 04's event log is the debugging tool for this work — a
misplaced split event is far easier to find in the log than in the output
geometry. The feature PRD's worked-example list promises an L-shape with exactly
one valley. `CONTEXT.md` defines `valley` as rising from a reflex corner and
`event` as including the wavefront splitting in two. The equidistance oracle
from ticket 01 still holds here, since pitch is still uniform — use it while it
lasts.

- [ ] An L-shaped footprint at uniform pitch produces a roof with exactly one
      valley
- [ ] T-shaped and U-shaped footprints produce valid roofs
- [ ] Valleys are classified as valleys, distinct from hips, and measured
- [ ] The invariant harness's generator produces reflex footprints and every
      property from ticket 02 still holds
- [ ] The equidistance oracle still passes on reflex footprints at uniform pitch
- [ ] Simultaneous split events from a symmetric footprint resolve by the
      documented tie-breaking rule, deterministically
- [ ] A footprint whose split events collide at a single point produces a roof
      or a stated failure, never an exception
