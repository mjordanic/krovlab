# 09: Gable ends — `pitch = 90`, with verges

**What to build:** The architect declares an edge to be a gable end and gets the
most common alternative to a fully hipped roof: no face over that edge, the wall
rising straight up, and the neighbouring faces closing over it and meeting the
wall at a verge. The verges come back classified as verges and measured, because
a verge is priced per metre like everything else and is not a hip.

A gable is expressed as `pitch = 90` on that edge, not as a separate flag. That
is the `weight = 0` case: the edge does not move as the wavefront propagates.
Doing it through the pitch parameter is what avoids a parallel gable-mask
argument that would then have to be kept consistent with the pitch list — and it
is the one degenerate weight the model permits.

The area invariant needs care: a gabled edge produces no face, so the remaining
faces must still sum to the whole footprint area with nothing left uncovered.

**Blocked by:** 07

**Status:** ready-for-agent

**Prior art:** The feature PRD's "A gable is `pitch = 90`, not a separate flag"
decision gives the reasoning; ADR-0001 admits `weight = 0` solely as this case.
`CONTEXT.md` defines `gable end`, `verge` (and forbids "rake" and "barge") and
`vertical face`, which is the glossary's name for exactly this degeneracy.
Ticket 07's weighted wavefront is what this extends — `weight = 0` is the
boundary of the strictly-positive regime it established, so the entry point's
pitch constraint of `0 < pitch <= 90` is deliberately inclusive at 90. Ticket
02's harness gains verge classification to check; ticket 05's plan view already
has verge in its colour legend.

- [ ] A rectangle with one edge at `pitch = 90` produces a roof with no face
      over that edge and two verges
- [ ] A rectangle with both short edges gabled produces a simple ridged roof
      with four verges
- [ ] Verges are classified as verges, distinct from hips, and measured
- [ ] Plan areas still sum to the footprint area with a gabled edge present
- [ ] The invariant harness's generator produces gabled edges and every property
      from ticket 02 still holds
- [ ] Gabling every edge, or enough edges that no roof can close, produces a
      stated failure rather than an exception or a broken roof
- [ ] Gables work together with reflex corners and per-edge pitch
