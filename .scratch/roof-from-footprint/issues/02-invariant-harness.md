# 02: Invariant harness — terrain, areas, planarity, drainage, determinism

**What to build:** The architect is told when a roof he has been handed is not a
valid terrain, instead of discovering it on site. The roof carries a validity
result that has actually been checked, and the properties behind that result are
asserted over generated footprints rather than over a handful of examples.

This is the correctness gate every later geometry ticket inherits. Each of them
adds a class of footprint — reflex corners, per-edge pitch, holes, gables,
overhang — and each is finished when this harness passes on it. Building it now,
against the convex uniform case where an independent oracle still exists, is
what makes the harness itself trustworthy before it becomes the only judge.

The properties, all of them held to for every roof generated:

- Face plan areas sum to the footprint area — nothing unroofed, nothing covered
  twice.
- Every face is planar.
- Every face's sloped area is at least its plan area, equal only in the limit.
- The roof is a terrain: sampled points in plan have exactly one height.
- Steepest descent on every face points toward that face's own eave. This is the
  drainage property, and it is the reason a straight skeleton is the right
  algorithm at all — so it is the property that most deserves to exist.
- Every arc classification is consistent with its geometry: ridges horizontal,
  hips rising from convex corners, valleys from reflex corners.
- The same input yields a byte-identical roof across runs.

Generation should produce footprints in the class the code currently claims to
support, so that later tickets widen the generator rather than rewrite the
harness.

**Blocked by:** 01

**Status:** ready-for-agent

**Prior art:** The "Invariants are the primary tests" and "Oracles, where an
independent one exists" passages of the feature PRD list these properties and
say why they, and not the event queue, are the thing to assert. Ticket 01's
hand-computed square and rectangle tests and its equidistance-oracle assertion
are the examples to sit beside; the equidistance oracle survives only until
per-edge pitch lands, which is why these properties must stand on their own.
`hypothesis` is already a dev dependency for the generation. `terrain`, `eave`,
`ridge`, `hip`, `valley`, `plan area` and `sloped area` are glossary terms in
`CONTEXT.md`.

- [ ] Each property above is a named property-based test over generated
      footprints, failing with a message that identifies which property broke
- [ ] The returned roof carries a validity result that reflects these checks,
      so a caller learns the roof is not a terrain without running the tests
- [ ] The drainage property is asserted per face against that face's own eave,
      not against the nearest eave
- [ ] Determinism is asserted by comparing two runs of the same input for exact
      equality, not approximate
- [ ] The generator produces only footprints in the currently supported class,
      and is written so later tickets widen it in place
- [ ] The harness is reusable by later tickets without copying assertions
